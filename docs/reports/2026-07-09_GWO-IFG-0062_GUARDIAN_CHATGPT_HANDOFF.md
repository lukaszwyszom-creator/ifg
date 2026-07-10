# GWO-IFG-0062 — GUARDIAN CHATGPT HANDOFF

**Data:** 2026-07-09  
**Status:** DONE (implementacja lokalnego workflow + testy jednostkowe dodane + smoke test)

🩷 STATUS KOŃCOWY

✅ Co działa
- Dodano workflow handoff dla IFG dostępny z CLI:
  - `guardian ifg handoff latest`
- Workflow skanuje najnowsze raporty `.md` w `docs/reports`.
- Preferowane są raporty z dzisiejszą datą (`YYYY-MM-DD` w nazwie pliku).
- Tworzony jest zbiorczy plik:
  - `reports/CHATGPT_HANDOFF_YYYY-MM-DD.md`
- Na początku pliku dodawane jest streszczenie:
  - liczba raportów,
  - wykryte identyfikatory GWO,
  - lista scalonych plików.
- Następnie wklejana jest pełna treść każdego raportu.
- Na końcu dodawana jest sekcja:
  - `## Wygenerowane raporty`
  - z pełnymi ścieżkami względnymi do repo.
- Dla macOS dodano opcjonalne kopiowanie do schowka (`pbcopy`) — domyślnie włączone, wyłączalne przez `--no-clipboard`.

⚠️ Znane problemy
- W tym środowisku lokalnym nie był dostępny `pytest`, więc pełny run testów `pytest` nie został uruchomiony; wykonano smoke testy modułu i CLI.

❌ Co nie działa
- Brak nowych problemów funkcjonalnych.

## A. ROOT CAUSE
Przekazywanie raportów Cursor → ChatGPT było manualne (wyszukiwanie plików i kopiowanie treści), co zwiększało ryzyko pominięcia raportu lub błędu operatora.

## B. ZMIENIONE PLIKI
- `scripts/ifg_guardian/modules/ifg_handoff.py`
  - nowy moduł workflow handoff:
    - selekcja raportów z preferencją dnia bieżącego,
    - ekstrakcja identyfikatorów GWO,
    - generacja zbiorczego markdown,
    - opcjonalne `pbcopy` na macOS.
- `scripts/ifg_guardian/cli.py`
  - nowa ścieżka CLI:
    - `ifg handoff latest`
    - opcje: `--limit`, `--[no-]clipboard`
  - walidacja `--limit >= 1`.
- `tests/unit/test_guardian_ifg_handoff.py`
  - nowe testy jednostkowe (logika wyboru raportów, generacja pliku, dispatch CLI).

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem zadania).

## D. TESTY
Wykonano:
- smoke test modułu handoff (lokalny skrypt Python z `PYTHONPATH=scripts`) — **OK**
- smoke test CLI:
  - `python3 scripts/guardian.py ifg handoff latest --limit 2 --no-clipboard` — **OK**

Dodane (do regularnego uruchamiania w CI/lokalnie):
- `tests/unit/test_guardian_ifg_handoff.py`

Niewykonane z powodu środowiska:
- `pytest` (brak `pytest`/zależności w aktualnym interpreterze)

## E. NASTĘPNY KROK
Dodać uruchomienie `tests/unit/test_guardian_ifg_handoff.py` do istniejącej ścieżki testowej Guardiana w CI, aby automatycznie weryfikować workflow handoff.

## RYZYKO REGRESJI
- **Niskie**:
  - brak zmian w kodzie produkcyjnym IFG,
  - brak zmian backend/API/modeli danych,
  - zmiany dotyczą wyłącznie narzędzia operacyjnego Guardiana i generacji plików markdown.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0062_GUARDIAN_CHATGPT_HANDOFF.md`
- `reports/CHATGPT_HANDOFF_2026-07-09.md`
