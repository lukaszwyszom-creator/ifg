# Fix: UI dokumentu KK — formularz i podgląd

**Data:** 2026-06-19

## Zmiany

### Formularz (`DocForm`)

- Pod polem ilości: podpowiedź zależna od znaku (`kkQuantityDirectionHint`).
- Usunięto kolumnę „Cena suger.” — tylko Ilość + Cena zakupu.
- Style `.kkItemsTable`, `colgroup`, `numCell` / `numInput`.

### Podgląd (`DocDetail`)

- Kolumny KK: **TOWAR | ILOŚĆ | CENA ZAKUPU** (bez ceny sprzedaży).
- `fmtIntegerQty`, `fmtMoney2`, wyrównanie `numCell`.
- `detailItemColSpan('KK')` → 3.

### CSS

- `WarehousePage.module.css`: `.kkItemsTable`, szerokości kolumn.

## Build

```bash
cd frontend-react && npm run build
# ✓ built
```

## Ryzyka

- Podpowiedź kierunku korekty znika przy ilości 0 lub pustej — zgodnie z logiką backendu.
- Ujemna korekta bez ceny zakupu w formularzu nadal pokazuje „n/d” (bez zmian walidacji).
