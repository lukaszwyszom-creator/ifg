# suggested_sale_price_mode — net vs gross

## Cel

Jednoznaczna semantyka `suggested_sale_price`:
- historyczne dane → **netto** (`mode='net'`, DEFAULT w DB),
- nowe PZ → normatywna cena **brutto** (`mode='gross'`),
- FV podstawia cenę według `suggested_sale_price_mode`, bez zgadywania.

## Migracja

**Revision:** `e7f8a9b0c1d2` (`add_suggested_sale_price_mode`)  
**Revises:** `e2f3a4b5c6d7`

| Tabela | Kolumna | Reguła |
|--------|---------|--------|
| `warehouse_items` | `suggested_sale_price_mode` | `NOT NULL DEFAULT 'net'`, CHECK `IN ('net','gross')` |
| `warehouse_document_items` | `suggested_sale_price_mode` | `NULL`, CHECK nullable; snapshot z PZ |

Istniejące rekordy kartoteki dostają `'net'` przez DEFAULT — bez przeliczania wartości.

## Pliki

| Plik | Zmiana |
|------|--------|
| `alembic/versions/e7f8a9b0c1d2_add_suggested_sale_price_mode.py` | migracja |
| `app/persistence/models/warehouse_item.py` | pole ORM |
| `app/persistence/models/warehouse_document.py` | pole ORM (snapshot) |
| `app/schemas/warehouse_item.py` | response API |
| `app/schemas/warehouse_document.py` | input/response |
| `app/services/warehouse_document_service.py` | post PZ → `mode='gross'` |
| `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx` | wysyłka `mode='gross'` |
| `frontend-react/src/components/invoice/catalogItemLineFromWarehouse.js` | mapowanie FV |
| `frontend-react/src/components/invoice/InvoiceForm.jsx` | import helpera |
| `tests/unit/test_suggested_sale_price_mode.py` | testy backend |
| `frontend-react/src/components/invoice/catalogItemLineFromWarehouse.test.js` | testy mapowania FV |

## Testy

```bash
pytest tests/unit/test_suggested_sale_price_mode.py tests/unit/test_warehouse_documents.py tests/unit/test_warehouse_items.py -q
node --test frontend-react/src/components/invoice/catalogItemLineFromWarehouse.test.js
cd frontend-react && npm run build
```

## Ryzyka

- Po deploy wymagana migracja Alembic przed startem aplikacji.
- Stare PZ-drafty bez `suggested_sale_price_mode` w DB: backend domyśli `'gross'` gdy podano cenę normatywną.
- Kartoteka z historycznym `mode='net'` i nową etykietą „brutto” w UI — użytkownik musi zaksięgować nowe PZ z `gross`, żeby zaktualizować tryb na towarze.
