# Stany magazynowe — grupowanie po cenie zakupu netto

**Data:** 2026-06-20  
**Plik:** `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx`

## Problem biznesowy

Uśrednianie ceny zakupu dla tego samego towaru zaburzało inwentaryzację i rozliczenia roczne. UI pokazywało średnią (np. 31,15 zł) zamiast rzeczywistych cen warstw FIFO.

## API — wystarczył frontend

`GET /warehouse/items/balance` zwraca **jedną pozycję na warstwę FIFO** z polami:

- `item_id`, `name`, `isbn`
- `quantity_available` (remaining_quantity warstwy)
- `unit_price_net` (= `purchase_unit_price` warstwy)
- `cost_pending` (gdy `unit_price_net === null`)
- `value_net` (= qty × cena, lub null)

Backend **nie wymagał zmian**.

## Nowa agregacja UI

Klucz grupowania: `item_id` + `unit_price_net` (osobny bucket `pending` dla kosztu nieustalonego).

| Reguła | Zachowanie |
|--------|------------|
| Ten sam towar + ta sama cena | suma ilości w jednym wierszu |
| Ten sam towar + inna cena | osobny wiersz |
| Brak ceny zakupu | osobny wiersz „koszt nieustalony”, wartość netto „—” |
| Średnia cena | usunięta |

### Przykład (3 warstwy)

1. Towar X \| 2000 \| 31,38 zł \| wartość
2. Towar X \| 10 \| 31,22 zł \| wartość
3. Towar X \| 5 \| koszt nieustalony \| —

## Zmiany UI

- Nagłówek: **„Cena zakupu netto”** (bez „średnia”)
- Toolbar: „N **pozycji**” zamiast „N towarów”
- Tooltip: liczba warstw FIFO tylko przy hover (gdy > 1 warstwa w grupie)
- PDF inwentaryzacji: spójna etykieta i obsługa kosztu nieustalonego

## Build

```
cd frontend-react && npm run build
✓ built successfully
```

## Status wdrożenia

Commit: `feat(warehouse): group stock by purchase price` — patrz `WAREHOUSE_BALANCE_GROUP_BY_PRICE_DEPLOY.md`.
