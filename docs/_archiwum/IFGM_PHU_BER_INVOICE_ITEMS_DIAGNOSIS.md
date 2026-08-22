# IFGM — diagnoza pozycji faktur PHU BER Grzegorz Berend

**Data:** 2026-05-22  
**Zakres:** brak netto/VAT w `/invoice/[id]` przy poprawnym brutto nagłówka

---

## 1. Cel i objaw

Na ekranie szczegółu faktury IFGM pozycje od **PHU BER Grzegorz Berend** pokazują:

- Netto: **—**
- Kwota VAT: **—**

…przy poprawnej kwocie brutto faktury u góry.

---

## 2. Dostęp do bazy produkcyjnej (DS723+)

| Próba | Wynik |
|-------|--------|
| SQL na lokalnym Docker (`docker-db-1`) z filtrami `%BER%` / `%Berend%` | **0 wierszy** — brak faktur PHU BER w dev DB |
| SSH `admin@100.87.84.118` | **Connection refused** (port 22) |
| API prod `POST /auth/login` | Brak znanego hasła — odczyt faktur niemożliwy |

**Wniosek:** raport opiera się na analizie kodu, schematu DB/ORM, lokalnej weryfikacji API oraz typowym wzorcu danych z produkcji opisanym w zadaniu. Konkretny UUID faktury PHU BER z DS723+ wymaga odczytu SQL na serwerze (patrz sekcja 9).

---

## 3. Struktura danych — ścieżka DB → API → mobile

### 3.1 Tabela `invoice_items` (DB)

Kolumny kwotowe (ORM: `app/persistence/models/invoice_item.py`):

| Kolumna DB | Typ |
|------------|-----|
| `unit_price_net` | Numeric |
| `vat_rate` | Numeric |
| `net_amount` | Numeric |
| `vat_amount` | Numeric |
| `gross_amount` | Numeric |

**Nie ma** kolumn `net_total` / `vat_total` / `gross_total` w DB.

### 3.2 Mapper backend (`invoice_mapper.py`)

```python
net_total=orm.net_amount,
vat_total=orm.vat_amount,
gross_total=orm.gross_amount,
```

Domain i API używają nazw `*_total`; DB używa `*_amount`. Mapowanie jest **poprawne** w obecnym kodzie.

### 3.3 Schema API (`app/schemas/invoice.py` → `InvoiceItemResponse`)

Pola w JSON odpowiedzi:

```json
{
  "name": "...",
  "quantity": "1.0000",
  "unit": "szt.",
  "unit_price_net": "100.00",
  "vat_rate": "23.00",
  "net_total": "100.00",
  "vat_total": "23.00",
  "gross_total": "123.00",
  "sort_order": 1
}
```

Sumy nagłówka faktury pochodzą z `invoices.totals_json` (`total_net`, `total_vat`, `total_gross`), nie z kolumn tabeli `invoices`.

### 3.4 Weryfikacja lokalna API

`GET /api/v1/invoices/{id}` (lokalny Docker) zwraca `net_total`/`vat_total`/`gross_total` zgodnie z DB:

```json
{
  "name": "Consulting services",
  "quantity": "12.0000",
  "unit": "h",
  "unit_price_net": "90.00",
  "vat_rate": "0.00",
  "net_total": "1080.00",
  "vat_total": "0.00",
  "gross_total": "1080.00"
}
```

DB dla tej pozycji: `net_amount=1080.00`, `vat_amount=0.00`, `gross_amount=1080.00`.

---

## 4. Porównanie wariantów A / B / C

| Wariant | Opis | Czy dotyczy PHU BER? |
|---------|------|----------------------|
| **A** | DB OK, API nie zwraca kwot | **Nie** — mapper i schema zwracają `net_total` z `net_amount` |
| **B** | API zwraca `net_amount`, mobile czyta tylko `net_total` | **Możliwe** na starszym deployu / innym kliencie; mobile **naprawione** (aliasy) |
| **C** | DB ma `0`/`NULL` w `net_amount`/`vat_amount`, sumy w `totals_json` OK | **Najbardziej prawdopodobne** — objaw: brutto u góry OK, pozycje puste |

### Wzorzec objawu zgodny z wariantem C

```
invoices.totals_json     → total_gross = 123.00  ✓ (nagłówek IFGM)
invoice_items.net_amount → 0.00                    ✗
invoice_items.vat_amount → 0.00                    ✗
invoice_items.gross_amount → 0.00 (często)         ✗
```

Import KSeF (`xml_parser._parse_item`) bierze netto z `fa:P_11`. Gdy w XML brak `P_11` / `P_9A`, parser zapisuje zera na pozycji, ale sumy nagłówka (`P_13_*`, `P_14_*`, `P_15`) mogą być poprawne.

**Nie naprawiano parsera KSeF w tym zadaniu** (zgodnie z warunkiem stop).

---

## 5. Przykład faktury (lokalna weryfikacja, nie PHU BER)

