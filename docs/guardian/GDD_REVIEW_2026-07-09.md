# GDD REVIEW 2026-07-09

**Projekt:** IFG
**Otwarte wpisy:** 9

## GDD-0001 — Guardian Handoff

- **Typ:** Process
- **Priorytet:** High
- **Status:** OPEN
- **Powód odłożenia:** Poprawka parsera wymaga osobnego, deterministycznego zakresu testów handoff bez ryzyka regresji w bieżącym release Monitora.
- **Opis:** Parser sekcji "Decyzje dla ChatGPT" w handoff kończy ekstrakcję zbyt późno i wciąga linie spoza sekcji (np. A. ROOT CAUSE), gdy raport nie używa list punktowanych.
- **Kiedy wrócić:** Przed kolejnym cyklem raportowania GWO / przy pracy nad GWO-IFG-0063 follow-up.
- **Źródło:** GWO-IFG-0059 review + analiza CHATGPT_HANDOFF_2026-07-09.md
- **Utworzono:** 2026-07-09

## GDD-0007 — KSeF Monitor / API

- **Typ:** Architecture
- **Priorytet:** High
- **Status:** OPEN
- **Powód odłożenia:** Wymaga zmiany kontraktu API i synchronizacji semantyki statusów między workerem, journalem i UI.
- **Opis:** Agregować process_status po stronie backendu zamiast wyliczać końcowy status procesu w frontendzie (aggregateGroupStatus).
- **Kiedy wrócić:** Przy planowaniu kolejnej iteracji KSeF Monitor backend-first lub integracji mobile/API.
- **Źródło:** GUARDIAN_REPORT_DEBT_STANDARD + GWO-IFG-0053 (Technical/Architecture Debt)
- **Utworzono:** 2026-07-09

## GDD-0002 — KSeF Monitor

- **Typ:** Refactor
- **Priorytet:** Medium
- **Status:** OPEN
- **Powód odłożenia:** Moduł jest stabilny po GWO-0053..0058; rozdzielenie pliku teraz zwiększyłoby ryzyko regresji bez nowej funkcjonalności.
- **Opis:** Rozbić transmissionUtils.js na mniejsze moduły (statusy, faktury, filtr/wyszukiwarka, progress) przy kolejnym większym rozwoju Monitora KSeF.
- **Kiedy wrócić:** Przy pierwszym GWO rozszerzającym Monitor poza utrzymanie (nowy widok, backend grouping lub nowe typy procesów).
- **Źródło:** GWO-IFG-0059_MONITOR_RELEASE_REVIEW.md
- **Utworzono:** 2026-07-09

## GDD-0005 — KSeF Monitor

- **Typ:** Technical Debt
- **Priorytet:** Medium
- **Status:** OPEN
- **Powód odłożenia:** Progress bar jest estymacją frontendową wystarczającą na obecnym etapie; backend nie dostarcza jeszcze jawnego workflow etapów.
- **Opis:** Dopracować mapowanie operation_type i modeli etapów progress bara (purchase/sale/generic) wraz z backendową semantyką statusów procesu.
- **Kiedy wrócić:** Przy rozszerzaniu Monitora o nowe typy operacji KSeF lub po wprowadzeniu backendowego process_status.
- **Źródło:** GWO-IFG-0058_MONITOR_PROGRESS_BAR.md
- **Utworzono:** 2026-07-09

## GDD-0006 — Frontend

- **Typ:** Performance
- **Priorytet:** Medium
- **Status:** OPEN
- **Powód odłożenia:** Ostrzeżenie Vite nie blokuje release Monitora KSeF; optymalizacja bundla dotyczy całej aplikacji frontendowej.
- **Opis:** Optymalizacja bundle frontendu (obecnie ~898 kB głównego chunku JS) poprzez code-splitting i manualChunks.
- **Kiedy wrócić:** Przy kolejnym większym deployu frontendu lub gdy metryki ładowania UI staną się problemem operatorskim.
- **Źródło:** GWO-IFG-0059_MONITOR_RELEASE_REVIEW.md (vite build warning)
- **Utworzono:** 2026-07-09

## GDD-0009 — Guardian Reporting

- **Typ:** Process
- **Priorytet:** Medium
- **Status:** OPEN
- **Powód odłożenia:** Debt w raportach GWO jest obecnie dokumentowany lokalnie; centralny rejestr dopiero powstaje wraz z GDD.
- **Opis:** Ustalić workflow promowania wpisów z sekcji Debt raportów GWO do rejestru GDD (kiedy i kto tworzy wpis OPEN).
- **Kiedy wrócić:** Po pierwszym użyciu `guardian deferred review` w cyklu release.
- **Źródło:** GWO-GUARDIAN-STANDARD + GWO-GUARDIAN-GDD_CORE
- **Utworzono:** 2026-07-09

## GDD-0003 — KSeF Monitor

- **Typ:** Performance
- **Priorytet:** Low
- **Status:** OPEN
- **Powód odłożenia:** Obecna skala danych i lokalny pipeline filter/search są wystarczające po review release.
- **Opis:** Rozważyć backendowe filtrowanie i grupowanie transmisji przy bardzo dużej liczbie rekordów zamiast pełnego przetwarzania po stronie frontendu.
- **Kiedy wrócić:** Gdy lista transmisji przekroczy praktyczny limit UX (np. >500 rekordów na stronę lub zauważalne opóźnienia interakcji).
- **Źródło:** GWO-IFG-0056/0057/0059 + GUARDIAN_REPORT_DEBT_STANDARD (Performance Debt)
- **Utworzono:** 2026-07-09

## GDD-0004 — KSeF Monitor

- **Typ:** UX
- **Priorytet:** Low
- **Status:** OPEN
- **Powód odłożenia:** Wyszukiwarka działa poprawnie; highlight to usprawnienie czytelności, nie wymóg release.
- **Opis:** Rozważyć podświetlanie dopasowanego fragmentu (highlight) w tytule procesu i kolumnie faktur podczas aktywnego wyszukiwania.
- **Kiedy wrócić:** Jeżeli operatorzy zgłoszą potrzebę szybszej identyfikacji trafienia w długich listach.
- **Źródło:** GWO-IFG-0057_MONITOR_SEARCH.md (E. Następny krok)
- **Utworzono:** 2026-07-09

## GDD-0008 — KSeF Monitor

- **Typ:** UX
- **Priorytet:** Low
- **Status:** OPEN
- **Powód odłożenia:** GWO-IFG-0054A dostarczył warunek wyświetlania numer · kontrahent; pełna nazwa bez hover nie była celem tej iteracji.
- **Opis:** Umożliwić odczyt pełnej nazwy kontrahenta w kolumnie Faktury bez konieczności hover (np. rozwijany wiersz lub druga linia przy długich nazwach).
- **Kiedy wrócić:** Jeżeli operatorzy zgłoszą problem z czytelnością skróconych nazw mimo tooltipu.
- **Źródło:** GWO-IFG-0054A_KSEF_MONITOR_COUNTERPARTY_PREVIEW.md (UX Debt)
- **Utworzono:** 2026-07-09

