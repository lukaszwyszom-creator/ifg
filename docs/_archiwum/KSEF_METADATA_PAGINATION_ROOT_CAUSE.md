# KSeF metadata pagination — root cause

Data: 2026-06-23  
Pliki IFG: `app/integrations/ksef/client.py`, `scripts/ksef_metadata_probe.py`  
Źródła MF: OpenAPI prod `/docs/v2/openapi.json`, `ksef-docs/pobieranie-faktur/przyrostowe-pobieranie-faktur.md`

## Fakty produkcyjne

| Obserwacja | Wartość |
|------------|---------|
| Strona 0 | 50 ref, `hasMore=true`, `isTruncated=false` |
| Strona „2” | `pageOffset=50` → **0 ref**, `hasMore=false` |
| `page_date_max` | 20260605 |
| Subject2 | poprawny (poza zakresem tego raportu) |

---

## 1. Czy `pageOffset` jest używany poprawnie?

### OpenAPI MF (`POST /invoices/query/metadata`)

Parametr `pageOffset`:

> **Indeks pierwszej strony wyników (0 = pierwsza strona).**

Inne endpointy KSeF v2 (uprawnienia, role) opisują paginację jednoznacznie:

> Zapytanie zwraca **jedną stronę wyników** o **numerze** i rozmiarze…  
> Przy `hasMore=true` wywołać ponownie z **kolejnym numerem strony**.

Scenariusz przyrostowy w opisie metadata:

- `hasMore=false` → koniec
- `hasMore=true` i `isTruncated=false` → **zwiększyć pageOffset**
- `hasMore=true` i `isTruncated=true` → zawęzić `dateRange`, `pageOffset=0`

### IFG dziś (`client.py`)

```python
params={"pageOffset": current_offset, "pageSize": _METADATA_PAGE_SIZE}  # 50
# ...
page_offset += _METADATA_PAGE_SIZE  # 0 → 50 → 100 …
```

### Werdykt

**NIE — implementacja jest błędna.**

IFG traktuje `pageOffset` jak **offset rekordów** (0, 50, 100…).  
OpenAPI definiuje `pageOffset` jako **numer strony** (0, 1, 2…).

Prod pasuje do tego błędu:

- `pageOffset=0`, `pageSize=50` → strona 0, 50 wyników, `hasMore=true` (istnieje strona 1)
- `pageOffset=50` → API interpretuje to jako **strona nr 50**, nie „druga paczka po 50 rekordach” → **0 wyników**

Probe (`ksef_metadata_probe.py`) przekazuje `--page-offset` wprost — sam w sobie jest OK do testów, ale domyślne użycie syncu przez klienta ma błąd inkrementacji.

---

## 2. Czy wymagany jest `sortOrder`?

OpenAPI:

- Query param `sortOrder`: `Asc` | `Desc`, **default = `Asc`**
- Sortowanie po polu daty z `dateRange.dateType` (`permanentStorageDate` | `invoicingDate` | `issueDate`)
- MF: *„Do scenariusza przyrostowego należy używać daty PermanentStorage oraz kolejność sortowania Asc”*

IFG **nie wysyła** `sortOrder` — obowiązuje default `Asc`.

**Wniosek:** brak jawnego `sortOrder` **nie tłumaczy** pustej strony przy `pageOffset=50`. To nie jest root cause prod.  
Jawnie `sortOrder=Asc` warto dodać w patchu (zgodność z dokumentacją przyrostową).

---

## 3. Czy offset powinien być liczony inaczej?

**Tak.**

| | IFG (błędnie) | OpenAPI MF |
|---|---------------|------------|
| Strona 1 | `pageOffset=0` | `pageOffset=0` ✅ |
| Strona 2 | `pageOffset=50` | `pageOffset=1` |
| Strona 3 | `pageOffset=100` | `pageOffset=2` |
| Inkrementacja | `+= pageSize` | `+= 1` (numer strony) |

Przy `isTruncated=true` (≥10 000 ref w jednym filtrze) MF wymaga **zmiany `dateRange.from`**, nie dalszego zwiększania offsetu — to osobna gałąź (prod: `isTruncated=false`).

---

## 4. Czy metadata wymaga innego mechanizmu kolejnych stron?

Dla **`POST /invoices/query/metadata`** — nie ma tokena kontynuacji w odpowiedzi prod OpenAPI (`QueryInvoicesMetadataResponse`: `hasMore`, `isTruncated`, `permanentStorageHwmDate`, `invoices[]`).

Mechanizm oficjalny:

