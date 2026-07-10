# PZ draft edit hotfix — raport wdrożenia DS723+

**Data:** 2026-06-20  
**Commit:** `0eca052` — `fix(warehouse): flush PZ draft items before recreating layers`

## Testy lokalne (przed commit)

```
.venv/bin/pytest tests/unit/test_warehouse_documents.py \
  tests/unit/test_warehouse_items.py \
  tests/unit/test_warehouse_balance_layers.py -q

82 passed in 0.36s
```

## Git

- Branch: `production`
- Push: `origin/production` (`6d00b34..0eca052`)
- Pliki w commicie:
  - `app/services/warehouse_document_service.py` (+1 linia: `self.session.flush()` przed `_create_pz_draft_layers` w `update_document`)
  - `tests/unit/test_warehouse_documents.py` (`test_edit_pz_draft_recreates_layers`)
  - `docs/PZ_DRAFT_EDIT_FIX.md`

## Deploy DS723+

Ścieżka: `/volume1/docker/ifg_v2/ifg_standalone`

```bash
git pull --ff-only origin production   # OK: fast-forward 6d00b34..0eca052
docker compose -f docker/docker-compose.prod.yml --env-file .env.production build api
docker compose -f docker/docker-compose.prod.yml --env-file .env.production up -d --no-deps --force-recreate api worker
```

- **Alembic:** nie uruchamiano (migracja `f8a9b0c1d2e3` już na produkcji).
- Pierwszy `curl /health` tuż po recreate: `Connection reset by peer` (API jeszcze startowało).
- Po ~8 s: health OK.

### Health (po starcie)

```json
{
  "status": "ok",
  "app_name": "IFG Faktury",
  "version": "1.0.0",
  "environment": "production",
  "db_timezone": "Europe/Warsaw"
}
```

## Weryfikacja ręczna — edycja PZ draft

Dokument produkcyjny:

| Pole | Wartość |
|------|---------|
| `id` | `f3dd031e-08b5-49b3-9d55-9637833ddae6` |
| Typ | PZ draft |
| Towar | Kościoły Archidiecezji Częstochowskiej t. II |

Scenariusz: ilość **10 → 15**, zapis przez `WarehouseDocumentService.update_document()` w kontenerze `api`.

| Metryka | Przed | Po |
|---------|-------|-----|
| Ilość pozycji dokumentu | 10 | **15** |
| Warstwa FIFO (`remaining_quantity`) | 10 | **15** |
| Stan magazynowy (`warehouse_balance`) | 2010 | **2015** (+5) |

**Wynik:** brak wyjątku FK, edycja PZ draft działa poprawnie.

## Ryzyko resztkowe

- Niskie — zmiana punktowa, spójna z `create_document()`.
- Frontend bez zmian w tym deployu (hotfix tylko API).
