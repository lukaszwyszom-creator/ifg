# Fix: agregacja stanów magazynowych po towarze

**Data:** 2026-06-19  
**Plik:** `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx`

## Agregacja frontendowa

**Tak** — API `/warehouse/items/balance` zwraca warstwy z polami:
`item_id`, `name`, `isbn`, `quantity_available`, `unit_price_net`, `vat_rate`, `value_net`, `source_document_*`, `layer_id`.

## Zmiany

- `aggregateBalanceByItem()` — grupowanie po `item_id`.
- **Liczba dostępna** = suma `quantity_available` warstw.
- **Wartość netto** = suma `value_net` (lub qty × cena).
- **Cena netto** = średnia ważona (`value_net / quantity_available`).
- Usunięto kolumny dokument źródłowy / data z głównej tabeli.
- Źródła warstw (PZ/KK) w `title` wiersza + podpowiedź przy wielu warstwach.
- Inwentaryzacja PDF — wiersze po towarze (bez „dostawa I/II”).

## Build

```bash
cd frontend-react && npm run build
# ✓ built
```

## Ryzyka

- Różne stawki VAT między warstwami tego samego towaru — wyświetlany VAT z pierwszej warstwy.
- Tooltip (`title`) ma ograniczoną czytelność na mobile.
- Brak `item_id` w odpowiedzi → komunikat błędu zamiast listy.
