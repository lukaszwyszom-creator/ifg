# GWO-IFG-0056 — MONITOR KSEF FILTERS

**Data:** 2026-07-09  
**Status:** DONE (frontend-only, bez zmian backend/API)

🩷 STATUS KOŃCOWY

✅ Co działa
- Dodano pasek filtrów nad tabelą Monitora KSeF:
  - Wszystkie
  - Sprzedaż
  - Zakupy
  - Aktywne
  - Błędy
  - Zakończone
- Domyślnie aktywny filtr: `Wszystkie`.
- Filtrowanie działa lokalnie na już pobranych danych (`groupTransmissions(data.items)`), bez dodatkowych requestów HTTP.
- Zmiana filtra natychmiast odświeża widok.
- Stan rozwiniętych grup nie jest resetowany (klucze grup pozostają stabilne, filtr tylko ogranicza widok).
- Filtrowanie nie wpływa na polling/auto-refresh.
- Dodano przyjazny komunikat dla braku wyników:
  - `Brak transmisji spełniających wybrane kryteria.`
- UI filtrów działa jako spójne toggle/chipy z wyraźnym stanem aktywnym i poprawnym zachowaniem responsywnym (wrap bez skakania układu).

⚠️ Znane problemy
- Brak nowych problemów funkcjonalnych po zmianie.

❌ Co nie działa
- Brak.

## A. ROOT CAUSE
Operator nie miał szybkiego sposobu lokalnego zawężenia listy procesów, co wymuszało ręczne skanowanie pełnej tabeli i spowalniało reakcję na błędy/aktywne procesy.

## B. ZMIENIONE PLIKI
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
  - dodano stan aktywnego filtra,
  - dodano pasek przycisków filtrów,
  - dodano `filteredGroups` (lokalne filtrowanie),
  - usunięto zależność od serwerowego `warningsOnly` w zapytaniu listy.
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js`
  - dodano `MONITOR_FILTERS`,
  - dodano `groupMatchesFilter(group, filterKey)` jako wspólny helper logiki filtrów.
- `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css`
  - style paska filtrów i chipów (`filtersBar`, `filterChip`, `filterChipActive`) z responsywnym zawijaniem.
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - rozszerzono testy o przypadki dla wszystkich filtrów,
  - dodano test przypadku bez wyników.

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem zadania).

## D. TESTY
Uruchomiono:
- `node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - wynik: **29 passed, 0 failed**
- `cd frontend-react && npm run build`
  - wynik: **success**

## E. NASTĘPNY KROK
Opcjonalnie można dodać zapamiętywanie ostatniego filtra w `localStorage`, aby operator wracał do preferowanego widoku po odświeżeniu strony.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0056_MONITOR_FILTERS.md`
