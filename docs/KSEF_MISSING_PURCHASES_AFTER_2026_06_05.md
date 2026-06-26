# KSeF — brak faktur zakupowych po 2026-06-05 (analiza metadata)

**Data:** 2026-06-21  
**Przypadek:** Portal KSeF: GENERON i P4 z **12.06.2026**; IFG po sync: max `issue_date` **05.06.2026**, metadata **50 ref**, brak ref po 05.06.

**Zakres analizy (tylko odczyt kodu):**
- `app/integrations/ksef/client.py`
- `app/services/ksef_session_service.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`

---

## 1. Budowa zapytania metadata

Funkcja: `KSeFClient._query_purchase_metadata_refs()` (`client.py:655–730`)

```
POST /v2/invoices/query/metadata?pageOffset={N}&pageSize=50
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "subjectType": "Subject2",
  "dateRange": {
    "dateType": "<PermanentStorage | Invoicing>",
    "from": "{date_from}T00:00:00Z",
    "to":   "{date_to}T23:59:59Z"
  }
}
```

- `date_from` / `date_to` pochodzą z payload joba → `sync_purchase_invoices()` → `_sync_received_invoices_incremental()` (ISO daty z joba, np. `2026-03-23` – `2026-06-21`).
- Format dat: `_format_metadata_datetime()` — UTC, początek/koniec doby.
- Stałe: `_METADATA_SUBJECT_PURCHASE = "Subject2"`, `_METADATA_PAGE_SIZE = 50`.

Worker (`sync_purchase_invoices.py`) nie modyfikuje body — przekazuje tylko `date_from`, `date_to`, `nip` do serwisu.

---

## 2. Subject2 vs Subject1

| Ścieżka | Subject |
|---------|---------|
| Metadata query (`_query_purchase_metadata_refs`) | **wyłącznie Subject2** (`_METADATA_SUBJECT_PURCHASE`) |
| Incremental sync (worker, `ca30742`) | metadata → **Subject2** (`subject_type_used = "subject2"`) |
| Batch fallback (`sync_received_invoices` bez incremental) | pętla `subject2`, `subject1`, `subject3` — **nie dotyczy workera z defer** |

**Produkcja (log):** `subjectType=Subject2 dateType=PermanentStorage` — potwierdzone Subject2.

Subject1 **nie jest używany** w ścieżce metadata/incremental workera.

---

## 3. Paginacja pageOffset / pageSize

```python
page_offset = 0
while True:
    params = {"pageOffset": page_offset, "pageSize": 50}
    ...
    page_refs = _extract_metadata_invoice_refs(data)
    batch_refs.extend(page_refs)

    has_more = data.get("hasMore") is True
    page_offset += 50
    if not has_more or not page_refs:
        break
```

- `pageOffset` rośnie o **50** (nie o liczbę zwróconych elementów).
- Warunek stopu: **`hasMore != true`** LUB **`page_refs` puste**.

---

## 4. Czy pobierane są wszystkie strony?

**Tylko w ramach jednego `dateType`**, dopóki `hasMore=true` i kolejna strona nie jest pusta.

Produkcja (job `4d6ad6ef`):
```
pageOffset=0  → 200
pageOffset=50 → 200
→ refs=50  (log: PermanentStorage refs=50)
```

Druga strona zwróciła **0 ref** → pętla przerwana (`not page_refs`).

**Nie ma** trzeciej strony (offset 100), bo pętla kończy się po pustej stronie 1.

---

## 5. Scenariusz: page 0 = 50, page 1 = pusta, a w KSeF są nowsze dokumenty

**TAK — możliwe**, na dwa sposoby w obecnym kodzie:

### A. Fałszywie negatywne `hasMore` (paginacja)

KSeF zwraca dokładnie 50 pozycji na stronie 0, ustawia `hasMore=false`, ale łącznie w zakresie jest >50 dokumentów (w tym z 12.06). Klient **nie pobierze** strony 2+, bo zatrzymuje się na `hasMore=false`.

### B. Wczesne przerwanie po `dateType=PermanentStorage` (**silniejsza hipoteza**)

```python
for date_type in ("PermanentStorage", "Invoicing"):
    ...
    if batch_refs:
        refs = batch_refs
        break   # ← NIE wykonuje zapytania Invoicing
```

