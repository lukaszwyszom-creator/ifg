# GWO-IFG-0057 — MONITOR KSEF SEARCH

**Data:** 2026-07-09  
**Status:** DONE (frontend-only, bez zmian backend/API)

🩷 STATUS KOŃCOWY

✅ Co działa
- Dodano wyszukiwarkę Monitora KSeF nad tabelą, spójną z panelem filtrów.
- Placeholder ustawiony zgodnie z wymaganiem:
  - `🔍 Numer FV / kontrahent / KSeF / ID`
- Wyszukiwanie działa lokalnie, bez requestów HTTP i bez debounce.
- Tryb działania:
  - case-insensitive,
  - częściowe dopasowanie (`contains`),
  - aktualizacja wyników podczas wpisywania,
  - bez przycisku „Szukaj”.
- Zakres wyszukiwania obejmuje:
  - numer FV,
  - kontrahenta,
  - numer KSeF,
  - identyfikator transmisji,
  - `correlation_id`,
  - `job_id`,
  - tytuł procesu.
- Dodano przycisk czyszczenia `×` widoczny po wpisaniu tekstu.
- Po wyczyszczeniu focus wraca do pola wyszukiwania.
- Wyszukiwanie działa razem z filtrami z GWO-0056 w jednym pipeline:
  - `data -> filter -> search -> render`.
- Komunikaty empty-state:
  - przy aktywnym wyszukiwaniu: `Brak transmisji pasujących do wyszukiwania.`
  - przy samym filtrze: `Brak transmisji spełniających wybrane kryteria.`

⚠️ Znane problemy
- Brak nowych problemów funkcjonalnych po zmianie.

❌ Co nie działa
- Brak.

## A. ROOT CAUSE
Brak wyszukiwarki wymuszał ręczne przeglądanie listy procesów i wydłużał czas odnajdywania konkretnej transmisji/faktury.

## B. ZMIENIONE PLIKI
- `frontend-react/src/components/dashboard/TransmissionTable.jsx`
  - dodano pole wyszukiwania, stan `searchQuery`, przycisk czyszczenia i zarządzanie focusem,
  - podłączono wyszukiwanie do wspólnego pipeline renderowania.
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js`
  - dodano `groupMatchesSearch(group, query)`,
  - dodano `filterAndSearchGroups(groups, filterKey, query)`,
  - logika przeszukiwania pola i metadanych grupy/procesu/faktur.
- `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css`
  - dodano styl panelu wyszukiwania (`searchBar`, `searchInput`, `searchClear`, `searchIcon`).
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - rozszerzono testy o przypadki wyszukiwania i współpracy z filtrami.

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem).

## D. TESTY
Uruchomiono:
- `node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - wynik: **35 passed, 0 failed**
- `cd frontend-react && npm run build`
  - wynik: **success**

## E. NASTĘPNY KROK
Opcjonalnie: podświetlanie dopasowanego fragmentu (highlight) w tytule procesu/kolumnie faktur, jeśli operatorzy zgłoszą taką potrzebę.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0057_MONITOR_SEARCH.md`
