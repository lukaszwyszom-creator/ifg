# Naprawa edycji PZ draft — FK violation

**Data:** 2026-05-22

## Problem produkcyjny

Edycja PZ draft kończyła się błędem:

```
ForeignKeyViolation: inventory_layers.source_document_item_id
Key (source_document_item_id)=... is not present in table warehouse_document_items
```

Stack: `update_document()` → `_create_pz_draft_layers()` → `add_layer()` → `session.flush()`.

## Przyczyna

W `update_document()` flow edycji PZ draft:

1. `_sync_pz_draft_layers_before_replace()` — usuwa stare warstwy FIFO (OK).
2. Usunięcie starych `warehouse_document_items` z sesji, dodanie nowych pozycji do `doc.doc_items` (tylko w pamięci ORM).
3. `_create_pz_draft_layers()` — tworzy `inventory_layers` z `source_document_item_id = item.id`.
4. `InventoryLayerRepository.add_layer()` wywołuje `session.flush()` — PostgreSQL wymaga istniejącego wiersza w `warehouse_document_items`.

Nowe pozycje dokumentu **nie były flushowane** przed utworzeniem warstw.

W `create_document()` ten sam problem nie występował — po `doc_repo.add()` jest jawne `self.session.flush()` przed `_create_pz_draft_layers()`.

## Poprawka

Jedna linia w `update_document()` — `self.session.flush()` po zastąpieniu pozycji, przed `_create_pz_draft_layers()`:

```python
if doc.doc_type == WarehouseDocumentType.PZ.value:
    self.session.flush()
    self._create_pz_draft_layers(doc, date.today())
```

Spójne z flow tworzenia PZ draft. Bez zmian w post/cancel/WZ/FIFO.

## Test regresji

`test_edit_pz_draft_recreates_layers` w `tests/unit/test_warehouse_documents.py`:

- `FkEnforcingLayerRepository` symuluje FK (warstwa wymaga flushowanych pozycji).
- Scenariusz: create PZ draft → edit quantity → save bez wyjątku → warstwa istnieje z poprawną ilością.

## Wynik testów

```
.venv/bin/pytest tests/unit/test_warehouse_documents.py \
  tests/unit/test_warehouse_items.py \
  tests/unit/test_warehouse_balance_layers.py -q

82 passed in 0.40s
```

## Ryzyko

| Obszar | Ocena |
|--------|-------|
| create PZ draft | Brak — ten sam wzorzec co wcześniej |
| edit PZ draft | Naprawione |
| cancel PZ draft | Brak zmian w kodzie |
| post PZ | Brak zmian w kodzie |
| WZ / FIFO | Brak zmian w kodzie |
| Wydajność | Jeden dodatkowy flush w ścieżce update PZ — akceptowalne |

Jedyny edge case: jeśli flush po replace pozycji nie usunie starych wierszy z DB przed insertem warstw — w praktyce SQLAlchemy w jednej transakcji najpierw przetwarza DELETE, potem INSERT przy flush; FK na nowe `item.id` (nowe UUID) nie koliduje ze starymi wierszami.
