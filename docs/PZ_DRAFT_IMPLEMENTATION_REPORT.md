# Raport implementacji: PZ draft jako stan magazynowy (E1–E5)

**Data:** 2026-06-19  
**Podstawa:** [`docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md`](PZ_DRAFT_E1_E5_EXECUTION_PLAN.md)  
**Audyt prod (DS723+):** PZ posted = 1, PZ draft = 0, brak duplikatów warstw  
**Zakres:** E1–E5 zrealizowane; E6–E7 **poza zakresem**

---

## Status etapów

| Etap | Status | Uwagi |
|------|--------|-------|
| **E1** | ✅ Zrealizowany | Migracja `f8a9b0c1d2e3`, nullable koszt + UNIQUE |
| **E2** | ✅ Zrealizowany | `scripts/backfill_pz_draft_layers.py` — idempotentny no-op na prod |
| **E3** | ✅ Zrealizowany | `scripts/verify_pz_draft_backfill.sql` |
| **E4** | ✅ Zrealizowany | create/post/update/cancel PZ + FIFO NULL snapshot |
| **E5** | ✅ Zrealizowany | API balance + DocumentsTab + BalanceTab |

---

## Wynik testów

```text
pytest tests/unit/test_pz_draft_schema.py \
       tests/unit/test_backfill_pz_draft_layers.py \
       tests/unit/test_warehouse_documents.py \
       tests/unit/test_warehouse_balance_layers.py \
       tests/unit/test_warehouse_items.py

87 passed in 0.39s
```

---

## Zmienione / nowe pliki

### E1
- `alembic/versions/f8a9b0c1d2e3_pz_draft_nullable_layer_cost.py`
- `app/persistence/models/inventory_layer.py`
- `tests/unit/test_pz_draft_schema.py`

### E2
- `scripts/backfill_pz_draft_layers.py`
- `tests/unit/test_backfill_pz_draft_layers.py`

### E3
- `scripts/verify_pz_draft_backfill.sql`

### E4
- `app/services/warehouse_document_service.py`
- `app/persistence/repositories/inventory_layer_repository.py`
- `tests/unit/test_warehouse_documents.py`

### E5
- `app/services/warehouse_item_service.py`
- `app/schemas/warehouse_item.py`
- `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`
- `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx`
- `tests/unit/test_warehouse_balance_layers.py`

---

## Zgodność z wymaganiami biznesowymi

| # | Wymaganie | Implementacja |
|---|-----------|---------------|
| 1 | PZ draft = stan magazynowy | `_create_pz_draft_layers` w `create_document(PZ)` |
| 2 | PZ draft tworzy warstwę FIFO | `InventoryLayerORM` + `add_layer` |
| 3 | Warstwa draft: qty, price NULL | `purchase_unit_price=None` |
| 4 | Post PZ: UPDATE warstwy, koszt | `_post_pz` — lookup + `save`, bez INSERT |
| 5 | 1 linia PZ = 1 warstwa | UNIQUE index + guard w `_create_pz_draft_layers` |
| 6 | UNIQUE `source_document_item_id` | migracja E1 |
| 7 | WZ schodzi z draft | `_consume_fifo` bez filtra ceny; test `test_wz_consumes_draft_pz_layer_before_post` |
| 8 | Balance: ilość przy NULL koszcie | `quantity_available` zawsze; `cost_pending` |
| 9 | Wartość NULL bez kosztu | `value_net=None`, UI „—” |
| 10 | Brak duplikatów po post | post nie tworzy warstwy; test `test_post_pz_does_not_duplicate_layer` |

---

## Zgodność z planem wykonawczym

| Punkt planu | Status |
|-------------|--------|
| 1 migracja Alembic (M1+M2+M3) | ✅ jedna rewizja |
| Backfill idempotentny | ✅ `--dry-run` / `--execute` |
| Gate SQL E3 | ✅ 6 query |
| Kolejność commitów E4-a/b/c | ✅ repo → service → testy |
| E5 API + frontend | ✅ |
| E6/E7 nie dotykane | ✅ |
| Jedno okno maintenance | ✅ możliwe (patrz wdrożenie) |

