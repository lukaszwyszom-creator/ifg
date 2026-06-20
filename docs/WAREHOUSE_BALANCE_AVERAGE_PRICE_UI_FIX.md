# Stany magazynowe — poprawka UI średniej ceny netto

**Data:** 2026-06-20  
**Zakres:** Magazyn → Stany (`BalanceTab.jsx`)

## Problem

Po agregacji wielu warstw FIFO UI sugerowało zmianę ceny zakupu:

- widoczny podpis pod nazwą towaru: „3 warstwy FIFO — szczegóły w podpowiedzi”
- kolumna „Cena netto” pokazywała średnią ważoną (np. 31,15 zł) jakby to była cena ostatniego PZ (31,38 zł)

## Zmiany (tylko frontend)

### `BalanceTab.jsx`

1. **Usunięto** widoczny tekst pod nazwą towaru o warstwach FIFO.
2. **Szczegóły warstw** — tylko w `title` (tooltip) na komórce „Towar” przy wielu warstwach.
3. **Nagłówek kolumny:** „Cena netto” → **„Śr. cena netto”** (+ tooltip na nagłówku).
4. **Komórka ceny:** `fmtAvgUnitPrice()` — średnia tylko gdy pełny koszt; przy `cost_pending` → **„koszt nieustalony”** (warstwy bez kosztu nie liczone jako 0 zł).
5. **Tooltip ceny:** „Średnia cena netto = wartość netto / liczba dostępna. Nie zmienia cen zakupu warstw FIFO.” + lista warstw przy wielu warstwach.
6. **Wartość netto** — bez zmian (suma z backendu / agregacji).

### Backend

Nie zmieniany.

## Build

```
cd frontend-react && npm run build
✓ built successfully
```

## UX po zmianie

| Element | Było | Jest |
|---------|------|------|
| Pod nazwą towaru | „N warstw FIFO — szczegóły…” | brak (tylko tooltip) |
| Kolumna ceny | Cena netto | Śr. cena netto |
| Wartość 31,15 zł | wyglądała jak cena zakupu | średnia z tooltipem wyjaśniającym |
| Warstwy bez kosztu | mogły zaniżać średnią | „koszt nieustalony” |
