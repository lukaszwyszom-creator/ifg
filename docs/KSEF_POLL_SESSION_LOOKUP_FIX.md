# KSeF poll_ksef_status — naprawa wyszukiwania aktywnej sesji

## Problem produkcyjny

- `ksef_sessions` zawiera aktywną sesję dla NIP `9670402857`
- `submit_invoice` kończy się poprawnie
- `poll_ksef_status` kończy się błędem: `NotFoundError: Brak aktywnej sesji KSeF dla NIP 9670402857`
- transmisje: `failed_retryable`, faktury: `sending`

## Przyczyna

Dwa niezależne błędy w ścieżce poll → lookup sesji:

### 1. NIP z faktury bez normalizacji (główna przyczyna NotFoundError)

`poll_ksef_status` pobierał NIP bezpośrednio z `invoice.seller_snapshot["nip"]` i przekazywał go do `get_session_context()`.

W `ksef_sessions.nip` zapisany jest 10-cyfrowy NIP (`9670402857`, `String(10)`). W snapshot faktury NIP mógł występować jako `PL9670402857` lub `967-040-28-57`.

Lookup w `_get_active_db_session()` używał **dokładnego** porównania `nip == nip` — sformatowany NIP ze snapshotu nie pasował do rekordu w bazie → `NotFoundError`.

`submit_invoice` korzystał z innej ścieżki (kontekst sesji / znormalizowany NIP ze settings), dlatego wysyłka działała mimo tego samego rekordu sesji.

### 2. Porównanie dat expires_at (aware vs naive)

`get_active_session()` porównywało `orm.expires_at <= datetime.now(UTC)`. Przy SQLite w testach (i potencjalnie przy odczytach bez strefy) `expires_at` bywa naive, podczas gdy `now` jest aware → `TypeError`.

Handler `poll_ksef_status` łapie ogólne `Exception`, ustawia retry i loguje stack trace — w produkcji objawiało się to jako `failed_retryable` zamiast jawnego `NotFoundError`.

## Struktura tabeli vs warunki lookup

| Kolumna `ksef_sessions` | Oczekiwanie lookup | Stan przed fixem |
|-------------------------|-------------------|------------------|
| `nip` (10 cyfr) | równość po normalizacji | surowy NIP ze snapshotu |
| `status` = `active` | tak | tak |
| `environment` | zgodny z `auth_provider.environment` | brak filtra |
| `expires_at` | ważność w UTC | porównanie bez normalizacji TZ |

## Naprawa

### `app/services/ksef_session_service.py`

- `_normalize_session_nip()` — jeden format NIP (usuwa `PL`, myślniki, spacje)
- `_as_utc_aware()` — bezpieczne porównanie `expires_at` z `datetime.now(UTC)`
- `resolve_invoice_seller_nip(invoice)` — NIP ze snapshotu (znormalizowany) lub fallback `settings.seller_nip`
- `_get_active_db_session()` — lookup po znormalizowanym NIP, filtr `environment`, `order_by(created_at.desc()).limit(1)`, fallback bez `environment` dla starszych rekordów
- Normalizacja NIP we wszystkich publicznych metodach sesji

### `app/worker/job_handlers/poll_ksef_status.py`

- NIP przez `KSeFSessionService.resolve_invoice_seller_nip(invoice)` zamiast surowego snapshotu

### `tests/unit/test_ksef_poll_session_lookup.py`

- Test normalizacji NIP
- Test: aktywna sesja + `get_session_context("PL9670402857")` → sukces
- Test regresyjny: pełny `PollKSeFStatusJobHandler.handle()` ze sformatowanym NIP w snapshot → polling wywołuje KSeF i kończy `SUCCESS`

## Pliki

| Plik | Zmiana |
|------|--------|
| `app/services/ksef_session_service.py` | normalizacja NIP, lookup sesji, UTC expires |
| `app/worker/job_handlers/poll_ksef_status.py` | `resolve_invoice_seller_nip` |
| `tests/unit/test_ksef_poll_session_lookup.py` | testy regresyjne (nowy) |

## Testy

```bash
pytest tests/unit/test_ksef_poll_session_lookup.py \
       tests/unit/test_ksef_session_service.py \
       tests/unit/test_poll_ksef_status_handler.py -q
```

Wynik: **31 passed**

## Commit

_(uzupełnione po commicie)_

## Wdrożenie

Po merge/deploy worker musi korzystać z wersji z normalizacją NIP. Istniejące transmisje `failed_retryable` / faktury `sending` można ponowić ręcznie (retry jobów) — sesja aktywna w DB będzie już znajdowana.
