# KSeF — numer faktury zakupowej w liście

## Problem

W zestawieniu faktur zakupu z KSeF pierwsza kolumna pokazywała fikcyjne numery w formacie IFG (`NN/MM/RRRR`), generowane w UI, gdy `number_local` z XML nie pasował do wzorca numeracji sprzedaży.

## Przyczyna

1. **Import KSeF** (`ksef_session_service.sync_received_invoices`) zapisuje numer wystawcy z pola XML `P_2` do kolumny `number_local` — to poprawne źródło danych.
2. **`InvoiceCardList`** dla wszystkich kierunków próbował sparsować `number_local` jako numer IFG; przy braku dopasowania nadawał tymczasową sekwencję (`ui:temporary_sequence`) i wyświetlał np. `01/05/2026`.
3. **`mark_as_ready`** mógł nadać numer IFG także fakturze `direction=purchase` bez numeru (ścieżka obronna, poza typowym importem KSeF).

## Zmiany

| Warstwa | Plik | Zmiana |
|---------|------|--------|
| Frontend | `InvoiceCardList.jsx` | Dla `direction=purchase`: wyświetlanie surowego `number_local` (P_2) lub „brak numeru”; sortowanie po `issue_date` malejąco; bez sekwencji IFG |
| Backend | `invoice_service.py` | `mark_as_ready` nie wywołuje `_assign_number_local` dla faktur zakupowych |
| Testy | `test_ksef_sync_service.py`, `test_ksef_xml_parser.py`, `test_invoice_service.py`, `dashboardAggregation.test.js` | Regresja numeru z XML i braku numeracji IFG dla purchase |

## Zachowanie po fixie

- **Zakup / KSeF:** kolumna „Numer” = wartość `P_2` z XML (pole `number_local` w API); brak wartości → „brak numeru”.
- **Sprzedaż:** bez zmian — dotychczasowa numeracja IFG w UI i backendzie.
- **Sortowanie zakupów:** po dacie wystawienia (`issue_date`), malejąco.

## Ryzyko

- Istniejące rekordy zakupowe z błędnymi numerami IFG w bazie (jeśli kiedyś trafiły przez `mark_as_ready`) nadal będą miały te wartości w `number_local` — fix nie migruje danych historycznych.
- Wyszukiwanie po numerze w API (`number_filter`) nadal przeszukuje `number_local`; dla zakupów to numer dostawcy, nie KSeF reference.

## Weryfikacja

```bash
pytest tests/unit/test_ksef_sync_service.py tests/unit/test_ksef_xml_parser.py tests/unit/test_invoice_service.py -q
node --test frontend-react/src/components/dashboard/dashboardAggregation.test.js
```
