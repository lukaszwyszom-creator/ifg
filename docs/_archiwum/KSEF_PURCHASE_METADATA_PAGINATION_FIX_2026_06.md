# KSeF purchase metadata pagination fix (2026-06)

## Root cause

Synchronizacja zakupów pobierała **tylko pierwszą stronę** metadata (`pageOffset=0`, `pageSize=50`) i kończyła paginację, gdy KSeF zwracał `hasMore=false` — nawet przy pełnej stronie 50 rekordów. W produkcji pierwsze 50 ref zaczynało się od **2026-03-30**, więc faktury z **2026-06-12** (GENERON, P4) nigdy nie trafiały do listy `invoice_refs`.

Dodatkowo stary kod **przerywał po pierwszym niepustym `dateType`** (`PermanentStorage`), nie łącząc wyników z `Invoicing`.

Resume HTTP 429 (commit `ca30742`) działało poprawnie, ale wznawiało pobieranie XML tylko w obrębie niepełnej listy 50 ref.

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/integrations/ksef/client.py` | `_query_purchase_metadata_refs`: pełna paginacja, union dateType, dedup, logi per strona, `max_pages=200`; helpery `_metadata_ref_date_token`, `_metadata_ref_date_range` |
| `tests/unit/test_ksef_metadata_pagination.py` | **nowy** — 4 testy paginacji i union dateType |
| `tests/unit/test_ksef_purchase_sync_resume.py` | Test resume od `current_offset=50` na liście 70 ref |
| `tests/unit/test_ksef_client_retry.py` | Mocki metadata: Invoicing pusta strona po PermanentStorage |

Bez zmian: `ksef_session_service.py`, `sync_purchase_invoices.py` — incremental sync korzysta z `query_purchase_metadata_refs()`.

## Algorytm `_query_purchase_metadata_refs`

Struktura funkcji:

1. `from_dt` / `to_dt` — bez zmian.
2. `all_refs: list[str] = []`, `date_types_used: list[str] = []`.
3. Dla każdego `dateType` w `(PermanentStorage, Invoicing)`:
   - `page_offset = 0`, `pages_fetched = 0`, `date_type_refs: list[str] = []`.
   - Pętla `while pages_fetched < _METADATA_MAX_PAGES` (limit 200 stron):
     - `current_offset = page_offset` — offset logowany i wysyłany **przed** inkrementacją.
     - `POST /invoices/query/metadata` z `pageOffset=current_offset`, `pageSize=50`.
     - Log INFO: `dateType`, `pageOffset`, `pageSize`, `page_refs`, `hasMore`, `total_refs` (przed extend), `page_date_min/max`.
     - Pusta strona → `break`.
     - `date_type_refs.extend(page_refs)`, `pages_fetched += 1`.
     - Kontynuacja gdy `hasMore=true` **lub** strona pełna (`page_refs == pageSize`); WARNING przy `hasMore=false` na pełnej stronie.
     - Stop gdy `hasMore=false` i strona niepełna.
   - Przekroczenie `max_pages` → log ERROR.
   - Niepusty `date_type_refs` → `date_types_used.append`, `all_refs.extend`.
4. Dedup `all_refs` zachowując kolejność.
5. Jeden końcowy log: `subjectType`, `dateTypes`, `raw_refs`, `unique_refs`.
6. `return unique`.

Warunki zakończenia paginacji per `dateType`:

- strona pusta, **lub**
- `hasMore=false` i `page_refs < pageSize`, **lub**
- osiągnięto `_METADATA_MAX_PAGES`.

Kontynuacja mimo `hasMore=false` gdy strona pełna (50 ref) — obejście niepewnego `hasMore` z KSeF.

## PermanentStorage / Invoicing

- Oba typy są **zawsze** odpytywane — brak `break` po pierwszym niepustym.
- Brak `date_type_used`, `refs = batch_refs`, `while True`.
- Wynik = **union** (`all_refs`) z deduplikacją końcową.

## Wynik testów

```bash
.venv/bin/python -m py_compile app/integrations/ksef/client.py
# exit 0

.venv/bin/pytest tests/unit/test_ksef_metadata_pagination.py \
  tests/unit/test_ksef_purchase_sync_resume.py \
  tests/unit/test_ksef_client_retry.py -q
# 30 passed
```

Pokrycie wymagań:

1. page 0=50 + page 50=20 → 70 ref ✓
2. page 0=50, hasMore=false, page 50=20 → 70 ref ✓
3. page 0=50, page 50=0 → 50 ref ✓
4. PermanentStorage + Invoicing union/dedup ✓
5. resume od offset 50 na liście 70 ref ✓
6. Istniejące testy resume ✓

## Migracja DB

**Nie wymagana.**

## Deploy na DS723+

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api worker
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d api worker
```

## Weryfikacja produkcyjna

### 1. Uruchom sync zakupów

NIP `9670402857`, zakres `2026-03-23`–`2026-06-21` — przez UI/API sync zakupów KSeF.

### 2. Logi workera — paginacja i liczba ref

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
export PATH="/var/packages/ContainerManager/target/usr/bin:$PATH"
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production logs worker --tail=300 | grep -E "metadata page|metadata query|incremental sync"
```

Oczekiwania:

- Wiele linii `KSeF metadata page ... pageOffset=0`, `50`, `100`, …
- Końcowy log `raw_refs` / `unique_refs` **> 50**
- `KSeF purchases incremental sync ... refs=` **> 50**

### 3. Ref z 2026-06-12 w DB

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db psql -U ifg -d ifg -c "
SELECT ksef_reference_number, issue_date, created_at
FROM invoices
WHERE direction = 'purchase'
  AND (ksef_reference_number LIKE '%20260612%'
       OR ksef_reference_number LIKE '8762469751-20260612%'
       OR ksef_reference_number LIKE '9512120077-20260612%')
ORDER BY issue_date DESC;
"

sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T db psql -U ifg -d ifg -c "
SELECT MAX(issue_date) AS max_issue_date
FROM invoices
WHERE direction = 'purchase';
"
```

Oczekiwania po udanym sync:

- `max_issue_date >= 2026-06-12`
- Wiersze GENERON / P4: `8762469751-20260612...`, `9512120077-20260612...`

### 4. Probe metadata (opcjonalnie)

```bash
sudo docker compose -f docker/docker-compose.prod.yml --env-file .env.production exec -T api python scripts/ksef_metadata_probe.py \
  --env production --auth fresh --nip 9670402857 \
  --subject Subject2 --date-type PermanentStorage \
  --date-from 2026-03-23 --date-to 2026-06-21 --page-offset 50 --page-size 50
```

Powinna zwrócić kolejne ref (nie pustą stronę), gdy w zakresie jest >50 dokumentów.
