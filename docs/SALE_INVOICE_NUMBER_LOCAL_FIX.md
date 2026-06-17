# Fix: faktura sprzedaży bez `number_local`

**Data:** 2026-05-22  
**Kontekst produkcji:** FV `cc4a8c2f-948d-45e2-86e8-9dd19c7961a5` — `direction=sale`, `status=ready_for_submission`, `issue_date=2026-06-17`, `number_local=NULL`.

## Przyczyna

Ścieżka tworzenia faktury sprzedaży (`InvoiceService.create_invoice`) **już alokuje** `number_local` przed zapisem do DB (fix z wcześniejszej sesji). Faktura produkcyjna bez numeru powstała najpewniej **przed wdrożeniem tego fixu** albo w sytuacji, gdy numer został utracony po zapisie (brak numeru w obiekcie zwróconym z repozytorium).

Punkty nadawania numeru w kodzie:

| Moment | Plik | Zachowanie |
|--------|------|------------|
| `create_invoice` (sale) | `invoice_service.py` | `_allocate_number_local()` przed `add()` |
| Po `add()` (defensywnie) | `invoice_service.py` | uzupełnienie brakującego numeru lub sync prealokacji |
| `update_invoice` (sale, ready) | `invoice_service.py` | `ensure_number_local()` gdy brak numeru |
| `mark_as_ready` | `invoice_service.py` | idempotentne `_assign_number_local()` tylko dla sale |
| Submit KSeF | `transmission_service.py` | `ensure_number_local()` + walidacja przed kolejką |

Zakupy (`direction=purchase`) **nie** przechodzą przez alokację IFG — bez zmian.

## Wprowadzone zmiany

### 1. `app/services/invoice_service.py`

- **Defensywa po `create`:** jeśli sale wraca z DB bez `number_local`, a numer był prealokowany — `update_number_local`; w przeciwnym razie `ensure_number_local`.
- **Defensywa po `update`:** sale w `ready_for_submission` bez numeru → `ensure_number_local`.
- **`_allocate_number_local`:** pętla retry (do `MAX_RETRIES`) przy kolizji numeru zamiast natychmiastowego `IntegrityError`.

### 2. `app/domain/models/invoice.py`

- Czytelniejszy komunikat walidacji: *„Faktura sprzedaży nie ma numeru lokalnego. Zapisz fakturę ponownie przed wysyłką do KSeF.”*

### 3. `app/services/transmission_service.py`

- Jawna walidacja przed enqueue: sale bez `number_local` → ten sam komunikat (po `_prepare_sale_invoice_for_submit`, który próbuje nadać numer).
- `_friendly_submit_error` mapuje błędy numeru na komunikat użytkowy.

## Testy regresyjne

| Test | Plik |
|------|------|
| create sale → dostaje `FV/n/mm/yyyy` | `test_invoice_numbering_regression.py` (istniejący) |
| create purchase → `number_local is None` | `test_invoice_numbering_regression.py`, `test_invoice_service.py` |
| sale z numerem → `mark_as_ready` nie nadpisuje | `test_invoice_numbering_regression.py` (istniejący) |
| sale bez numeru w DB → `update` uzupełnia numer | `test_invoice_numbering_regression.py` |
| submit/retry bez numeru → czytelny błąd | `test_transmission_service.py` |

**Wynik testów:**

```text
pytest tests/unit/test_invoice_service.py \
       tests/unit/test_invoice_numbering_regression.py \
       tests/unit/test_invoice_repository_sequence.py \
       tests/unit/test_transmission_service.py -q

80 passed
```

## Zmienione pliki

- `app/services/invoice_service.py`
- `app/domain/models/invoice.py`
- `app/services/transmission_service.py`
- `tests/unit/test_invoice_service.py`
- `tests/unit/test_invoice_numbering_regression.py`
- `tests/unit/test_transmission_service.py`

## Naprawa rekordu produkcyjnego (bez automatycznego repair)

**Nie wykonano** masowego repair danych.

Dla FV `cc4a8c2f-948d-45e2-86e8-9dd19c7961a5` po wdrożeniu wystarczy **zapisać fakturę ponownie** w UI (PUT) — `update_invoice` nada brakujący numer w statusie `ready_for_submission`. Alternatywnie: endpoint `mark-as-ready` (idempotentny).

Jednorazowy SQL/SQLAlchemy repair możliwy po potwierdzeniu — poza zakresem tego fixu.

## Ryzyka

| Ryzyko | Ocena |
|--------|-------|
| Podwójna numeracja przy race condition | Niska — retry w `_allocate_number_local`, unikalny indeks na `number_local` |
| Nadpisanie istniejącego numeru | Brak — wszystkie ścieżki sprawdzają `(number_local or "").strip()` |
| Zakupy dostają numer IFG | Brak — gałęzie tylko dla `direction == "sale"` |
| Faktury locked (sending/accepted/rejected) | Brak — `ensure_number_local` wymaga `ready_for_submission` |
| Audit `invoice.marked_ready` przy backfill przez update | Akceptowalne — sygnalizuje nadanie numeru |

## Wdrożenie

1. Deploy backendu z powyższymi zmianami.
2. Ręcznie zapisać dotknięte faktury sprzedaży bez numeru (lub potwierdzić jednorazowy repair).
3. Przed wysyłką do KSeF — submit zablokuje sale bez numeru z czytelnym komunikatem.
