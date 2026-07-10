# IFG TEST DISCOVERY FIX

## Root cause

Nie udało się odtworzyć blokera `Test discovery failed` w bieżącym stanie repo.

`pytest --collect-only` przechodzi poprawnie, więc nie występuje już wyjątek przerywający collect.

Najbardziej prawdopodobna przyczyna historyczna:
- problem został już usunięty we wcześniejszych zmianach środowiska/testów,
- obecny blocker release nie dotyczy discovery, tylko innych warningów (np. lokalny Alembic env check bez `DATABASE_URL`).

## Zmienione pliki

- Brak zmian kodu wymaganych do naprawy collect w tym przebiegu.

## Wynik collect przed

Polecenie:
- `pytest --collect-only`

Wynik:
- `1429 tests collected`
- brak wyjątku podczas collect
- exit code: `0`

## Wynik collect po

Polecenie:
- `pytest --collect-only`

Wynik:
- `1429 tests collected`
- brak wyjątku podczas collect
- exit code: `0`

## Wynik release evaluate

Polecenie:
- `python scripts/guardian.py release evaluate --markdown`

Wynik:
- `Decision: READY_WITH_WARNINGS`
- `Test discovery passed (tests/unit)` (w sekcji Positive Signals)
- brak blockerów związanych z discovery.
