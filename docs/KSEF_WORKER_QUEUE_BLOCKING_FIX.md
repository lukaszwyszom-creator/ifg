# Fix: worker nie blokuje wysyłki FV przez sync zakupów (HTTP 429)

**Data:** 2026-05-22  
**Powiązane:** `docs/KSEF_WORKER_QUEUE_BLOCKING_ANALYSIS.md`

## Problem

Jeden job `sync_purchase_invoices` mógł zablokować worker na `time.sleep(retry_after)` (~2041 s przy 429), przez co `submit_invoice` pozostawał w `queued`.

## Wdrożone zmiany

### 1. `app/worker/__main__.py`

- `BATCH_SIZE = 1` — jeden job na tick, brak „martwych” jobów w batchu.
- `claim_priority_jobs()` — kolejność: `submit_invoice` → `poll_ksef_status` → `sync_purchase_invoices`.
- Obsługa `JobRateLimitDeferredError`: `status=pending`, `available_at=now+retry_after`, `attempts` bez incrementu (cofnięcie po claim).

### 2. `app/worker/job_handlers/sync_purchase_invoices.py`

- `JobRateLimitDeferredError` — sygnał odroczenia dla workera.
- Przed sync: `ksef_client.defer_purchase_rate_limit = True` (w `finally` reset).
- Mapowanie `KSeFRateLimitDeferredError` / `report.rate_limited` → odroczenie joba.

### 3. `app/integrations/ksef/client.py`

- `KSeFRateLimitDeferredError` z `retry_after_seconds`.
- Flaga `defer_purchase_rate_limit`: przy 429 **natychmiastowy raise** zamiast `time.sleep`.
- `_download_metadata_purchase_invoices`: propagacja `KSeFRateLimitDeferredError`.

## Testy regresyjne

`tests/unit/test_background_job_claim.py`:

| Test | Cel |
|------|-----|
| `test_claim_priority_prefers_submit_over_older_sync` | priorytet sprzedaży |
| `test_sync_rate_limit_defers_job_without_consuming_attempt` | defer bez zużycia attempt |
| `test_submit_invoice_runs_immediately_when_sync_is_rate_limited` | submit mimo oczekującego sync |
| `test_defer_purchase_rate_limit_raises_without_sleep` | brak sleep przy defer |

```text
pytest tests/unit/test_background_job_claim.py \
       tests/unit/test_ksef_client_retry.py \
       tests/unit/test_ksef_session_worker.py -q

55 passed
```

## Po deployu

- FV w `queued` powinny przejść do wysyłki bez czekania na koniec sync zakupów.
- Sync zakupów wznowi się po `available_at` (Retry-After z KSeF).
- **Bez zmian danych produkcyjnych** — ręczne ponowienie wysyłki tylko jeśli transmisje utknęły przed deployem.

## Zmienione pliki

- `app/worker/__main__.py`
- `app/worker/job_handlers/sync_purchase_invoices.py`
- `app/integrations/ksef/client.py`
- `tests/unit/test_background_job_claim.py`
