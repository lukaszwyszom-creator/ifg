# PZ / kartoteka / FV — cena normatywna brutto

## Cel

Dopięcie PZ i kartoteki bez pełnego Magazyn V1: poprawne kolumny tabeli PZ, zapis VAT i ceny normatywnej brutto, podstawianie na FV sprzedaży.

## Zmiany

### `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`

- Tabela pozycji PZ: nagłówki `ILOŚĆ`, `CENA ZAKUPU (NETTO)`, `STAWKA VAT`, `NORMATYWNA CENA SPRZEDAŻY BRUTTO`.
- Ilość — liczba całkowita (`step=1`, sanitizacja).
- Ceny — 2 miejsca po przecinku w podglądzie (`fmtMoney2`).
- Wyrównanie liczb do prawej, `colgroup` + klasy CSS.
- Wybór towaru — podpowiedź `vat_rate` i `suggested_sale_price` z kartoteki.
- Podgląd dokumentu PZ — te same kolumny.

### `frontend-react/src/pages/warehouse/WarehousePage.module.css`

- Style `.pzItemsTable`, `.numCell`, `.numInput`, szerokości kolumn.

### `frontend-react/src/components/invoice/InvoiceForm.jsx`

- `catalogItemToLineFields()`: `suggested_sale_price` → `price_mode: 'gross'` + `unit_price_gross`; fallback `default_price_net` jako netto; `vat_rate` z kartoteki.

### `frontend-react/src/api/warehouseItems.js`

- Komentarz semantyki `suggested_sale_price` (brutto z PZ).

## Bez zmian

- Backend, endpointy, migracje.
- Pełny Magazyn V1 (WZ/KK/Stany/raporty) — bez rozszerzeń.

## Testy

```bash
pytest tests/unit/test_warehouse_items.py -q
cd frontend-react && npm run build
```

## Ryzyka

- Istniejące dane w `suggested_sale_price` zapisane wcześniej jako netto będą traktowane jako brutto na FV — wymaga weryfikacji danych po pierwszym PZ.
- Wąska kolumna „NORMATYWNA CENA…” na małych ekranach — może wymagać przewijania poziomego.
