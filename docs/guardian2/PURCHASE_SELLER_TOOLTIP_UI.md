# UI — tooltip pełnej nazwy sprzedawcy (lista zakupów)

**Data:** 2026-05-22  
**Komponent:** `InvoiceCardList` — kolumna „Sprzedawca” (`direction=purchase`)

---

## Problem

Długie nazwy sprzedawców były obcinane (ellipsis), bez dostępu do pełnej treści.

## Rozwiązanie

| Plik | Zmiana |
|------|--------|
| `InvoiceCardList.jsx` | `title={contractorName}` na `<span>` kolumny Sprzedawca (tylko purchase, gdy nazwa ≠ `—`) |
| `InvoiceCardList.module.css` | `.purchaseSellerValue` — potwierdzenie ellipsis (jak przy numerze faktury) |

### Strategia

- **Szerokość kolumny:** bez zmian (elastyczna kolumna grid `minmax(..., 1fr)`)
- **Skracanie:** istniejące `overflow: hidden`, `text-overflow: ellipsis`, `white-space: nowrap`
- **Pełna nazwa:** natywny atrybut `title` (ten sam wzorzec co `purchaseNumberValue`)

## Bez zmian

Sortowanie, backend, numery KSeF, pozostałe kolumny — **bez zmian**.

## Test

```bash
node --test --test-name-pattern "pełną nazwę sprzedawcy" \
  frontend-react/src/components/dashboard/dashboardAggregation.test.js
```
