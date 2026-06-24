# Purchase PDF bank account fix (2026-06-24)

## Problem

Podgląd/PDF faktury **zakupu** pokazywał rachunek bankowy Ikony (ustawienia firmy) w sekcji Sprzedawca.

## Zmiana

- `resolve_seller_bank_account_for_render()` w `pdf_service.py`
- `direction=purchase` → tylko `seller_snapshot.bank_account` (lub aliasy), bez fallbacku do ustawień
- `direction=sale` → rachunek z ustawień firmy (bez zmian)

## Commit

_(po commit)_

## Deploy

Backend api — bez zmian frontend-react.

## Weryfikacja

- `pytest tests/unit/test_pdf_service.py` — 9 passed
- Prod: podgląd/PDF faktury zakupu bez linii „Rachunek bankowy” (gdy brak konta w snapshot)
