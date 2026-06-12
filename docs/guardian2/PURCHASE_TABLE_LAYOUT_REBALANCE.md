# Rebalans layoutu — lista faktur zakupowych

**Data:** 2026-05-22  
**Komponent:** `InvoiceCardList` (Advanced Dashboard → Faktury zakupowe)

---

## Zmiany

Tylko `InvoiceCardList.module.css` (+ aktualizacja testu regresji).

### Nowe proporcje kolumn (desktop, `noKsef` — Advanced Dashboard)

| Kolumna | Było | Jest | Uwagi |
|---------|------|------|-------|
| Checkbox | 28px | 28px | — |
| Numer | 20ch | **10ch** (−50%) | ellipsis + `title` bez zmian |
| Data | 86px | **82px** | lekka redukcja |
| Sprzedawca | minmax(187px, 1fr) | **minmax(243px, 1.35fr)** (+~30% min) | ellipsis + `title` |
| NIP | 100px | **96px** | — |
| Brutto | 88px | **84px** | — |
| Termin | 80px | **76px** | — |
| Pozostało | 86px | **82px** | — |
| PDF | 136px | **148px** | miejsce na Podgląd + PDF |

Wariant z KSeF (`withCheckbox` bez `noKsef`): analogicznie, Sprzedawca min **218px**, PDF **148px**.

### PDF / overflow

- `.purchaseNumberColumn .invoiceCellPdf` — `min-width: 0`, bez `padding-right` wypychającego treść
- `.pdfActions` — `flex-wrap: nowrap`, `min-width: 0`
- Grid track PDF poszerzony do **148px**

### Nagłówki

- `.purchaseNumberColumn .headerRow .invoiceCellNumber` — `text-align: left` (zgodnie z danymi)
- Nagłówek i wiersze używają tego samego `--invoice-grid-columns` w `.invoiceGrid`

---

## Bez zmian

- Sortowanie purchase: **`issue_date` DESC** (`return b.dateTs - a.dateTs`)
- Numeracja KSeF, backend, API, layout sprzedaży

---

## Weryfikacja manualna (~1500px)

- [ ] Długi numer → ellipsis, pełny w tooltip
- [ ] Długa nazwa sprzedawcy → ellipsis, pełna w tooltip
- [ ] Przyciski Podgląd + PDF w całości widoczne
- [ ] Brak poziomego scrolla
- [ ] Nagłówki nad właściwymi kolumnami

```bash
node --test --test-name-pattern "obcina długi numer|pełną nazwę sprzedawcy" \
  frontend-react/src/components/dashboard/dashboardAggregation.test.js
```
