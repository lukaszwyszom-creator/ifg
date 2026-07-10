# GWO-IFG-0063A — GUARDIAN REPORTING STANDARD (DETERMINISTYCZNE DECYZJE)

**Data:** 2026-07-09  
**Status:** DONE (przebudowa handoff + aktualizacja standardu raportów + testy)

🩷 STATUS KOŃCOWY

✅ Co działa
- Workflow `guardian ifg handoff latest` działa teraz deterministycznie:
  - agreguje wyłącznie sekcję `## Decyzje dla ChatGPT` z raportów,
  - nie używa heurystyk i nie zgaduje treści.
- W bloku `## Co wymaga decyzji ChatGPT` handoff generuje grupowanie per raport/GWO:
  - `### GWO-...`
  - lista decyzji z sekcji raportu.
- Dla raportu bez sekcji `## Decyzje dla ChatGPT` wpisywane jest jawnie:
  - `(Raport nie zawiera sekcji "Decyzje dla ChatGPT".)`
- Gdy wszystkie raporty mają `Brak.` w sekcji decyzji:
  - handoff wpisuje: `Brak decyzji wymagających oceny ChatGPT.`
- Zaktualizowano standard raportowania:
  - nowa sekcja `## Decyzje dla ChatGPT` jest obowiązkowa,
  - umieszczana bezpośrednio przed `## Wygenerowane raporty`.
- Zaktualizowano wspólny mechanizm domykania raportów Guardiana (`finish_markdown`) tak, aby dodawał sekcję decyzji (`Brak.` domyślnie).

⚠️ Znane problemy
- W aktualnym środowisku brak modułu `pytest`, więc uruchomienie testów plikowych przez `pytest` nie było możliwe.

❌ Co nie działa
- Brak regresji funkcjonalnych stwierdzonych w smoke testach.

## A. ROOT CAUSE
Heurystyczne wykrywanie punktów decyzyjnych powodowało „zgadywanie” treści raportów i mogło generować fałszywe sygnały. Wymagany był standard deterministyczny oparty wyłącznie na jawnie oznaczonej sekcji autora raportu.

## B. ZMIENIONE PLIKI
- `scripts/ifg_guardian/modules/ifg_handoff.py`
  - usunięto heurystyki bazujące na sekcjach i słowach kluczowych,
  - dodano deterministyczny parser sekcji `## Decyzje dla ChatGPT`,
  - dodano kompatybilność dla starszych raportów (jawny komunikat o braku sekcji),
  - dodano agregację per raport/GWO.
- `tests/unit/test_guardian_ifg_handoff.py`
  - test raportu z decyzjami,
  - test raportu z `Brak.`,
  - test raportu bez sekcji,
  - test agregacji wielu raportów,
  - test zachowania kolejności raportów.
- `scripts/ifg_guardian/core/reporting/debt.py`
  - rozszerzono `finish_markdown` o obowiązkową sekcję `## Decyzje dla ChatGPT`.
- `scripts/ifg_guardian/core/reporting/__init__.py`
  - eksport nowego helpera sekcji decyzji.
- `.cursor/rules/rules_09_reporting.mdc`
  - doprecyzowano obowiązkowy standard raportu z sekcją `## Decyzje dla ChatGPT`.
- `docs/guardian/core/GUARDIAN_REPORT_DEBT_STANDARD.md`
  - zaktualizowano dokumentację standardu raportowania (deterministyczne decyzje ChatGPT).

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem zadania).

## D. TESTY
Wykonano:
- wymagany smoke test CLI:
  - `python3 scripts/guardian.py ifg handoff latest --limit 3 --no-clipboard` ✅
- smoke test parsera sekcji decyzji (lokalny inline Python) ✅
- smoke test `finish_markdown` dla nowego standardu sekcji decyzji ✅

Próba uruchomienia testów plikowych:
- `python3 -m pytest -q tests/unit/test_guardian_ifg_handoff.py --confcutdir=tests/unit`
- wynik: `No module named pytest` (brak narzędzia w środowisku)

## E. NASTĘPNY KROK
Po doinstalowaniu `pytest` uruchomić pełny zestaw testów handoff i raportowania w CI/lokalnie, aby automatycznie egzekwować nowy standard.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0063A_GUARDIAN_REPORTING_STANDARD.md`
- `reports/CHATGPT_HANDOFF_2026-07-09.md`
