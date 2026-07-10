# GWO-IFG-0054A — KSEF MONITOR COUNTERPARTY PREVIEW

**Data:** 2026-07-09  
**Status:** DONE (implementacja + testy + build)

🩷 STATUS KOŃCOWY

✅ Co działa
- Dla grupy z dokładnie 1 fakturą i dostępnym `invoice_snapshot` kolumna `Faktury` pokazuje: `FV/... · Kontrahent`.
- Dla grup z wieloma fakturami pozostaje dotychczasowy format (`N faktur`).
- Dla pojedynczej faktury bez `invoice_snapshot` pozostaje dotychczasowy format (sam numer FV).
- Tooltip nadal pokazuje pełne informacje o fakturze (bez zmian regresyjnych).
- Responsywność została zachowana: kontrahent nie rozszerza tabeli (ellipsis na desktop/laptop, zawijanie na małych ekranach zgodnie z istniejącymi regułami).

⚠️ Znane problemy
- Długa nazwa kontrahenta jest skracana wizualnie w kolumnie (`ellipsis`), więc pełna nazwa wymaga hover tooltipa.

❌ Co nie działa
- Brak nowych problemów funkcjonalnych po tej zmianie.

## A. ROOT CAUSE
Operator w zwiniętym wierszu procesu widział sam numer FV, bez szybkiej informacji „czyja to faktura”. To wymuszało rozwijanie grupy lub hover, co spowalniało skanowanie listy.

## B. ZMIENIONE PLIKI
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.js`
  - Dodano flagę `hasSnapshot` w snapshotach faktur.
  - Zaktualizowano merge deduplikacji (`extractInvoicesFromRows`) dla `hasSnapshot`.
  - Rozszerzono `invoicesSummaryLabel()`:
    - `1 faktura + hasSnapshot + counterparty` => `numer · kontrahent`.
    - w pozostałych przypadkach zachowane dotychczasowe zachowanie.
- `frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - Dodano test dla podglądu `numer · kontrahent` przy pojedynczej FV z `invoice_snapshot`.
  - Dodano test regresyjny: pojedyncza FV bez `invoice_snapshot` nadal pokazuje sam numer.

## C. DEPLOY
Nie wykonywano deployu w ramach GWO-IFG-0054A.

## D. TESTY
- Unit tests:
  - `node --test frontend-react/src/components/dashboard/transmissions/transmissionUtils.test.js`
  - Wynik: **21 passed, 0 failed**
- Build:
  - `cd frontend-react && npm run build`
  - Wynik: **success** (`vite build` zakończony poprawnie)

## E. NASTĘPNY KROK
Opcjonalnie: dodać `title`/`aria-label` z pełną wartością `numer · kontrahent` bezpośrednio w komórce kolumny `Faktury`, żeby pełna nazwa była dostępna także bez tooltipa.

## UX Debt
- **LOW — pełna nazwa kontrahenta w komórce bez hover**  
  Opis: Obecnie pełna nazwa jest dostępna praktycznie przez tooltip; przy skróceniu ellipsis w kolumnie użytkownik widzi tylko część tekstu.  
  Wartość: szybszy odczyt przy długich nazwach i mniejsza liczba hoverów.  
  Uzasadnienie odłożenia: poza zakresem tej mikro-poprawki (GWO-IFG-0054A skupia się na warunku wyświetlania `numer · kontrahent`, nie na nowej interakcji w tabeli).
