# Fix: widok szczegółu dokumentu WZ

**Data:** 2026-06-19

## Zmiany

### `DocumentsTab.jsx` — `DocDetail`

- **PZ (bez zmian układu):** TOWAR | ILOŚĆ | CENA ZAKUPU (NETTO) | STAWKA VAT | NORMATYWNA CENA SPRZEDAŻY BRUTTO
- **WZ:** TOWAR | ILOŚĆ | CENA SPRZEDAŻY BRUTTO — usunięto kolumnę ceny zakupu
- **Ilość:** `fmtIntegerQty()` dla PZ/WZ/KK w podglądzie (bez `1.0000`)
- **Wyrównanie:** `numCell` + `colgroup` dla WZ (jak PZ)
- **Cena sprzedaży brutto WZ:** `wzSalePriceGross()` — kartoteka (`suggested_sale_price` + mode), pozycja dokumentu, fallback `unit_price_net` → brutto z VAT
- **Nagłówek WZ:** etykieta „Powód wydania” gdy jest `issue_reason`

### `WarehousePage.module.css`

- Style `.wzItemsTable`, `.colWzProduct`, `.colWzQty`, `.colWzGross`

## Build

```bash
cd frontend-react && npm run build
# ✓ built
```

## Ryzyka

- Cena brutto WZ bez danych na pozycji dokumentu jest **wyliczana w UI** z kartoteki lub netto + VAT — backend nie zwraca osobnego pola brutto na WZ.
- WZ powiązany z FV może mieć tylko `unit_price_net` — wyświetlamy przeliczoną brutto (zaokrąglenie 2 miejsc).
- KK pozostaje bez zmian układu kolumn (poza formatowaniem ilości).
