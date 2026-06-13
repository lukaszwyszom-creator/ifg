# KSeF purchase — zerowe netto/VAT w totals_json

**Data:** 2026-06-13  
**Produkcja:** DS723+  
**Zakres:** import FA(3), `totals_json`, `invoice_items`

---

## Diagnoza

### Struktura danych

| Warstwa | Pola kwot |
|---------|-----------|
| `invoices.totals_json` | `total_net`, `total_vat`, `total_gross` (stringi) |
| `invoice_items` | `net_amount`, `vat_amount`, `gross_amount` |

Brak `items_json` na fakturze — pozycje wyłącznie w `invoice_items`.

### Przyczyna (A + D)

**A) Parser sum z XML** — `_extract_totals()` sumuje wyłącznie nagłówek FA(3): `P_13_*` (netto) i `P_14_*` (VAT) oraz `P_15` (brutto).

Część faktur zakupowych (np. usługi księgowe, art. 106e ust. 7/8) ma:
- poprawne **`P_15`** (brutto) w nagłówku,
- **brak** `P_13_*` / `P_14_*` w nagłówku,
- poprawne kwoty w pozycji: **`P_11A`**, **`P_9B`**, `P_12`.

Parser pozycji (poprzedni fix) wylicza net/VAT z linii, ale **nagłówek faktury** trafiał do `totals_json` bez fallbacku → `total_net=0`, `total_vat=0`, `total_gross=P_15`.

**B) Parser pozycji** — po fixie P_11A/P_9B pozycje są OK; problem dotyczy głównie **nagłówka totals**, nie linii.

**C) Zapis totals_json** — `ksef_session_service` kopiuje `parsed["total_net/vat/gross"]` 1:1 do `Invoice.total_*` → mapper zapisuje `totals_json`. Brak błędu w zapisie.

**D) Dane historyczne** — faktury zaimportowane **przed** fallbackiem totals (lub gdy pozycje miały zera, a nagłówek tylko P_15) nadal mają `total_net/total_vat=0` w DB mimo poprawnych pozycji po późniejszym repair pozycji.

### Porównanie przypadków

| | Faktura OK | Faktura zła |
|---|-----------|-------------|
| Nagłówek XML | `P_13_1`, `P_14_1`, `P_15` | tylko `P_15` |
| Pozycja XML | `P_11` / `P_9A` | `P_11A` / `P_9B` |
| `totals_json` | net/vat/gross > 0 | net=0, vat=0, gross OK |
| `invoice_items` | kwoty > 0 | kwoty > 0 (po fixie pozycji) |

### SQL diagnostyczny (produkcja, read-only)

```sql
SELECT i.id, i.number_local, i.ksef_reference_number, i.issue_date,
       i.seller_snapshot_json->>'name' AS seller,
       i.totals_json,
       COUNT(ii.id) AS items,
       SUM(ii.net_amount) AS sum_net,
       SUM(ii.vat_amount) AS sum_vat,
       SUM(ii.gross_amount) AS sum_gross
FROM invoices i
JOIN invoice_items ii ON ii.invoice_id = i.id
WHERE i.direction = 'purchase'
  AND COALESCE((i.totals_json->>'total_gross')::numeric, 0) > 0
  AND (
    COALESCE((i.totals_json->>'total_net')::numeric, 0) = 0
    OR COALESCE((i.totals_json->>'total_vat')::numeric, 0) = 0
  )
GROUP BY i.id
ORDER BY i.issue_date DESC;
```

---

## Fix (kod)

### `app/integrations/ksef/xml_parser.py`

- `_sum_item_totals()` — suma net/VAT/brutto z pozycji parsera
- `_resolve_totals_with_item_fallback()` — gdy nagłówek nie ma P_13/P_14:
  - uzupełnia `total_net` / `total_vat` z pozycji (> 0),
  - nie nadpisuje poprawnych wartości z nagłówka,
  - jeśli jest `P_15` i net z pozycji, VAT z pozycji lub `gross - net`.

### Testy regresji

- `test_parse_fa3_xml_totals_fallback_from_items_when_header_p13_missing`
- `test_parse_fa3_xml_header_totals_not_overwritten_by_item_fallback`

---

## Naprawa danych historycznych

Skrypt: `scripts/repair_purchase_totals_from_items.py`

- **dry-run domyślnie**
- tylko `direction='purchase'`
- tylko gdy `total_net` lub `total_vat` = 0/null **oraz** suma pozycji > 0
- raport JSON: `docs/KSEF_PURCHASE_TOTALS_REPAIR_REPORT.json`

```bash
# Diagnostyka (bez zapisu)
.venv/bin/python scripts/repair_purchase_totals_from_items.py

# Produkcja — WYMAGA pg_dump przed --apply
docker compose -f docker/docker-compose.prod.yml exec db \
  pg_dump -U postgres ksef_backend -Fc > backup_pre_totals_repair.dump
.venv/bin/python scripts/repair_purchase_totals_from_items.py --apply
```

**Nie uruchamiać `--apply` bez potwierdzenia i backupu.**

---

## Wykonanie wdrożenia (2026-06-13)

| Krok | Status |
|------|--------|
| Commit `27fa7e4` + push `production` | OK |
| DS723+ `git pull` + rebuild `api`/`worker` | OK |
| Health `http://127.0.0.1:8000/health` | OK |
| `pg_dump` przed repair | `backups/backup_pre_totals_repair_20260613_225057.dump` (106K) |
| Repair dry-run | 3 kandydatów (VAT=0 przy poprawnym netto — faktury zw/exempt) |
| Repair `--apply` | 3 faktury zaktualizowane |
| Purchase z `total_net=0` po repair | **0** |

Raport repair na DS723+: `backups/KSEF_PURCHASE_TOTALS_REPAIR_REPORT.json`

Commit follow-up: `d29277a` — mkdir dla raportu skryptu repair.


```bash
docker compose -f docker/docker-compose.prod.yml up -d --build api worker
```

Nowe importy KSeF od razu dostaną poprawne `totals_json`. Stare rekordy — opcjonalnie skrypt repair.

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/integrations/ksef/xml_parser.py` | fallback totals z pozycji |
| `tests/unit/test_ksef_xml_parser.py` | 2 testy regresji |
| `scripts/repair_purchase_totals_from_items.py` | dry-run repair historyczny |
| `docs/KSEF_PURCHASE_TOTALS_ZERO_FIX.md` | ten raport |
