# GWO-IFG-0058 — MONITOR PROGRESS BAR

**Data:** 2026-07-09  
**Status:** DONE (frontend-only, bez zmian backend/API)

🩷 STATUS KOŃCOWY

✅ Co działa
- Dodano wizualny pasek postępu procesu w zwiniętym wierszu grupy (w kolumnie procesu, pod meta procesu).
- Pasek pokazuje:
  - procent postępu,
  - etykietę (`X/Y etapów`),
  - punkty statusu etapów,
  - semantyczny ton koloru (success/info/warning/danger/neutral).
- Kolory są zgodne z GWO-0055:
  - sukces → zielony,
  - w toku/info → niebieski,
  - ostrzeżenie/retry → pomarańczowy,
  - błąd → czerwony (`danger`),
  - neutralny → szary.
- Dodano `title` z listą etapów i ich statusów (subtelny tooltip natywny bez komplikowania komponentu).
- Pasek nie wpływa na filtry, wyszukiwarkę, polling i stan rozwiniętych grup.

⚠️ Znane problemy
- Postęp jest estymacją opartą na wzorcach operacji i statusach/severity, nie twardym workflow backendowym.

❌ Co nie działa
- Brak regresji funkcjonalnych stwierdzonych testami.

## A. ROOT CAUSE
Operator nie widział, na którym etapie proces jest aktualnie, bez rozwijania szczegółów technicznych. Brakowało szybkiej prezentacji postępu w zwiniętym widoku.

## B. Jak rozpoznawane są etapy
Helper `deriveProcessProgress(group)` działa frontendowo na danych grupy transmisji:

- **Synchronizacja zakupów** (model 5 kroków):
  - sesja,
  - metadata,
  - XML,
  - import,
  - podsumowanie.
- **Wysyłka sprzedaży** (model 5 kroków):
  - przygotowanie,
  - wysyłka,
  - status,
  - UPO,
  - podsumowanie.
- **Inne typy procesów**:
  - model uproszczony: start / przetwarzanie / zakończenie.

Statusy etapów: `done`, `active`, `warning`, `failed`, `pending`, `skipped`.

Ton całego paska:
- `danger` jeśli pojawia się `failed` lub status grupy `error`,
- `warning` przy ostrzeżeniu/retry,
- `info` gdy proces aktywny,
- `success` dla procesu zakończonego sukcesem (100%),
- `neutral` w pozostałych przypadkach.

## C. Gdzie zastosowano fallback
- Dla nierozpoznanych typów procesów używany jest model uproszczony (start/przetwarzanie/zakończenie), aby nie udawać precyzji domenowej.
- Dla skrajnie ubogich danych helper zwraca bezpieczny stan neutralny.

## D. Ryzyko błędnej interpretacji postępu
- Ponieważ backend nie dostarcza jawnego workflow etapów, postęp jest inferowany po `operation_type`, `status`, `severity`.
- W niestandardowych sekwencjach zdarzeń procent może być orientacyjny.
- Ryzyko ograniczone przez:
  - jawny model fallback,
  - ton oparty na bezpiecznych priorytetach (`failed` > `warning` > `active`).

## E. ZMIENIONE PLIKI
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js`
  - `deriveProcessProgress(group)` + pomocnicza logika etapów i tonu.
- `frontend-react/src/components/dashboard/transmissions/TransmissionGroup.jsx`
  - render paska postępu w zwiniętym widoku grupy.
- `frontend-react/src/components/dashboard/transmissions/TransmissionMonitor.module.css`
  - styl paska, wypełnienia, kropek etapów i responsywności.
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - testy postępu (success/running/error/warning + modele purchase/sale/fallback).

## C. DEPLOY
Nie wykonywano deployu (zgodnie z wymaganiem).

## D. TESTY
Uruchomiono:
- `node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - wynik: **42 passed, 0 failed**
- `cd frontend-react && npm run build`
  - wynik: **success**

## E. NASTĘPNY KROK
Opcjonalnie: dopracować mapowanie etapów dla kolejnych niestandardowych `operation_type`, jeśli pojawią się nowe procesy journal KSeF.

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty
- `docs/reports/2026-07-09_GWO-IFG-0058_MONITOR_PROGRESS_BAR.md`
