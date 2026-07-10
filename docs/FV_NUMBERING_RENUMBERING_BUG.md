# Renumeracja faktur sprzedaży — raport

Data: 2026-05-22

## Problem

Po utworzeniu dwóch faktur sprzedaży w tym samym miesiącu:
- FV A i FV B początkowo pokazywały ten sam numer (np. `01/06/2026`),
- po zapisaniu FV B numer FV A zmieniał się na `02/06/2026`, a FV B dostawała `01/06/2026`.

## Przyczyna

**Dwa niezależne źródła błędu:**

### 1. Frontend — dynamiczna numeracja w UI (główna przyczyna widocznego efektu)

Plik `InvoiceCardList.jsx` dla faktur **sale** bez `number_local` w bazie nadawał **tymczasowy** numer (`ui:temporary_sequence`) na podstawie pozycji faktury na liście (sortowanie po `issue_date` + indeks w tablicy).

Przy odświeżeniu listy po zapisaniu kolejnej faktury kolejność elementów się zmieniała → tymczasowe numery były przydzielane na nowo → wyglądało to jak renumeracja już „zapisanych” faktur.

Numery w formacie `01/06/2026` to **wyłącznie warstwa prezentacji** — backend przechowywał `FV/1/06/2026`, a UI obcinało prefix `FV/`.

### 2. Backend — brak numeru przy tworzeniu

`create_invoice()` zapisywał fakturę sale ze `number_local=None`. Numer był nadawany dopiero przez `mark_as_ready()` / `ensure_number_local()` (np. przed wysyłką do KSeF), więc przez długi czas faktury na liście nie miały trwałego numeru w DB.

`get_next_sequence_number()` używał `COUNT(*)` zamiast `MAX(seq)` — mniej odporne na luki w numeracji.

## Rozwiązanie

| Warstwa | Zmiana |
|---------|--------|
| **Backend** | Numer sale nadawany **jednorazowo** w `create_invoice()` przez `_allocate_number_local()` |
| **Backend** | `mark_as_ready()` nadal uzupełnia brakujący numer (stare faktury), ale nie zmienia istniejącego |
| **Backend** | `get_next_sequence_number()` → `MAX(seq)` z parsowania `FV/{seq}/{MM}/{YYYY}` |
| **Frontend** | Usunięto `ui:temporary_sequence`; wyświetlany jest wyłącznie `number_local` z API (lub `—`) |

## Zmienione pliki

- `app/services/invoice_service.py` — `_allocate_number_local()`, numer przy create
- `app/persistence/repositories/invoice_repository.py` — `get_next_sequence_number()` na MAX(seq)
- `frontend-react/src/components/invoice/InvoiceCardList.jsx` — usunięcie dynamicznej renumeracji
- `tests/unit/test_invoice_numbering_regression.py` — test regresyjny (nowy)
- `tests/unit/test_invoice_service.py` — aktualizacja testów create

## Testy regresyjne

Plik: `tests/unit/test_invoice_numbering_regression.py`

Scenariusz:
1. Utwórz FV A → `FV/1/06/2026`
2. Utwórz FV B → `FV/2/06/2026`
3. Ponowny odczyt A i B → numery bez zmian
4. `mark_as_ready` na fakturze z numerem → idempotentne, numer bez zmian

Uruchomienie:
```bash
pytest tests/unit/test_invoice_numbering_regression.py -q
```

## Ryzyko dla istniejących danych

| Ryzyko | Opis | Mitigacja |
|--------|------|-----------|
| Faktury sale bez numeru | Starsze rekordy ze `number_local=NULL` nadal wymagają `mark-as-ready` lub wysyłki KSeF | Endpoint `mark-as-ready` bez zmian; `ensure_number_local` działa |
| Duplikaty numerów historyczne | Brak UNIQUE na `number_local` w DB — stare duplikaty nie są auto-naprawiane | Weryfikacja ręczna SQL jeśli podejrzenie kolizji |
| Nowe faktury | Od teraz numer nadawany przy create — brak okresu „bez numeru” | — |
| Frontend | Faktury bez numeru pokazują `—` zamiast tymczasowego numeru | Zamierzone — nie wprowadza użytkownika w błąd |

## Weryfikacja manualna

1. Utwórz dwie faktury sprzedaży w tym samym miesiącu.
2. Sprawdź numery na liście: `01/MM/RRRR`, `02/MM/RRRR`.
3. Odśwież stronę — numery muszą pozostać identyczne.
4. Podgląd HTML/PDF obu faktur — numer zgodny z listą.
