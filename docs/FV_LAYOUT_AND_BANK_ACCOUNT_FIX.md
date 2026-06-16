# FV layout i rachunek bankowy — raport

Data: 2026-05-22

## Cel

Poprawa danych i układu faktury sprzedaży (HTML/PDF + formularz) oraz dodanie numeru rachunku bankowego sprzedawcy w ustawieniach firmy.

## Zmiany

### Backend

| Obszar | Plik | Opis |
|--------|------|------|
| Rachunek bankowy | `app/services/bank_account.py` | Normalizacja (26 cyfr), walidacja, format prezentacji `XX XXXX XXXX XXXX XXXX XXXX XXXX` |
| DB | `alembic/versions/e2f3a4b5c6d7_add_seller_bank_account.py` | Kolumna `seller_bank_account VARCHAR(26)` w `app_settings` |
| Model | `app/persistence/models/app_settings.py` | Pole `seller_bank_account` |
| Ustawienia | `app/services/settings_service.py`, `app/schemas/settings.py` | Walidacja przy zapisie, zwracanie w GET/PUT |
| HTML/PDF | `app/services/pdf_service.py` | Kolumna „Cena brutto”, ilość bez miejsc dziesiętnych, VAT jako `5%`, linia „Rachunek bankowy: …” |
| API faktur | `app/api/routers/invoices.py` | Podgląd/PDF pobierają `seller_bank_account` z `SettingsService` |

### Frontend

| Obszar | Plik | Opis |
|--------|------|------|
| Ustawienia | `frontend-react/src/pages/settings/CompanySettingsPage.jsx` | Nowa strona „Ustawienia firmy” z polem „Rachunek bankowy” |
| Routing | `frontend-react/src/App.jsx`, `Sidebar.jsx` | Trasa `/settings`, link w menu |
| Formularz FV | `InvoiceForm.jsx`, `InvoiceForm.module.css` | Kolumny cena netto + cena brutto, ilość całkowita (`step=1`), VAT jako `5%` / `23%` |

### Testy

| Plik | Zakres |
|------|--------|
| `tests/unit/test_bank_account.py` | Normalizacja, walidacja, format wyświetlania |
| `tests/unit/test_settings_bank_account.py` | Zapis przez `SettingsService` |
| `tests/unit/test_pdf_service.py` | HTML: rachunek, ilość, VAT, cena brutto |
| `tests/unit/test_invoice_totals.py` | Regresja 120×60×5%, ilości całkowite |

Wynik: **37 passed** (nowe + istniejące w zakresie).

Frontend build: **`npm run build` OK**.

## Wymagania vs implementacja

1. **Rachunek bankowy** — zapis jako 26 cyfr; wpis ze spacjami akceptowany; błąd przy niepoprawnej długości/znakach; na fakturze `Rachunek bankowy: 12 3456 7890 …`.
2. **Formularz ustawień** — `/ui/settings` → pole „Rachunek bankowy”.
3. **Ilość** — tylko liczby całkowite w formularzu i na HTML/PDF.
4. **VAT** — prezentacja `0%`, `5%`, `23%` (bez `.00`).
5. **Cena brutto** — kolumna w tabeli; netto: `unit_net × (1+VAT)`; brutto: wpisana cena.
6. **Kalkulacje** — bez regresji: brutto 7200,00 / netto 6857,14 / VAT 342,86 dla 120×60×5%.
7. **Testy regresyjne** — pokryte w plikach powyżej.

## Wdrożenie

1. Migracja Alembic na produkcji (po `pg_dump`):
   ```bash
   alembic upgrade head
   ```
2. W UI: **Ustawienia firmy** → wpisać rachunek Ikony → Zapisz.
3. Podgląd/PDF faktury sprzedaży powinien pokazać sformatowany numer.

## Ryzyka

- **Migracja DB** — wymaga `alembic upgrade head` przed użyciem pola; bez migracji zapis ustawień może się nie powieść.
- **Dane sprzedawcy z env** — pola NIP/nazwa/adres mogą pochodzić ze zmiennych środowiskowych (priorytet nad DB); rachunek bankowy jest **tylko w DB**.
- **Brak rachunku** — faktura renderuje się poprawnie, ale bez linii „Rachunek bankowy” (celowe — brak hardcodu).
- **Szeroka tabela pozycji** — dodatkowa kolumna „Cena brutto” na wąskich ekranach może wymagać przewijania poziomego (mobile: układ pionowy bez nagłówka kolumn).
