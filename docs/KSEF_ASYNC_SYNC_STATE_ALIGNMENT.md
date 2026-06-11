# KSeF async sync — wyrównanie stanu KSeFSyncStateRepository

Data: 2026-05-22

## Cel

Asynchroniczny job `sync_purchase_invoices` ma aktualizować `KSeFSyncStateRepository` tak samo jak synchroniczny `POST /api/v1/ksef/sync/purchases`.

## Problem

Worker wywoływał bezpośrednio `KSeFSessionService.sync_received_invoices()` — pobieranie faktur działało, ale **pomijało** warstwę stanu:

- brak `mark_running` przed importem,
- brak `mark_success` z licznikami po sukcesie,
- brak `mark_error` przy wyjątku.

Efekt: `GET /api/v1/ksef/sync/status` nie odzwierciedlał async jobów; UI pokazywało nieaktualny „Sync: …”.

## Rozwiązanie

Jedna linia zmiany architektury w handlerze joba: zamiast `sync_received_invoices()` użyto **`sync_purchase_invoices()`** z tymi samymi parametrami z payloadu joba (`nip`, `date_from`, `date_to`, `actor_user_id`).

Metoda `sync_purchase_invoices()` (już używana przez endpoint synchroniczny):

1. `mark_running("purchase_invoices")`
2. `sync_received_invoices(...)` — **bez zmian** logiki pobierania
3. `mark_success(...)` z `state_json` (daty, subject_type, last_counts)
4. przy wyjątku: `mark_error(...)` + re-raise

Handler mapuje raport z powrotem na format wyniku joba (`saved`, `received`, …) wymagany przez `SyncPurchaseResponse` i frontend.

## Zmienione pliki

| Plik | Zmiana |
|------|--------|
| `app/worker/job_handlers/sync_purchase_invoices.py` | `sync_purchase_invoices()` zamiast `sync_received_invoices()`; mapowanie liczników dla job result |

**Bez zmian:** endpointy API, frontend, `sync_received_invoices`, KSeF client, worker loop.

## Wpływ na istniejące endpointy

| Endpoint | Wpływ |
|----------|--------|
| `POST /api/v1/ksef-sessions/sync-purchase` | Brak zmiany kontraktu (202 + job_id) |
| `GET /api/v1/ksef-sessions/sync-purchase/jobs/{job_id}` | Brak zmiany — result nadal `{saved, received, skipped_existing, skipped_parse}` |
| `POST /api/v1/ksef/sync/purchases` | Bez zmian |
| `GET /api/v1/ksef/sync/status` | **Po async jobie** status przechodzi `running` → `success`/`error` jak przy sync synchronicznym |

## Zachowanie UI

Bez zmian w React — `runPurchaseSync()` nadal polluje job i odświeża `getPurchaseSyncStatus()` po zakończeniu. Po wdrożeniu backendu pole „Sync: …” w topbarze będzie aktualizowane również podczas i po async imporcie.

## Ryzyko wdrożenia

| Ryzyko | Ocena | Uwagi |
|--------|-------|-------|
| Regresja pobierania faktur | **Niskie** | Ta sama metoda `sync_received_invoices` wewnątrz `sync_purchase_invoices` |
| Zmiana zakresu dat joba | **Niskie** | Przy podanym `date_from` w payloadzie `resolve_purchase_sync_window` zwraca dokładnie `(date_from, date_to)` |
| Konflikt stanu sync (sync + async równolegle) | **Średnie** | Oba kanały piszą ten sam scope `purchase_invoices` — jak wcześniej przy dwóch synchronicznych wywołaniach; nie wprowadzono nowego locka |
| Wymaga restartu workera | **Tak** | Zmiana kodu handlera — redeploy/restart procesu worker |
| Wymaga rebuildu frontendu | **Nie** | Brak zmian UI |

## Wdrożenie

1. Wdróż backend + **zrestartuj worker**.
2. Uruchom async sync z UI („Odśwież KSeF”).
3. W trakcie: `GET /api/v1/ksef/sync/status` → `status: "running"`.
4. Po zakończeniu: `status: "success"`, `last_success_at` zaktualizowany, `state_json.last_counts` z licznikami.
