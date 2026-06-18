# KSeF — faktura utknięta w `sending` po `failed_retryable`

## Problem produkcyjny

Faktury FV/1–FV/10:
- `invoices.status = sending`
- najnowsza `transmissions.status = failed_retryable`
- `error_message = Brak aktywnej sesji KSeF...`

UI pokazywało „W toku” — brak możliwości ponownej wysyłki.

## Przyczyna

Synchronizacja statusu faktury po transmisji była zaimplementowana tylko dla statusów terminalnych:
- `success` → `accepted`
- `failed_permanent` → `rejected`

Dla `failed_retryable` / `failed_temporary` `TransmissionService.sync_invoice_from_terminal_transmission()` kończyło się na `return` bez zmiany faktury.

Worker `submit_invoice` przy błędach retryable wywoływał `_return_invoice_to_ready_for_submission()`, które **ustawiało status tylko na obiekcie domenowym w pamięci** — bez `invoice_repository.update()`. Transmisja była zapisywana jako `failed_retryable`, faktura w DB pozostawała `sending`.

## Naprawa

### `app/services/transmission_service.py`

`sync_invoice_from_terminal_transmission()` obsługuje `FAILED_RETRYABLE`:
- faktura w statusie `sending` → `ready_for_submission`
- persystencja przez `lock_for_update` + `update`
- bez zmian dla `accepted`, `rejected`, `failed_permanent`

`FAILED_TEMPORARY` pozostaje bez synchronizacji (auto-retry w workerze).

### `app/worker/job_handlers/submit_invoice.py`

`_mark_retryable_failure()` wywołuje `sync_invoice_from_terminal_transmission(..., FAILED_RETRYABLE)` przed flush.

Usunięto redundantne wywołania `_return_invoice_to_ready_for_submission()` przed `_mark_retryable_failure`.

## Pliki

| Plik | Zmiana |
|------|--------|
| `app/services/transmission_service.py` | sync `failed_retryable` → `ready_for_submission` |
| `app/worker/job_handlers/submit_invoice.py` | sync w `_mark_retryable_failure` |
| `tests/unit/test_transmission_service.py` | testy sync retryable |
| `tests/unit/test_ksef_session_worker.py` | asercja `update()` po braku sesji |

## Testy

```bash
pytest tests/unit/test_transmission_service.py::TestSyncInvoiceTerminalStatus \
       tests/unit/test_ksef_session_worker.py::TestNoKSeFSession \
       tests/unit/test_poll_ksef_status_handler.py -q
```

## Commit

_(uzupełnione po commicie)_

## Istniejące dane produkcyjne

Fix dotyczy nowych błędów po deploy. Faktury już utknięte w `sending` wymagają ręcznej korekty statusu (SQL/admin) lub ponownej wysyłki po naprawie sesji KSeF — poza zakresem tego commita (bez zmian danych produkcyjnych).