---

## Wdrożenie DS723+ (checklist)

Prod: **0 PZ draft** → backfill będzie no-op, ale **obowiązkowy** w oknie.

```bash
# 1. Backup
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec db pg_dump -U postgres -d ksef_backend -Fc \
  > /volume1/docker/ifg/backups/pre_pz_draft_$(date +%Y%m%d).dump

# 2. E1
docker compose ... exec api alembic upgrade head

# 3. E2 (no-op expected: candidates=0)
docker compose ... exec api python -m scripts.backfill_pz_draft_layers --dry-run
docker compose ... exec api python -m scripts.backfill_pz_draft_layers --execute

# 4. E3
docker compose ... exec db psql -U postgres -d ksef_backend \
  -f /path/to/scripts/verify_pz_draft_backfill.sql

# 5. E4+E5
cd frontend-react && npm ci && npm run build && cd ..
docker compose ... up -d --build --force-recreate api worker
```

**Smoke po wdrożeniu:**
1. Nowy PZ draft bez ceny → Stany: qty widoczne, wartość „—”
2. Zaksięguj PZ z ceną → wartość uzupełniona, 1 warstwa
3. WZ schodzi z qty
4. Istniejący posted PZ (1 szt.) — regresja: warstwa z ceną bez zmian

---

## Ryzyka produkcyjne

| Ryzyko | Poziom | Mitigacja |
|--------|--------|-----------|
| Podwójna warstwa przy post | **niskie** (po E4) | UNIQUE + UPDATE-only `_post_pz` |
| Backfill na prod | **bardzo niskie** | 0 draft PZ — no-op |
| Istniejący posted PZ | **niskie** | 1 dokument z warstwą i ceną — bez migracji danych |
| WZ przed post PZ — snapshot NULL | **średnie** | Akceptowane biznesowo; ruchy z `purchase_unit_price_snapshot=NULL` |
| Balance cache vs warstwy | **niskie–średnie** | create/cancel/update synchronizują `upsert_balance`; E3-3 po wdrożeniu |
| Frontend dist nie przebudowany | **średnie** | Obowiązkowy `npm run build` na DS723+ |
| Edycja PZ po częściowym WZ | **niskie** | Blokada z komunikatem błędu |
| Brak walidacji FV zakupu przy post | **informacyjne** | Poza minimalnym E4; wymaga ceny na linii, nie `source_invoice_id` |

**Ocena ryzyka wdrożenia na prod (z audytem 0 draft):** **niska–średnia** (głównie okno maintenance + dist + smoke).

---

## Odstępstwa od planu (minimalne)

1. **FV zakupu przy post PZ** — plan biznesowy wspomina `source_invoice_id`; E4 wymaga tylko `purchase_unit_price` na linii (pole nagłówka istnieje, brak twardej walidacji FV).
2. **`WarehousePage.module.css`** — bez zmian; użyto istniejących stylów i „—” w tabeli.
3. **`recalculate_balance()` w repo** — nie dodano; delta `upsert_balance` w create/cancel/update wystarcza.

---

## Następne kroki (poza tym wdrożeniem)

- **E6:** blokada sprzedaży przy braku stanu (FV)
- **E7:** auto-WZ przy ACCEPTED
- Opcjonalnie: walidacja FV zakupu przy post PZ

---

## Podsumowanie

Implementacja E1–E5 jest **kompletna i zgodna** z [`docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md`](PZ_DRAFT_E1_E5_EXECUTION_PLAN.md). Przy **0 PZ draft** na produkcji backfill E2 jest bezpiecznym no-op; kluczowe ryzyko to poprawne wdrożenie w **jednym oknie** (E1→E2→E3→E4+E5) z rebuildem frontendu.
