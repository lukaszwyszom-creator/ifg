# GWO-IFG-0064 — GUARDIAN HANDOFF PENDING

**Data:** 2026-07-09  
**Status:** DONE (handoff pending + stan trwały + opcje CLI + testy)

🩷 STATUS KOŃCOWY

✅ Co działa
- Dodano trwały stan handoff w pliku:
  - `.state/handoff.json`
- `guardian ifg handoff latest` zmieniło semantykę na **pending**:
  - domyślnie przekazuje tylko raporty jeszcze nieprzekazane.
- Dodano opcję `--all`:
  - ignoruje stan i przekazuje wszystkie raporty zgodnie z dotychczasową logiką selekcji.
- Dodano opcję `--reset`:
  - czyści pamięć handoff przed selekcją raportów.
- Po poprawnym wygenerowaniu handoff stan jest aktualizowany (raporty oznaczane jako przekazane).
- Przy błędzie generacji stan nie jest zmieniany (zachowana kolejność operacji: generacja → zapis stanu).
- Gdy brak nowych raportów tworzony jest krótki handoff bez pustych sekcji:
  - `# CHATGPT HANDOFF`
  - `Brak nowych raportów do przekazania.`
- Nie zmieniono parsera sekcji `Decyzje dla ChatGPT` ani standardu raportowania.

⚠️ Znane problemy
- W bieżącym środowisku brak modułu `pytest`, więc testy plikowe nie mogły być uruchomione przez `python3 -m pytest`.

❌ Co nie działa
- Brak regresji funkcjonalnych stwierdzonych w smoke testach.

## A. ROOT CAUSE
Bez pamięci stanu te same raporty były przekazywane wielokrotnie. Potrzebna była trwała semantyka „pending”, odporna na restart programu.

## B. ZMIENIONE PLIKI
- `scripts/ifg_guardian/modules/ifg_handoff.py`
  - dodano obsługę stanu `.state/handoff.json` (load/save/reset),
  - domyślna selekcja raportów oparta o nieprzekazane pozycje,
  - wsparcie `include_all` i `reset_state`,
  - krótki handoff dla przypadku braku nowych raportów.
- `scripts/ifg_guardian/cli.py`
  - rozszerzono `guardian ifg handoff latest` o:
    - `--all`,
    - `--reset`.
- `tests/unit/test_guardian_ifg_handoff.py`
  - dodano testy dla:
    - pierwszego handoff,
    - drugiego handoff bez nowych raportów,
    - pojawienia się nowego raportu,
    - opcji `--all`,
    - opcji `--reset`,
    - odporności na uszkodzony plik stanu,
    - dispatch CLI z nowymi argumentami.

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem zadania).

## D. TESTY
Wykonano:
- smoke test CLI:
  - `python3 scripts/guardian.py ifg handoff latest --limit 3 --no-clipboard` ✅
- smoke test scenariuszy pending/all/reset/uszkodzony stan (inline Python) ✅

Próba uruchomienia testów jednostkowych plikowych:
- `python3 -m pytest -q tests/unit/test_guardian_ifg_handoff.py --confcutdir=tests/unit`
- wynik: `No module named pytest` (brak narzędzia w środowisku)

## E. NASTĘPNY KROK
Po doinstalowaniu `pytest` uruchomić `tests/unit/test_guardian_ifg_handoff.py` w CI/lokalnie jako stały test regresji workflow handoff pending.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0064_GUARDIAN_HANDOFF_PENDING.md`
- `reports/CHATGPT_HANDOFF_2026-07-09.md`