1. Paginacja **`pageOffset` (numer strony) + `pageSize` + `hasMore`**
2. Przy `isTruncated=true` — **okno dat** (shift `from` od ostatniego rekordu), reset `pageOffset=0`

MF dodatkowo wskazuje, że przy dużych wolumenach **stronicowanie metadata ma ograniczoną przepustowość** (20 req/h, max 250/ref per request → ~5000 ref/h) i dla produkcyjnego sync rekomenduje **`POST /invoices/exports`**.

---

## 5. Czy `/invoices/exports` rozwiązuje problem `hasMore=true` + pusta druga strona?

**Tak — omija wadliwą paginację metadata.**

| | `query/metadata` | `invoices/exports` |
|---|------------------|---------------------|
| Paginacja | `pageOffset` / `pageSize` / `hasMore` | **Brak** — jedna paczka async |
| Limit | 250/ref na request metadata; 10 000/ref przy `isTruncated` | do **10 000 FV** lub 1 GB na paczkę |
| Kontynuacja | `pageOffset++` lub shift daty | `isTruncated` + `LastPermanentStorageDate` / HWM |
| Metadane | response JSON | `_metadata.json` w paczce (ten sam model `InvoiceMetadata`) |
| XML | osobno `GET /invoices/ksef/{ref}` | w paczce ZIP |

Eksport używa **tych samych filtrów** (`subjectType`, `dateRange`, opcjonalne filtry podmiotu) — bez `pageOffset`.

Dla przypadku prod (50 ref na stronie 0, brak dostępu do strony 1 przez błędny offset):

- **Patch metadata** (`pageOffset=1` zamiast `50`) powinien odblokować kolejne strony, jeśli w KSeF jest >50 FV w zakresie.
- **Exports** daje pełną paczkę bez wielostronnego metadata — rozwiązuje problem strukturalnie i jest **rekomendowany przez MF** do sync przyrostowego.

Exports **nie zmienia** semantyki filtrów — jeśli w KSeF jest tylko 50 FV Subject2 w zakresie, exports też zwróci 50. Ale jeśli problem to wyłącznie błędna paginacja, exports pobierze wszystkie (>50) w jednej paczce.

---

## Podsumowanie jednoznaczne

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy obecna implementacja `pageOffset` jest poprawna? | **NIE** |
| Root cause | Inkrementacja `page_offset += pageSize` (50) zamiast `page_offset += 1` — traktowanie numeru strony jak offsetu rekordów |
| `sortOrder` | Nie wymagany jawnie (default Asc), ale warto dodać |
| Inny mechanizm stron | Numer strony + `hasMore`; przy truncacji — shift daty |
| `/invoices/exports` | Rozwiązuje problem paginacji metadata; MF rekomenduje do sync |

---

## Minimalny patch naprawczy (propozycja)

### A. Metadata — 1 linia logiki + opcjonalnie param (wystarczy na prod)

W `_query_purchase_metadata_refs` (`client.py`):

```python
# było:
page_offset += _METADATA_PAGE_SIZE

# ma być:
page_offset += 1
```

Opcjonalnie w `params`:

```python
params={
    "pageOffset": current_offset,
    "pageSize": _METADATA_PAGE_SIZE,
    "sortOrder": "Asc",
}
```

### B. Probe — dokumentacja / przykład weryfikacji

W `ksef_metadata_probe.py` — komentarz lub help text:

```
# pageOffset = numer strony (0, 1, 2…), NIE offset rekordów
```

Weryfikacja DS723+ po patchu:

```bash
# strona 0
python scripts/ksef_metadata_probe.py ... --page-offset 0 --page-size 50
# strona 1 (NIE 50)
python scripts/ksef_metadata_probe.py ... --page-offset 1 --page-size 50
```

Oczekiwanie: jeśli `hasMore=true` na stronie 0, strona 1 zwraca kolejne ref (w tym po 20260605).

### C. Długoterminowo (poza minimalnym patchem)

Migracja listowania ref na `POST /invoices/exports` + `_metadata.json` — zgodnie z `przyrostowe-pobieranie-faktur.md`, bez paginacji metadata.

---

## Pliki IFG — stan obecny

```712:712:app/integrations/ksef/client.py
params={"pageOffset": current_offset, "pageSize": _METADATA_PAGE_SIZE},
```

```766:766:app/integrations/ksef/client.py
page_offset += _METADATA_PAGE_SIZE
```

```233:233:scripts/ksef_metadata_probe.py
params = {"pageOffset": page_offset, "pageSize": page_size}
```

Probe nie ma błędu inkrementacji (offset podawany ręcznie). Błąd jest w kliencie sync.
