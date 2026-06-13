# KSeF — naprawa zerowych pozycji faktur zakupowych

**Data:** 2026-06-12  
**Produkcja:** DS723+ (50 faktur KSeF purchase, 16 z zerowymi pozycjami)

---

## Problem

Faktury zakupowe z KSeF mają poprawne `totals_json`, ale `invoice_items` zawiera pozycję z kwotami 0, np.:

| Pole | Wartość |
|------|---------|
| `totals_json` | `{"total_net":"219.51","total_vat":"50.49","total_gross":"270.00"}` |
| pozycja | `Usługi księgowe`, qty=1, `unit_price_net=0`, net/vat/gross=0 |
| `ksef_payload_json` | `{"source_system":"ksef_import"}` |

**Przyczyna:** parser FA(3) (`xml_parser._parse_item`) czytał wyłącznie pola netto `P_11` / `P_9A`. Wiele faktur księgowych (art. 106e ust. 7/8) podaje kwoty brutto w **`P_11A`** i **`P_9B`**. Nazwa pozycji (`P_7`) była poprawna, kwoty — zero. Import zapisywał „cichy” placeholder bez błędu.

**Uwaga:** string „Usługi księgowe” pochodzi z XML (`P_7`), nie z osobnego fallbacku w kodzie IFG.

---

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/integrations/ksef/xml_parser.py` | Obsługa `P_11A`, `P_11Vat`, `P_9B`; wyliczenia netto/VAT; `purchase_items_validation_error()` |
| `app/services/ksef_session_service.py` | Przed zapisem: ERROR + pominięcie faktury gdy `total_gross>0` bez niezerowych pozycji |
| `tests/unit/test_ksef_xml_parser.py` | Test regresji P_11A/P_9B |
| `tests/unit/test_ksef_sync_service.py` | Testy: odrzucenie zerowych pozycji, zapis poprawnego P_11A |

---

## Testy

```bash
pytest tests/unit/test_ksef_xml_parser.py tests/unit/test_ksef_sync_service.py -q
```

Wynik: **12 passed**

---

## Deploy na DS723+

1. **Backup PostgreSQL** (wymagany przed jakąkolwiek naprawą danych):
   ```bash
   docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec db \
     pg_dump -U postgres -d ksef_backend -Fc > backup_pre_ksef_items_$(date +%Y%m%d).dump
   ```
2. Wgraj nowy obraz API/worker (bez `docker compose down -v`).
3. Frontend-react **nie wymaga** rebuildu — zmiany tylko backend.

---

## Plan repair / reimport (16 faktur)

**Cel:** uzupełnić pozycje bez kasowania bazy i bez resetu wolumenów.

### Krok 1 — identyfikacja

```sql
SELECT i.id, i.ksef_reference_number, i.number_local,
       i.totals_json,
       ii.id AS item_id, ii.name,
       ii.net_amount, ii.vat_amount, ii.gross_amount
FROM invoices i
JOIN invoice_items ii ON ii.invoice_id = i.id
WHERE i.direction = 'purchase'
  AND i.ksef_payload_json->>'source_system' = 'ksef_import'
  AND (i.totals_json->>'total_gross')::numeric > 0
  AND ii.net_amount = 0 AND ii.vat_amount = 0 AND ii.gross_amount = 0;
```

### Krok 2 — reimport pozycji (po deploy fixu)

Opcja A — skrypt maintenance (zalecane):

1. Dla każdego `ksef_reference_number` z listy: `GET /invoices/ksef/{ref}` (KSeF API, sesja aktywna).
2. `parse_fa3_xml(xml_bytes)` — nowy parser.
3. Jeśli pozycje niezerowe: `DELETE FROM invoice_items WHERE invoice_id = :id`; wstaw nowe wiersze z ORM/mappera.
4. **Nie** zmieniać `totals_json`, płatności, alokacji.

Opcja B — ręczny sync (tylko nowe faktury):

- Fix zapobiega nowym zerom; **nie** naprawia istniejących 16 bez backfillu (sync pomija duplikaty po `ksef_reference_number`).

### Krok 3 — weryfikacja

```sql
SELECT COUNT(*) FROM invoice_items ii
JOIN invoices i ON i.id = ii.invoice_id
WHERE i.direction = 'purchase'
  AND i.ksef_payload_json->>'source_system' = 'ksef_import'
  AND (i.totals_json->>'total_gross')::numeric > 0
  AND ii.net_amount = 0 AND ii.vat_amount = 0;
-- oczekiwane: 0
```

### Bezpieczeństwo

- ❌ `docker compose down -v`
- ❌ DROP DATABASE / reset wolumenów
- ✅ backup przed UPDATE/DELETE na `invoice_items`
- ✅ naprawa tylko wskazanych faktur KSeF purchase

---

## Zachowanie po fixie

| Scenariusz | Zachowanie |
|------------|------------|
| XML z `P_11A=270`, `P_12=23` | Pozycja: net=219.51, vat=50.49, gross=270 |
| XML z nazwą ale bez kwot, totals>0 | **ERROR** w logu, faktura **nie** zapisana |
| XML bez `FaWiersz`, totals>0 | **ERROR**, pominięcie (wcześniej zapisywało `items=[]`) |

---

## Wykonanie backfill (2026-06-13, DS723+)

Skrypt: `scripts/repair_purchase_items_from_ksef.py`

| Krok | Wynik |
|------|--------|
| Backup | `backups/backup_pre_items_repair_20260613_225855.dump` |
| Naprawione (`--no-ksef`, totals fallback) | **15 / 16** |
| Pozostała | `FAW/00037/W/04/26` — **3 pozycje**, wymaga pobrania XML z KSeF (brak aktywnej sesji) |
| Weryfikacja `FAS/BYD/999/2026` | net=219.51, vat=50.49, gross=270.00 |

Ponowny repair dla `FAW/00037/W/04/26` po połączeniu KSeF:

```bash
sudo docker compose -f docker/docker-compose.prod.yml run --rm --no-deps \
  -v $(pwd)/scripts:/app/scripts:ro api \
  python /app/scripts/repair_purchase_items_from_ksef.py \
  --auth session --number FAW/00037/W/04/26 --apply
```

Raport: `backups/KSEF_PURCHASE_ITEMS_REPAIR_REPORT.json`

---

*KSeF Purchase Items Zero Repair — parser FA(3) + walidacja importu.*
