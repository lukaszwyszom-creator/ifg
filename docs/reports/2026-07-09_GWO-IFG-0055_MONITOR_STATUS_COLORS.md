# GWO-IFG-0055 — MONITOR STATUS COLORS

**Data:** 2026-07-09  
**Status:** DONE (implementacja + testy + build, bez deployu)

🩷 STATUS KOŃCOWY

✅ Co działa
- Wdrożono spójny system tonów kolorystycznych dla Monitora KSeF:
  - sukces → zielony,
  - informacja / running → niebieski,
  - ostrzeżenie / oczekiwanie / retry → pomarańczowy,
  - błąd → czerwony,
  - neutralny → szary.
- Ten sam ton jest używany konsekwentnie dla:
  - ikony procesu (nagłówek grupy + podsumowanie),
  - badge statusu,
  - lewego akcentu grupy (border-left).
- Nie kolorowano całych wierszy tabeli — kolor działa jako akcent.
- Utrzymano kompatybilność UI i responsywność.
- Ujednolicono mapowanie w jednym helperze, bez duplikacji logiki w komponentach.

⚠️ Znane problemy
- Brak nowych problemów funkcjonalnych po zmianie.
- `StatusBadge` jest komponentem współdzielonym, ale w Monitorze KSeF badge jest teraz zasilany ujednoliconym tonem po stronie `TransmissionDetails`.

❌ Co nie działa
- Brak.

## A. ROOT CAUSE
Mapowanie kolorów było rozproszone i niespójne: część elementów opierała się o `status.key`, część o `severity/status`, a ikony etapów miały stały kolor. To utrudniało szybkie skanowanie stanu procesu.

## B. ZMIENIONE PLIKI
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js`
  - dodano wspólny helper mapowania tonu:
    - `mapStatusKeyToTone(key)`
    - `deriveRowStatusTone(row)`
  - dodano zestawy statusów dla warning/info, aby znormalizować semantykę oczekiwania/retry/info.
- `frontend-react/src/components/dashboard/transmissions/TransmissionGroup.jsx`
  - użycie wspólnego tonu (`mapStatusKeyToTone`) do:
    - koloru badge grupy,
    - koloru ikony procesu,
    - klasy lewego akcentu grupy.
- `frontend-react/src/components/dashboard/transmissions/TransmissionSummary.jsx`
  - użycie wspólnego tonu do koloru statusu i ikony procesu.
- `frontend-react/src/components/dashboard/transmissions/TransmissionDetails.jsx`
  - ikona etapu kolorowana tonem z `deriveRowStatusTone`.
  - badge etapu mapowany przez wspólny ton (`toneToBadgeStatus`), aby uniknąć rozjazdu z ikoną.
- `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css`
  - dodano klasy akcentu grup (`groupAccent_*`) i klasy tonu ikon (`iconTone_*`).
  - dodano `status_info` dla spójnego niebieskiego badge.
  - zachowano akcentowy charakter (bez pełnego tła wierszy).
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - dodano testy helpera:
    - `mapStatusKeyToTone mapuje klucz statusu do tonu UX`
    - `deriveRowStatusTone preferuje błąd/ostrzeżenie nad info`

## C. DEPLOY
Nie wykonano deployu (zgodnie z wymaganiem zadania).

## D. TESTY
- Unit tests:
  - `node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - Wynik: **23 passed, 0 failed**
- Build frontendu:
  - `cd frontend-react && npm run build`
  - Wynik: **success** (`vite build` zakończony poprawnie)

## E. NASTĘPNY KROK
Opcjonalnie: dodać wizualny test/regresję screenshotową (np. Playwright) dla tonów statusów na desktop/laptop/tablet, aby łatwo wykrywać przyszłe rozjazdy kolorystyki.

## RYZYKO REGRESJI
- **Niskie/średnie**:
  - zmiana dotyczy głównie warstwy prezentacji (CSS + mapowanie koloru),
  - nie zmienia backendu, modeli ani API,
  - może wpłynąć na odczuwalną semantykę kilku statusów granicznych (np. `running` jako info/niebieski),
  - pokryte testami helpera i buildem.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0055_MONITOR_STATUS_COLORS.md`