Jeśli **PermanentStorage** zwróci jakiekolwiek ref (np. 50 szt. do 05.06), kod **nigdy nie odpytuje `dateType=Invoicing`**, pod którym portal mógłby indeksować faktury wg **daty wystawienia** (12.06).

Produkcja: w logach **tylko** `dateType=PermanentStorage`, **brak** linii `dateType=Invoicing`.

---

## 6. Sortowanie metadata a utrata najnowszych

- Kod **nie ustawia** parametru sortowania w body — obowiązuje domyślne sortowanie API KSeF.
- Klient **nie sortuje** ani nie filtruje ref po dacie — bierze listę jak zwróci API.
- Przy domyślnym sortowaniu **rosnącym** i błędnym `hasMore=false` po pierwszej stronie — **ucina się „ogon”** (nowsze dokumenty).
- Przy sortowaniu **malejącym** i limicie 50 bez dalszych stron — zwrócone są „50 najnowszych wg kryterium API”; wtedy brak 12.06 sugerowałby raczej **inny dateType/indeks**, nie sort w kliencie.

**Wniosek:** utrata najnowszych nie wynika z sortowania po stronie IFG, lecz z **zakresu/zwróconej strony metadata** (dateType + paginacja + hasMore).

---

## 7. Jedno potwierdzenie przyczyny

### Log (najszybsze, bez zmian kodu)

```bash
sudo docker compose -f docker/docker-compose.prod.yml logs worker 2>&1 | \
  grep 'KSeF metadata query subjectType'
```

**Oczekiwany wzorzec potwierdzający hipotezę B:**

```
KSeF metadata query subjectType=Subject2 dateType=PermanentStorage refs=50
```

**Brak** drugiej linii:

```
KSeF metadata query subjectType=Subject2 dateType=Invoicing refs=...
```

→ kod zatrzymał się na PermanentStorage i **pominął Invoicing**.

### SQL (potwierdza skutek, nie root cause API)

```sql
SELECT ref
FROM background_jobs b,
     jsonb_array_elements_text(b.payload_json->'resume'->'invoice_refs') AS ref
WHERE b.id = '4d6ad6ef-b187-4fd9-8504-6a63985c5ef9'
  AND ref ~ '202606(0[6-9]|1[0-9]|2[0-9]|30|31)-';
```

Wynik **0 wierszy** → w zwróconej liście metadata **nie ma ref z czerwca po 05.06** (zgodne z obserwacją prod).

---

## Podsumowanie przyczyn

| Hipoteza | Prawdopodobieństwo | Mechanizm |
|----------|-------------------|-----------|
| **Break po PermanentStorage — brak zapytania Invoicing** | **Wysokie (~75%)** | `client.py:710–713` — pierwszy niepusty dateType kończy pętlę |
| Paginacja: 50 + pusta str. 1 + hasMore=false przy >50 FV | Średnie (~40%) | `client.py:705–708` |
| Zły Subject (Subject1) | Niskie (~5%) | Metadata hardcoded Subject2 |
| Bug UI / deduplikacja IFG | Wykluczone | Wszystkie 50 ref już w bazie; brak ref z 12.06 w odpowiedzi KSeF |

---

## Werdykt

| Pole | Wartość |
|------|---------|
| **Przyczyna prawdopodobna** | Metadata query kończy się na **`dateType=PermanentStorage`** (50 ref); **`dateType=Invoicing` nie jest odpytywany** mimo faktur widocznych w portalu z datą wystawienia 12.06.2026. Paginacja (`hasMore` + pusta strona 1) dodatkowo może ucinać wynik do 50 pozycji. |
| **Pewność** | **~75%** (potwierdzone logiem prod: tylko PermanentStorage; analiza kodu `break` po pierwszym dateType) |
| **Plik / funkcja** | `app/integrations/ksef/client.py` → **`KSeFClient._query_purchase_metadata_refs`** (pętla `date_type` + paginacja `pageOffset`) |
| **Wywołanie** | `ksef_session_service._sync_received_invoices_incremental` → `query_purchase_metadata_refs` (worker path) |

---

## Następny krok (poza tym raportem)

Ręczne zapytanie KSeF API (ten sam zakres dat) z **`dateType=Invoicing`** i porównanie, czy ref GENERON/P4 (12.06) pojawiają się — potwierdzi lub obniży hipotezę bez zmiany kodu IFG.
