# Diagnoza: raport GROUP_BY_PRICE vs produkcja

**Data:** 2026-06-20  
**Tryb:** read-only, bez wdrożenia

## Pytanie

Czy `WAREHOUSE_BALANCE_GROUP_BY_PRICE_FIX.md` opisuje kod faktycznie wdrożony na DS723+?

**Odpowiedź: NIE.**

---

## 1. Commity — stan repozytoriów

| Lokalizacja | HEAD | Commit GROUP_BY_PRICE |
|-------------|------|------------------------|
| **Lokalnie** (`production`) | `18358af` | **brak** — zmiany tylko w working tree |
| **origin/production** | `18358af` | **brak** |
| **DS723+** | `18358af` | **brak** |

### Ostatnie commity magazynowe (production)

```
18358af fix(warehouse): clarify average stock price UI      ← wdrożony
0eca052 fix(warehouse): flush PZ draft items before recreating layers
6d00b34 feat(warehouse): PZ draft as real stock
62ff9ac Aggregate warehouse stock by item
```

Commit **GROUP_BY_PRICE** nigdy nie został utworzony ani wypchnięty.

---

## 2. Raporty vs commity

| Plik raportu | W commicie? | Kod opisany wdrożony? |
|--------------|-------------|------------------------|
| `WAREHOUSE_BALANCE_AVERAGE_PRICE_UI_FIX.md` | tak (`18358af`) | **tak** |
| `WAREHOUSE_BALANCE_COST_PENDING_FIX.md` | **nie** (untracked) | **nie** |
| `WAREHOUSE_BALANCE_GROUP_BY_PRICE_FIX.md` | **nie** (untracked) | **nie** |

Raport `WAREHOUSE_BALANCE_GROUP_BY_PRICE_FIX.md` został **napisany po lokalnym `npm run build`**, ale **bez commitu, pushu i deployu**.

---

## 3. DS723+ — frontend dist

- Ścieżka: `/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/assets/index-DFvstsAU.js`
- Data modyfikacji: **2026-06-20 22:30** (po commicie `18358af`)
- Zawartość bundla: string **`Śr. cena`** — wersja z commitu `18358af`
- Brak w bundlu: `aggregateBalanceByItemAndPrice`, `balanceGroupKey`, `Cena zakupu netto`

`npm run build` na DS723+ wykonano dla wersji **18358af** (średnia cena), nie dla GROUP_BY_PRICE.

---

## 4. Weryfikacja kodu BalanceTab.jsx

### Commit `18358af` / produkcja / origin / DS723+ (źródło)

| Aspekt | Stan |
|--------|------|
| Agregacja | **`aggregateBalanceByItem`** — tylko po `item_id` |
| Nagłówek kolumny | **„Śr. cena netto”** |
| Cena w komórce | **`fmtAvgUnitPrice()`** — średnia `value_net / quantity_available` |
| Koszt nieustalony | tak, gdy `has_cost_pending` (cały wiersz zamiast ceny) |
| Wiersze | **1 wiersz na towar** (np. 2015 szt. zagregowane) |

### Working tree lokalny (niezacommitowane)

| Aspekt | Stan |
|--------|------|
| Agregacja | **`aggregateBalanceByItemAndPrice`** — po `item_id + unit_price_net` |
| Nagłówek | **„Cena zakupu netto”** |
| Średnia | usunięta |
| Koszt nieustalony | tylko dla wiersza bez ceny (`cost_pending`) |
| Wiersze | wiele wierszy na ten sam towar przy różnych cenach |

Plik: `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx` — **modified, unstaged**.

---

## 5. Zgodność raport ↔ produkcja

| Źródło | Zgodne z produkcją? |
|--------|---------------------|
| `WAREHOUSE_BALANCE_AVERAGE_PRICE_UI_FIX.md` | **tak** — opisuje `18358af` |
| `WAREHOUSE_BALANCE_GROUP_BY_PRICE_FIX.md` | **nie** — opisuje kod tylko lokalny, niewdrożony |
| Obserwacja użytkownika (ŚR. CENA NETTO, 2015 szt., koszt nieustalony) | **tak** — zgodna z `18358af` |

---

## 6. Wnioski

1. Produkcja działa zgodnie z commitem **`18358af`** (UI średniej ceny), nie z GROUP_BY_PRICE.
2. Raport GROUP_BY_PRICE został wygenerowany **przed commitowaniem i deployem** — dokumentacja wyprzedziła wdrożenie.
3. Aby produkcja pokazała grupowanie po cenie zakupu, wymagane: commit → push → `npm run build` → rsync/deploy `dist/` na DS723+.
