# Wdrożenie: grupowanie stanów magazynowych po cenie zakupu

**Data:** 2026-06-20

## Commit

```
feat(warehouse): group stock by purchase price
```

## Pliki

- `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx`
- `docs/WAREHOUSE_BALANCE_GROUP_BY_PRICE_FIX.md`

## Zmiana względem produkcji (18358af)

| Aspekt | Było (18358af) | Jest |
|--------|----------------|------|
| Agregacja | `item_id` | `item_id + unit_price_net` |
| Nagłówek ceny | Śr. cena netto | Cena zakupu netto |
| Średnia | tak | usunięta |
| Wiersze | 1 na towar | osobny wiersz na każdą cenę zakupu |
| Koszt nieustalony | zastępował cały wiersz z wartością | osobny wiersz, wartość „—” |

## Build lokalny

```
cd frontend-react && npm run build
✓ built in ~1.3s
```

## Push

Branch: `production` → `origin/production`

## Deploy DS723+ (krok operacyjny)

Frontend wymaga osobnego deployu dist na NAS (bind-mount):

```bash
cd frontend-react && npm run build
# rsync dist/ → DS723+ (deploy-ds723.sh lub tar przez SSH)
```

API/worker — bez zmian (tylko frontend).

## Weryfikacja po deploy

- Brak „Śr. cena netto” w UI
- Ten sam towar z różnymi cenami = wiele wierszy
- Warstwy bez ceny = „koszt nieustalony”, wartość „—”