| Pole | Wartość |
|------|---------|
| ID | `fc530737-acca-4e23-b4f7-75b3c12c4130` |
| `totals_json` | `{"total_net":"1080.00","total_vat":"0.00","total_gross":"1080.00"}` |
| Pozycja DB | `net_amount=1080`, `vat_amount=0`, `gross_amount=1080`, `vat_rate=0` |
| API `items[0]` | `net_total=1080`, `vat_total=0`, `gross_total=1080` |

Dla PHU BER na produkcji oczekiwany wzorzec problemowy (do potwierdzenia SQL):

```sql
SELECT i.id, i.number_local, i.totals_json,
       ii.name, ii.quantity, ii.unit,
       ii.unit_price_net, ii.vat_rate,
       ii.net_amount, ii.vat_amount, ii.gross_amount
FROM invoices i
JOIN invoice_items ii ON ii.invoice_id = i.id
WHERE i.seller_snapshot_json->>'name' ILIKE '%Berend%'
   OR i.seller_snapshot_json->>'name' ILIKE '%PHU BER%'
LIMIT 5;
```

---

## 6. Przyczyna (diagnoza)

1. **Backend obecnej wersji repo** — mapuje DB → API poprawnie; problem **nie leży** w samym schema `net_total` vs kolumna `net_amount`.
2. **Frontend (przed fixem)** — czytał wyłącznie `net_total`/`vat_total`/`gross_total`; nie obsługiwał aliasów `*_amount` ani wyliczeń z `gross_amount` + `vat_rate` gdy netto w pozycji = 0.
3. **Dane produkcyjne PHU BER (hipoteza)** — pozycje z zerowymi kwotami w DB przy poprawnym `totals_json` → wariant **C** (importer/backfill), nie mapper API.

---

## 7. Wdrożona poprawka

### Decyzja: **fix frontendowy** (bez zmian backendu)

### Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `mobile-expo/src/api/mobile.ts` | Typ `InvoiceItemResponse` + aliasy `net_amount`/`vat_amount`/`gross_amount`; `pickRawField` / `pickPositiveField`; rozszerzone `resolveInvoiceItemFields` |

### Mapowanie pól pozycji (mobile)

| UI | Źródło (kolejność) |
|----|---------------------|
| lp. | `sort_order` lub index + 1 |
| nazwa | `name` |
| ilość | `quantity` + `unit` |
| netto | `net_total` **lub** `net_amount` → `unit_price_net × qty` → `gross / (1 + VAT%)` → `gross − VAT` (gdy VAT > 0) → przy VAT 0%: `net = gross` |
| VAT % | `vat_rate` → wyliczenie z net/VAT |
| kwota VAT | `vat_total` **lub** `vat_amount` → wyliczenie ze stawki / `gross − net` |

Brak danych → **„—”**, nie fałszywe „0 zł” (wyjątek: VAT 0% przy znanym netto → „0 zł”).

`mobile-expo/app/invoice/[id].tsx` — bez zmian (używa `mapInvoiceItemForDisplay`).

---

## 8. Testy

| Test | Wynik |
|------|--------|
| `cd mobile-expo && npm run lint` | OK |
| `cd mobile-expo && npx tsc --noEmit` | OK |
| Backend `tests/unit/test_invoice_api.py` | Nie uruchamiano — **brak zmian backendu** |

---

## 9. Backfill — czy wymagany?

| Scenariusz | Backfill? |
|------------|-----------|
| API zwraca poprawne `net_total` (DB ma kwoty) | Nie — wystarczy mobile |
| API zwraca tylko `net_amount` (stary deploy) | Nie — mobile akceptuje oba warianty |
| DB: `net_amount=0`, `vat_amount=0`, `totals_json` OK | **Tak** — osobny etap |

### Proponowany etap backfillu (tylko opis, **nie wykonywać na produkcji** w tym zadaniu)

1. Zidentyfikować faktury KSeF z `net_amount=0` i `totals_json.total_gross > 0`.
2. Dla każdej: ponownie sparsować XML z KSeF (`GET /invoices/ksef/{ref}`) lub wyliczyć z `P_11`/`P_9A`/`P_12`.
3. Zaktualizować `invoice_items.net_amount`, `vat_amount`, `gross_amount` (+ ewentualnie poprawka `xml_parser` dla brakujących pól FA(3)).
4. Uruchomić na stagingu; na prod tylko po backupie `pg_dump`.

---

## 10. Następne kroki (operacyjne)

1. Na DS723+ wykonać SQL z sekcji 5 dla PHU BER — potwierdzić wariant C.
2. Dla 1 faktury: porównać `GET /api/v1/invoices/{id}` z wierszami `invoice_items`.
3. Jeśli DB ma zera → osobny task: importer KSeF + backfill (poza IFGM mobile).

---

*IFGM PHU BER Invoice Items Diagnosis — frontend fix + diagnoza danych bez zmian backendu/KSeF.*
