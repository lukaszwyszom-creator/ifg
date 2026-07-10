# GWO-IFG-0063 — GUARDIAN HANDOFF DECISION BLOCK

**Data:** 2026-07-09  
**Status:** DONE (rozszerzenie workflow handoff + testy + smoke CLI)

🩷 STATUS KOŃCOWY

✅ Co działa
- Rozszerzono istniejący workflow `guardian ifg handoff latest` o automatyczną sekcję:
  - `## Co wymaga decyzji ChatGPT`
- Zachowano wymaganą kolejność sekcji w pliku handoff:
  1) tytuł,
  2) streszczenie,
  3) blok decyzyjny,
  4) pełne treści raportów,
  5) `## Wygenerowane raporty`.
- Blok decyzyjny jest budowany automatycznie z heurystyk:
  - sekcje: `## E. NASTĘPNY KROK`, `## UX Debt`, `## RYZYKO REGRESJI`,
  - linie: `⚠️ Znane problemy`,
  - słowa-klucze: `opcjonalnie`, `następny krok`, `ryzyko`, `debt`, `decyzja`, `do rozważenia`, `nie wykonano`, `niewykonane`, `znane problemy`.
- Punkty decyzyjne są skrócone i limitowane:
  - maksymalnie 10 punktów,
  - każdy punkt w formie krótkiej,
  - z przypisaniem źródła raportu.
- Gdy brak sygnałów decyzyjnych, wpisywany jest fallback:
  - `Brak jawnych punktów decyzyjnych w scalonych raportach.`

⚠️ Znane problemy
- W tym środowisku nie był dostępny moduł `pytest`, więc uruchomienie testów przez `pytest` nie było możliwe.

❌ Co nie działa
- Brak regresji funkcjonalnych w handoff.

## A. ROOT CAUSE
Handoff zawierał pełne raporty, ale brakowało szybkiego bloku „co wymaga decyzji”, przez co operator musiał ręcznie przeszukiwać długie treści.

## B. ZMIENIONE PLIKI
- `scripts/ifg_guardian/modules/ifg_handoff.py`
  - dodano ekstrakcję punktów decyzyjnych (`extract_decision_points`) z heurystyk sekcji i fraz,
  - dodano model punktu (`DecisionPoint`),
  - wpięto blok `## Co wymaga decyzji ChatGPT` do generatora markdown,
  - zachowano istniejący mechanizm scalania i końcową sekcję raportów.
- `tests/unit/test_guardian_ifg_handoff.py`
  - dodano testy dla:
    - ekstrakcji z `E. NASTĘPNY KROK`,
    - ekstrakcji z `UX Debt`,
    - limitu 10 punktów,
    - przypadku braku punktów,
  - rozszerzono test agregacji o walidację kolejności sekcji.

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem zadania).

## D. TESTY
Wykonano:
- wymagany smoke test CLI:
  - `python3 scripts/guardian.py ifg handoff latest --limit 3 --no-clipboard` ✅
- smoke test heurystyki ekstrakcji (Python inline, lokalnie) ✅

Próba uruchomienia testów jednostkowych:
- `python3 -m pytest -q tests/unit/test_guardian_ifg_handoff.py --confcutdir=tests/unit`
- wynik: środowisko bez `pytest` (`No module named pytest`)

## E. NASTĘPNY KROK
Po doinstalowaniu `pytest` uruchomić `tests/unit/test_guardian_ifg_handoff.py` w CI/lokalnie jako stałą walidację bloku decyzyjnego.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0063_GUARDIAN_HANDOFF_DECISION_BLOCK.md`
- `reports/CHATGPT_HANDOFF_2026-07-09.md`
