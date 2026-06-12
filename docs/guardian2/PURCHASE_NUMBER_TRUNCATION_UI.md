# UI — skracanie długich numerów faktur zakupowych

**Data:** 2026-05-22  
**Komponent:** `InvoiceCardList` (zakładka Faktury zakupowe)

---

## Problem

Po fixie numeracji KSeF długie numery dostawców (`number_local` / P_2) nachodziły na kolumnę „Data”.

## Rozwiązanie

| Element | Zmiana |
|---------|--------|
| `InvoiceCardList.module.css` | Klasa `.purchaseNumberColumn` — kolumna Numer w gridzie: `20ch`; `.purchaseNumberValue` — ellipsis |
| `InvoiceCardList.jsx` | Klasy tylko dla `direction=purchase`; `title={pełny numer}` na `<span>` |

### Strategia skracania

- **Szerokość:** `20ch` (~20 znaków monospace-width; w praktyce 18–22 znaki przy `0.85rem`)
- **CSS:** `white-space: nowrap`, `overflow: hidden`, `text-overflow: ellipsis`
- **Pełny numer:** natywny tooltip `title` (bez nowego komponentu — projekt używa `title` w tym module)
- **Bez** `substring` w JS

## Bez zmian

- Sortowanie purchase: `issue_date` malejąco (`return b.dateTs - a.dateTs`) — **bez zmian**
- `displayNumber`, numeracja KSeF, backend — **bez zmian**
- Layout sprzedaży — **bez zmian**

## Test

`frontend-react/src/components/dashboard/dashboardAggregation.test.js` — regresja klas/CSS ellipsis.

```bash
node --test --test-name-pattern "obcina długi numer" \
  frontend-react/src/components/dashboard/dashboardAggregation.test.js
```
