# KSeF — obsługa HTTP 429 przy pobieraniu faktur zakupowych

Data: 2026-05-22

---

## Problem

Worker sync zakupów startował poprawnie, metadata zwracała np. `count=50`, ale przy pierwszym  
`GET /v2/invoices/ksef/{ksefNumber}` KSeF odpowiadał **429 Too Many Requests**. Job nie kończył się czytelnie — brak statusu/warningu dla UI.

---

## Przyczyna

1. Pobieranie XML używało ogólnego `_request_with_retry`, bez dedykowanej pętli per faktura i logu `KSEF_RATE_LIMIT_RETRY`.
2. Błąd downloadu był tylko logowany w kliencie — **nie trafiał** do `error_samples` raportu syncu.
3. `received` liczyło tylko pobrane XML, nie liczbę refów z metadata — przy samych błędach 429 UI widziało `0 od KSeF`.
4. Brak pola `warning` / `rate_limited` w wyniku joba i API statusu.

---

## Naprawa

| Warstwa | Plik | Zmiana |
|---------|------|--------|
| KSeF client | `app/integrations/ksef/client.py` | `_get_purchase_invoice_xml()` — do 5 prób, backoff, `Retry-After`, log `KSEF_RATE_LIMIT_RETRY` |
| KSeF client | `app/integrations/ksef/client.py` | `QueryReceivedInvoicesResult` — `download_errors`, `rate_limited`, `metadata_refs_count` |
| Service | `app/services/ksef_session_service.py` | merge `download_errors` → `error_samples`, `warning`, `rate_limited` |
| Worker | `app/worker/job_handlers/sync_purchase_invoices.py` | przekazuje `rate_limited` / `warning` w result joba |
| API | `app/api/routers/ksef_session.py` | `SyncPurchaseResponse`, `KSeFPurchaseSyncReportResponse` — pola `rate_limited`, `warning` |
| Frontend | `ksef.js`, `KSeFSessionBar.jsx`, `KSeFTopbarInfo.jsx` | wyświetla `warning` po syncu |

---

## Przepływ po fixie

```
POST /invoices/query/metadata → 50 refs
  → GET /invoices/ksef/{ref}
      → 429 → KSEF_RATE_LIMIT_RETRY ref=… attempt=1 sleep_seconds=…
      → retry (Retry-After lub backoff)
      → sukces → XML zapisany
      → nadal 429 po limicie → error_samples += "{ref}: rate limit (429)…"
  → job status=done, rate_limited=true, warning="KSeF ograniczył tempo…"
  → UI pokazuje warning w komunikacie sukcesu
```

Job **nie wisi** — kończy się statusem `done` (częściowy sukces) lub `failed` tylko przy błędzie krytycznym (np. wygasła sesja).

---

## Logi do monitorowania

```bash
grep KSEF_RATE_LIMIT_RETRY logs/api.log
grep KSEF_ASYNC_SYNC_WORKER_DONE logs/worker.log
```

Przykład:

```
KSEF_RATE_LIMIT_RETRY ksef_reference_number=5265… attempt=2 sleep_seconds=1.20
KSEF_ASYNC_SYNC_WORKER_DONE job_id=… saved=12 received=50 rate_limited=True
```

---

## Testy

```bash
.venv/bin/pytest tests/unit/test_ksef_client_retry.py::TestPurchaseInvoiceDownloadRateLimit -q
.venv/bin/pytest tests/unit/test_ksef_sync_service.py::test_sync_received_invoices_propagates_rate_limit_warning_and_error_samples -q
```

---

## Test plan (prod)

1. Uruchom sync zakupów przy dużej liczbie faktur (≥20).
2. W logach API/worker: sekwencja `KSEF_RATE_LIMIT_RETRY` → ewentualnie retry → `WORKER_DONE`.
3. Job GET `/ksef-sessions/sync-purchase/jobs/{id}` → `status=done`, `result.rate_limited=true`, `result.warning` ustawione.
4. UI „Odśwież KSeF” — komunikat sukcesu zawiera tekst o ograniczeniu tempa KSeF.
5. `GET /ksef/sync/status` → `state_json.last_counts.warning` po syncu z rate limit.
