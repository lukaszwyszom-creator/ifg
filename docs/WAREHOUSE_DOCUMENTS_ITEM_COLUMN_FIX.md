# Kolumna „Towar” w liście dokumentów magazynowych

**Data:** 2026-05-22  
**Zakres:** widok Magazyn → Dokumenty (`DocumentsTab.jsx`)

## Problem

Lista dokumentów pokazywała kolumnę „Opis / Powód” (notes, issue_reason, correction_reason), ale użytkownik potrzebował informacji o towarze/pozycjach dokumentu.

## Dostępność danych w API

| Dane | Dostępne na liście dokumentów? | Uwagi |
|------|-------------------------------|-------|
| Pozycje (`items[]`) | **Tak** | Każdy dokument w `GET /warehouse/documents` zawiera tablicę `items` z `item_id`, `quantity`, cenami itd. |
| Nazwa towaru | **Nie** | `WarehouseDocItemResponse` nie zawiera `name` ani `isbn` |
| ISBN towaru | **Nie** | j.w. |

**Wniosek:** pozycje dokumentu są dostępne na froncie bez zmian backendu. Etykiety towaru (nazwa, ISBN) wymagają mapowania `item_id` → katalog (`GET /warehouse/items`), co jest już stosowane w formularzu i szczegółach dokumentu w tym samym pliku.

Backend **nie był zmieniany** — wystarczy join z katalogiem po stronie UI.

### Opcjonalny minimalny backend patch (osobny krok, nie wdrożony)

Gdyby produkt wymagał jednego requestu bez dodatkowego ładowania katalogu:

1. W `WarehouseDocItemResponse` dodać opcjonalne pola `name: str | None`, `isbn: str | None`.
2. W mapperze listy dokumentów dołączyć join z `warehouse_items` (lub denormalizować przy zapisie).

To redukuje liczbę requestów, ale nie jest konieczne dla poprawnego działania UI.

## Zmiany UI

### `DocumentsTab.jsx`

- Kolumna „Opis / Powód” **zastąpiona** kolumną „Towar” (bez poszerzania tabeli).
- `DocList` ładuje równolegle dokumenty i katalog (`Promise.all`).
- Helpery:
  - `resolveDocItemLabel` — nazwa → ISBN → skrócony `item_id` (8 znaków + „…")
  - `fmtDocListItemsSummary` — jedna pozycja: sama nazwa; wiele: `"Pierwsza +N"` + `title` z pełną listą (tooltip natywny).

### `WarehousePage.module.css`

- Klasa `.docListItemCell`: `max-width`, `ellipsis`, `nowrap` — komórka nie rozpycha tabeli.

## Zachowanie (wymagania)

1. Jedna pozycja → nazwa towaru.
2. Wiele pozycji → `"Nazwa pierwsza +N"` (N = liczba pozostałych).
3. Brak nazwy w katalogu → ISBN, potem skrócony `item_id`.
4. Tooltip (`title`) z pełną listą pozycji (po jednej linii).
5. Logika PZ/WZ/post/cancel — bez zmian.

## Test

```bash
cd frontend-react && npm run build
```

Wynik: **sukces** (exit 0, ~1.3s).

```
✓ 960 modules transformed.
✓ built in 1.32s
```

## Status wdrożenia

Commit: `feat(warehouse): show item names in documents list` — patrz `WAREHOUSE_DOCUMENTS_ITEM_COLUMN_DEPLOY.md`.
