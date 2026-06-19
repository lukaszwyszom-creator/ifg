# Guardian — odtworzenie suggested_sale_price_mode

**Data:** 2026-05-22  
**Branch:** `production` @ `752992f`  
**Zakres:** wyłącznie 9 plików wskazanych w `docs/GUARDIAN_WORKTREE_CLEANUP_PZ_PRICE_MODE.md`  
**Bez:** commit, push, deploy, DS723+

---

## Odtworzone pliki

| Plik | Zmiana |
|------|--------|
| `app/persistence/models/warehouse_item.py` | `suggested_sale_price_mode` (NOT NULL, default `net`) |
| `app/persistence/models/warehouse_document.py` | `suggested_sale_price_mode` (nullable snapshot) |
| `app/schemas/warehouse_item.py` | pole w `WarehouseItemResponse` |
| `app/schemas/warehouse_document.py` | input/response + validator `net\|gross` |
| `app/services/warehouse_document_service.py` | `_resolve_doc_item_suggested_sale_price_mode`, post PZ → catalog `gross` |
| `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx` | kolumny PZ, `fmtMoney2`, wysyłka `suggested_sale_price_mode: 'gross'` |
| `frontend-react/src/pages/warehouse/WarehousePage.module.css` | `.pzItemsTable`, `.numCell`, `.numInput`, szerokości kolumn |
| `frontend-react/src/components/invoice/InvoiceForm.jsx` | import `catalogItemToLineFields` z helpera |
| `frontend-react/src/api/warehouseItems.js` | komentarz semantyki `net\|gross` |

## Pliki poza zakresem (już obecne jako untracked)

- `alembic/versions/e7f8a9b0c1d2_add_suggested_sale_price_mode.py`
- `tests/unit/test_suggested_sale_price_mode.py`
- `frontend-react/src/components/invoice/catalogItemLineFromWarehouse.js`
- `frontend-react/src/components/invoice/catalogItemLineFromWarehouse.test.js`

---

## Wynik testów

```bash
pytest tests/unit/test_suggested_sale_price_mode.py tests/unit/test_warehouse_documents.py tests/unit/test_warehouse_items.py -q
# 70 passed in 0.38s

node --test frontend-react/src/components/invoice/catalogItemLineFromWarehouse.test.js
# 8 passed
```

## Wynik build

```bash
cd frontend-react && npm run build
# ✓ built in 1.26s
```

---

## Kompletność feature

| Element | Status |
|---------|--------|
| Migracja Alembic | ✅ untracked na dysku |
| ORM + schemas + service | ✅ odtworzone |
| PZ UI (kolumny, gross w API) | ✅ odtworzone |
| FV mapowanie net/gross | ✅ helper + InvoiceForm import |
| Testy backend + frontend | ✅ 70 + 8 passed |
| Frontend build | ✅ OK |

**Feature kompletny** w worktree — wymaga migracji DB przed deployem (`alembic upgrade head`).

---

## Ryzyka

- Po deploy: migracja `e7f8a9b0c1d2` przed startem aplikacji.
- Historyczne `suggested_sale_price` pozostają `mode='net'` (DEFAULT migracji).
- Nowe PZ z normatywną ceną ustawiają `mode='gross'` na pozycji dokumentu i kartotece przy księgowaniu.
