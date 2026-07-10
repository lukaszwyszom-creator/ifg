# Stany magazynowe — poprawka „koszt nieustalony” vs wartość netto

**Data:** 2026-06-20  
**Plik:** `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx`

## Problem

Po poprzedniej poprawce UI pokazywało jednocześnie:

- wartość netto **62 760,00 zł**
- w kolumnie ceny tekst **„koszt nieustalony”**

To było sprzeczne — średnia da się policzyć z `value_net / quantity_available`, nawet gdy część warstw FIFO ma `cost_pending`.

## Przyczyna

`fmtAvgUnitPrice()` i agregacja blokowały średnią przy `has_cost_pending === true`, zamiast pokazać wyliczoną średnią i ostrzec tylko w tooltipie.

## Poprawka (tylko frontend)

1. **Średnia cena:** liczona zawsze gdy `quantity_available > 0` i `value_net > 0` — bez warunku `!has_cost_pending`.
2. **Komórka ceny:** pokazuje `value_net / quantity_available` (np. 31,15 zł), nie „koszt nieustalony”.
3. **Tooltip:** ostrzeżenie o warstwach bez kosztu + lista warstw (przy wielu warstwach lub gdy `cost_pending`).
4. **„koszt nieustalony”:** tylko gdy nie da się policzyć średniej (`unit_price_net == null`) i są warstwy pending (np. cały stan bez ustalonej wartości).

## Backend

Bez zmian.

## Build

```
cd frontend-react && npm run build
✓ built successfully
```
