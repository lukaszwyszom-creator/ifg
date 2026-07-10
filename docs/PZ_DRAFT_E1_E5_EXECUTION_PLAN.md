# Plan wykonawczy E1–E5: PZ draft jako stan magazynowy

**Data:** 2026-06-19  
**Podstawa:** [`docs/PZ_DRAFT_IMPLEMENTATION_AUDIT_2026_06.md`](PZ_DRAFT_IMPLEMENTATION_AUDIT_2026_06.md), [`docs/PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md`](PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md)  
**Zakres:** etapy E1–E5 (schema → backfill → weryfikacja → backend → UI/API). Bez implementacji w tym dokumencie.

---

## Podsumowanie wykonawcze

| Metryka | Ocena |
|---------|-------|
| **Złożoność implementacji** | **średnia–wysoka** (~12 plików, 1 migracja Alembic, skrypt backfill, ~15 testów do zmiany) |
| **Ryzyko wdrożenia** | **wysokie** (podwójne warstwy, rozjechany balance, okno maintenance obowiązkowe) |
| **Draft PZ na prod (DS723+)** | **niezweryfikowane w tej sesji** — wymaga SQL na produkcji (§ Produkcja) |
| **Migracje Alembic** | **1 rewizja** (zalecane) lub max **2** przy rozdzieleniu indeksu UNIQUE |
| **Jedno okno maintenance E1–E5** | **TAK — zalecane i konieczne** dla bezpiecznego wdrożenia |

---

## Produkcja DS723+: czy są draft PZ wymagające backfill?

### Status audytu prod

Z tej sesji **brak dostępu SSH/SQL do bazy DS723+**. Nie można potwierdzić liczby draft PZ ani linii bez warstw.

### Zapytania do wykonania na prod (przed oknem maintenance)

```bash
cd /volume1/docker/ifg/ifg_standalone
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec db psql -U postgres -d ksef_backend -c "
SELECT COUNT(*) AS draft_pz_documents
FROM warehouse_documents
WHERE doc_type = 'PZ' AND status = 'draft';
"
```

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec db psql -U postgres -d ksef_backend -c "
SELECT COUNT(*) AS draft_pz_lines_without_layer
FROM warehouse_documents d
JOIN warehouse_document_items di ON di.document_id = d.id
LEFT JOIN inventory_layers il ON il.source_document_item_id = di.id
WHERE d.doc_type = 'PZ' AND d.status = 'draft' AND il.id IS NULL;
"
```

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec db psql -U postgres -d ksef_backend -c "
SELECT d.id, d.created_at, COUNT(di.id) AS lines, SUM(di.quantity) AS total_qty
FROM warehouse_documents d
JOIN warehouse_document_items di ON di.document_id = d.id
LEFT JOIN inventory_layers il ON il.source_document_item_id = di.id
WHERE d.doc_type = 'PZ' AND d.status = 'draft' AND il.id IS NULL
GROUP BY d.id, d.created_at
ORDER BY d.created_at;
"
```

### Interpretacja wyników

| `draft_pz_lines_without_layer` | Backfill E2 |
|--------------------------------|-------------|
| **0** | Skrypt `--execute` = no-op; **nadal obowiązkowy** w oknie (idempotencja + audyt) |
| **> 0** | **Obowiązkowy** backfill przed pierwszym requestem E4; czas okna +5–15 min per ~100 linii |
| Duplikaty `source_document_item_id` (przed E1) | Naprawa ręczna przed UNIQUE — query poniżej |

```sql
SELECT source_document_item_id, COUNT(*)
FROM inventory_layers
WHERE source_document_item_id IS NOT NULL
GROUP BY source_document_item_id
HAVING COUNT(*) > 1;
```

**Wniosek operacyjny:** backfill projektujemy **zawsze** (idempotentny). Liczba rekordów prod decyduje o czasie E2, nie o konieczności etapu.

---

## Oszacowanie migracji Alembic

| Wariant | Liczba rewizji | Zawartość |
|---------|----------------|-----------|
| **Zalecany** | **1** | `purchase_unit_price` nullable na `inventory_layers`; nullable `purchase_unit_price_snapshot` na `inventory_layer_movements`; partial UNIQUE INDEX na `source_document_item_id` |
| Alternatywa | 2 | Rewizja 1: nullable kolumny; Rewizja 2: UNIQUE po backfill — **niezalecane** (brak ochrony podczas backfillu) |
| Opcjonalny `cost_finalized` | +0 lub +1 | **Pomijamy** — wystarczy `purchase_unit_price IS NOT NULL` jako sygnał kosztu |

**Docelowa rewizja (nazwa robocza):** `alembic/versions/<rev>_pz_draft_nullable_layer_cost.py`

**Pliki w commicie E1:**
- `alembic/versions/<rev>_pz_draft_nullable_layer_cost.py` (nowy)
- `app/persistence/models/inventory_layer.py`

---

## Czy E1–E5 w jednym oknie maintenance?

**Tak — zalecane i w praktyce wymagane.**

| Etap | W oknie? | Uwaga |
|------|----------|-------|
| E1 | tak | `alembic upgrade head` — stary kod nadal działa (nullable rozszerza schemat) |
| E2 | tak | natychmiast po E1, **przed** restartem API z E4 |
| E3 | tak | gate SQL — STOP jeśli fail |
| E4 | tak | deploy obrazu API z nowym kodem |
| E5 | tak | `npm run build` + ten sam restart API (dist bind-mount) |

**Nie wolno:** wdrożyć E4 bez E1+E2+E3 w tym samym oknie.  
**Można rozłożyć na commity dev:** E1→E4→E5 w repo (3–5 commitów), ale **prod = jeden release tag** + jedno okno.

**Szacowany czas okna:** 60–90 min (backup 10 + E1 5 + E2 10–30 + E3 10 + build 10 + deploy 10 + smoke 15).

---

# Etap E1 — Migracja schematu

## Cel

Warstwy FIFO mogą istnieć bez ceny; ruch WZ może zapisać NULL snapshot; jedna linia PZ = max jedna warstwa.

## Pliki do zmiany

| Plik | Zmiana |
|------|--------|
| `alembic/versions/<rev>_pz_draft_nullable_layer_cost.py` | **nowy** — upgrade/downgrade |
| `app/persistence/models/inventory_layer.py` | `purchase_unit_price: Mapped[Decimal \| None]`; `purchase_unit_price_snapshot: Mapped[Decimal \| None]`; aktualizacja komentarzy (cena ustalana przy post PZ) |

**Bez zmian:** `warehouse_document.py`, repozytoria, serwisy — stary kod ignoruje NULL do momentu E4.

## Kolejność commitów (dev)

```
commit E1-a: schema: nullable layer cost + unique source_document_item_id
  - alembic/versions/<rev>_pz_draft_nullable_layer_cost.py
  - app/persistence/models/inventory_layer.py
```

## Ryzyka

| Ryzyko | Poziom | Mitigacja |
|--------|--------|-----------|
| Istniejące duplikaty `source_document_item_id` blokują UNIQUE | średni | Query przed E1; ręczna korekta |
| Downgrade usuwa nullable — strata warstw NULL | niski | Nie robić downgrade na prod po E2 |
| Stary kod ORM wymaga NOT NULL w Pythonie | **wysoki** | E1 deploy **bez** E4 krótko OK w ORM, ale po E1 trzeba zaktualizować model w tym samym release co E4 |

## Wpływ na istniejące testy

| Plik | Wpływ |
|------|-------|
| `tests/unit/test_warehouse_documents.py` | **brak** — warstwy w testach zawsze z ceną |
| `tests/unit/test_warehouse_balance_layers.py` | **brak** |
| `tests/unit/test_warehouse_items.py` | **brak** |

## Testy do aktualizacji (E1)

- Brak obowiązkowych — opcjonalnie test migracji smoke: `alembic upgrade head` na czystej DB testowej.

## Wdrożenie DS723+ (E1)

```bash
# Po backup pg_dump
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api alembic upgrade head
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api alembic current
```

**Gate:** `alembic current` = nowa rewizja; brak błędu w logach api.

---

# Etap E2 — Backfill PZ draft

## Cel

Linie PZ `draft` bez warstwy dostają `inventory_layers` (qty, price NULL) i delta `warehouse_balance` — **zanim** włączy się kod E4.

## Pliki do zmiany / utworzenia

| Plik | Zmiana |
|------|--------|
| `scripts/backfill_pz_draft_layers.py` | **nowy** — skrypt operacyjny |
| `scripts/backfill_pz_draft_layers.sql` | **opcjonalny** — wersja SQL-only (audyt) |

**Bez zmian w aplikacji** — czysto operacyjny etap.

## Kolejność commitów (dev)

```
commit E2-a: ops: backfill script for PZ draft inventory layers
  - scripts/backfill_pz_draft_layers.py
  - (opcjonalnie) scripts/backfill_pz_draft_layers.sql
```

Commit E2 **przed** commitem E4 w historii repo; na prod wykonany **po** E1, **przed** deployem E4.

## Projekt skryptu backfill (szczegółowy)

### Interfejs CLI

```text
python -m scripts.backfill_pz_draft_layers [--dry-run|--execute] [--batch-id UUID]
```

| Flaga | Działanie |
|-------|-----------|
| `--dry-run` | SELECT kandydatów, log planowanych INSERT/UPDATE balance, **bez** commit |
| `--execute` | transakcja DB, commit, log JSON Lines do stdout + plik |
| `--batch-id` | UUID wpisywany do logu (rollback manualny po layer_id) |

### Algorytm (pseudokod)

```text
1. START TRANSACTION (tylko --execute)

2. Kandydaci:
   SELECT di.id AS doc_item_id, di.item_id, di.quantity, d.created_at, d.id AS doc_id
   FROM warehouse_documents d
   JOIN warehouse_document_items di ON di.document_id = d.id
   LEFT JOIN inventory_layers il ON il.source_document_item_id = di.id
   WHERE d.doc_type = 'PZ' AND d.status = 'draft' AND il.id IS NULL
   FOR UPDATE OF d, di

3. Dla każdego wiersza:
   layer_id = uuid4()
   INSERT inventory_layers (
     id, item_id, source_document_item_id, source_document_type,
     received_quantity, remaining_quantity, purchase_unit_price,
     received_date, is_correction
   ) VALUES (
     layer_id, item_id, doc_item_id, 'PZ',
     quantity, quantity, NULL,
     DATE(d.created_at AT TIME ZONE 'UTC'), false
   )
   LOG {action: insert_layer, layer_id, doc_item_id, doc_id, item_id, qty}

4. Agregacja delta per item_id z kroku 3:
   Dla każdego item_id: upsert warehouse_balance.quantity_available += SUM(qty nowych warstw)
   (INSERT ... ON CONFLICT (item_id) DO UPDATE SET quantity_available = quantity_available + EXCLUDED...)

5. COMMIT

6. Wypisz podsumowanie: documents, lines, layers_inserted, items_balance_updated
```

### Reguły idempotencji

- Warunek `il.id IS NULL` — ponowne uruchomienie **nie** duplikuje warstw (przy działającym UNIQUE z E1).
- **Nie** ustawiać `purchase_unit_price` z linii dokumentu — NULL do post PZ (zgodnie z kontraktem biznesowym).

### Obsługa błędów

| Sytuacja | Reakcja |
|----------|---------|
| `quantity <= 0` | SKIP + log warning |
| `item_id` nie istnieje w `warehouse_items` | ABORT całej transakcji |
| UNIQUE violation | ABORT + komunikat „warstwa już istnieje — uruchom weryfikację E3” |
| Częściowy rozchód niemożliwy przy draft bez warstwy | N/A (draft nie miał warstw) |

### Rollback (awaryjny)

```sql
-- Tylko warstwy z logu batch_id, jeśli zero movements z nich
DELETE FROM inventory_layers WHERE id IN (...);
-- Przelicz balance dla dotkniętych item_id (patrz E3 query 4.3)
```

### Zależności Python

- `DATABASE_URL` z env (ten sam co api)
- SQLAlchemy Session lub `psycopg` — wzorzec jak inne skrypty w `scripts/` (jeśli brak — minimalny standalone z `app.persistence`)

## Ryzyka

| Ryzyko | Poziom | Mitigacja |
|--------|--------|-----------|
| Backfill + stary kod post PZ = duplikat warstwy | **krytyczny** | Okno maintenance: brak post PZ draft; E4 deploy zaraz po E3 |
| Balance rozjechany vs suma warstw | średni | Recalculate per item po backfill (krok 4 agreguje delta; E3 query 4.3) |
| Uruchomienie bez E1 (NOT NULL) | **krytyczny** | Gate: alembic current przed `--execute` |

## Wpływ na istniejące testy

Brak — skrypt poza pytest (opcjonalny test integracyjny w CI z DB testową — poza minimalnym zakresem).

## Testy do aktualizacji (E2)

- Opcjonalnie: `tests/integration/test_backfill_pz_draft_layers.py` — draft PZ bez warstwy → po skrypcie 1 warstwa, balance OK.

## Wdrożenie DS723+ (E2)

```bash
# API może być zatrzymane lub na starym kodzie — ZERO post PZ draft w tym czasie
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api python -m scripts.backfill_pz_draft_layers --dry-run

docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec api python -m scripts.backfill_pz_draft_layers --execute \
  2>&1 | tee /volume1/docker/ifg/logs/backfill_pz_draft_$(date +%Y%m%d_%H%M).log
```

**Gate:** `draft_pz_lines_without_layer = 0`.

---

# Etap E3 — Weryfikacja danych (gate)

## Cel

Potwierdzenie spójności DB przed pierwszym requestem na kod E4/E5. **Brak zmian w kodzie aplikacji.**

## Pliki do zmiany

| Plik | Zmiana |
|------|--------|
| `scripts/verify_pz_draft_backfill.sql` | **nowy** (opcjonalny) — zestaw query z planu |
| `docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md` | wyniki prod wpisać ręcznie po audycie |

## Kolejność commitów (dev)

```
commit E3-a: ops: SQL verification queries for PZ draft backfill gate
  - scripts/verify_pz_draft_backfill.sql
```

## Query gate (wszystkie muszą PASS)

| ID | Opis | Oczekiwany wynik |
|----|------|------------------|
| E3-1 | Linie draft PZ bez warstwy | 0 wierszy |
| E3-2 | Duplikaty `source_document_item_id` | 0 wierszy |
| E3-3 | `warehouse_balance` vs SUM(`remaining_quantity`) | 0 rozjechań |
| E3-4 | `di.quantity` vs `il.received_quantity` dla draft | 0 rozjechań |
| E3-5 | Posted PZ bez warstwy / bez ceny | 0 wierszy |
| E3-6 | Warstwy draft z `purchase_unit_price IS NULL` | = liczba linii draft (jeśli backfill >0) |

Pełne SQL — [`docs/PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md`](PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md) §4.

## Ryzyka

| Ryzyko | Poziom | Mitigacja |
|--------|--------|-----------|
| Przejście gate z rozjechanym balance | **wysoki** | STOP deploy; recalculate SQL |
| Fałszywy PASS przy nieuruchomionym backfillu | **krytyczny** | E3-1 obowiązkowe |

## Wpływ na testy

Brak.

## Testy do aktualizacji (E3)

Brak.

## Wdrożenie DS723+ (E3)

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  exec db psql -U postgres -d ksef_backend -f - < scripts/verify_pz_draft_backfill.sql
```

**Gate:** operator + dev sign-off → dopiero deploy E4.

---

# Etap E4 — Backend: create / post / update / cancel PZ + FIFO

## Cel

PZ draft tworzy warstwę i balance; post PZ tylko uzupełnia koszt (i opcjonalnie FV zakupu); update/cancel synchronizują warstwy; WZ schodzi z warstw bez ceny.

## Pliki do zmiany

| Plik | Zmiana |
|------|--------|
| `app/services/warehouse_document_service.py` | **główny** — patrz tabela poniżej |
| `app/persistence/repositories/inventory_layer_repository.py` | `get_by_source_document_item_id(doc_item_id) -> InventoryLayerORM \| None` |
| `app/persistence/repositories/warehouse_document_repository.py` | opcjonalnie: `recalculate_balance(item_id)` — minimalna implementacja SUM warstw (jeśli cancel/update wymaga) |
| `app/schemas/warehouse_document.py` | opcjonalnie: walidacja post PZ — `source_invoice_id` w body update przed post (jeśli API expose) |

### Zmiany w `warehouse_document_service.py` (minimalne)

| Metoda | Zmiana |
|--------|--------|
| Docstring modułu L3–5 | draft **zmienia** stan ilościowy |
| `create_document` | jeśli PZ: po flush → `_create_pz_draft_layers(doc, today)` |
| `_create_pz_draft_layers` | **nowa** — INSERT warstwa price=NULL, upsert_balance +qty |
| `_post_pz` | lookup warstwy; UPDATE `purchase_unit_price`; walidacja ceny + opcjonalnie `source_invoice_id`; **bez** INSERT; **bez** upsert_balance +qty |
| `_validate_items_for_type` (PZ) | usunąć wymóg `purchase_unit_price` przy create |
| `update_document` | jeśli PZ: sync warstw (delete/update/insert); blokada gdy `remaining < received` |
| `cancel_document` | jeśli PZ draft: usuń warstwy / zero qty; upsert_balance −qty; blokada częściowego rozchodu |
| `_consume_fifo` | snapshot: `layer.purchase_unit_price` jeśli NOT NULL else NULL (wymaga E1 nullable snapshot) |

**Pominięte (minimal scope):** osobna walidacja FV zakupu w `_post_pz` — **zalecane** jako osobny minimalny commit w E4 jeśli biznes wymaga; audyt: pole `source_invoice_id` istnieje, brak walidacji.

## Kolejność commitów (dev)

```
commit E4-a: warehouse: layer lookup by source document item
  - app/persistence/repositories/inventory_layer_repository.py

commit E4-b: warehouse: PZ draft creates FIFO layer; post updates cost only
  - app/services/warehouse_document_service.py

commit E4-c: tests: PZ draft stock semantics
  - tests/unit/test_warehouse_documents.py
```

Commity E4-a+b **w jednym PR**; E4-c zaraz po lub squash przed merge.

## Ryzyka

| Ryzyko | Poziom | Mitigacja |
|--------|--------|-----------|
| Podwójna warstwa przy post | **krytyczny** | E1 UNIQUE + `_post_pz` UPDATE-only |
| Posted PZ historyczne przy post ponownym | niski | Idempotencja no-op na POSTED |
| Update draft kasuje linie → osierocone warstwy | średni | Sync w `update_document` |
| WZ przed post PZ — NULL snapshot | średni | E1 nullable snapshot; akceptacja biznesowa |
| `_to_dec(None)` w starym `_consume_fifo` | **wysoki** | Zmiana w E4-b obowiązkowa przed pierwszym WZ na draft |

## Wpływ na istniejące testy

| Test | Obecne zachowanie | Po E4 |
|------|-------------------|-------|
| `test_create_draft_does_not_change_balance` | draft bez stanu | **FAIL** → zastąpić |
| `test_draft_does_not_change_balance` | j.w. | **FAIL** → usunąć/zastąpić |
| `test_update_draft_does_not_touch_inventory_layers` | brak warstw | **FAIL** → nowy test sync |
| `test_cancel_draft_does_not_change_balance` | brak cofnięcia | **FAIL** → test cofnięcia |
| `test_post_pz_increases_balance` | balance przy post | **zmiana** — balance przy create |
| `test_post_pz_creates_inventory_layer` | warstwa przy post | **zmiana** — warstwa przy create |
| `test_pz_create_validates_purchase_price_required` | cena wymagana | **FAIL** → test opcjonalnej ceny |
| Wszystkie TestWZ / TestKK używające `_setup_stock` via post | OK | Dostosować helper: create+post lub create draft z warstwą |

Testy WZ/FIFO/numeracja — **większość bez zmian** jeśli `_setup_stock` nadal robi post (warstwa z ceną).

## Testy do aktualizacji / dodać (E4)

### Zastąpić / usunąć

- `TestPZ.test_create_draft_does_not_change_balance`
- `TestDocumentStatuses.test_draft_does_not_change_balance`
- `TestDraftEditAndCancel.test_update_draft_does_not_touch_inventory_layers`
- `TestDraftEditAndCancel.test_cancel_draft_does_not_change_balance`
- `TestPZ.test_pz_create_validates_purchase_price_required` → odwrócić asercję

### Zmodyfikować

- `TestPZ.test_post_pz_increases_balance` → balance już po create; post nie zwiększa
- `TestPZ.test_post_pz_creates_inventory_layer` → warstwa po create; post tylko cena
- `TestPZ.test_post_pz_sets_catalog_vat_rate` — nadal przy post (OK)

### Dodać (nowe)

- `test_create_pz_draft_creates_layer_without_price`
- `test_create_pz_draft_increases_balance`
- `test_post_pz_updates_layer_price_not_quantity`
- `test_post_pz_does_not_duplicate_layer`
- `test_post_pz_requires_purchase_price`
- `test_cancel_pz_draft_reverses_layer_and_balance`
- `test_cancel_pz_draft_blocked_after_partial_wz`
- `test_update_pz_draft_syncs_layer_quantity`
- `test_update_pz_draft_blocked_after_partial_wz`
- `test_wz_consumes_draft_pz_layer_before_post`
- `test_wz_movement_null_snapshot_when_layer_has_no_cost`

## Wdrożenie DS723+ (E4)

```bash
git checkout <TAG_E4_E5>
cd frontend-react && npm ci && npm run build && cd ..
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --build --force-recreate api worker
curl -fsS http://127.0.0.1:8000/health
pytest  # lokalnie przed tagiem; na prod smoke manual
```

**Smoke po E4:**
1. Nowy PZ draft bez ceny → Stany (API) pokaże qty dopiero po E5 UI — curl `GET /warehouse/items/balance`
2. Post PZ z ceną → ta sama warstwa, cena uzupełniona
3. WZ schodzi z qty

---

# Etap E5 — API balance + frontend magazynu

## Cel

Stany: ilość z warstw draft; wartość netto tylko gdy cena ≠ NULL; formularz PZ: cena opcjonalna w draft, wymagana przy księgowaniu.

## Pliki do zmiany

| Plik | Zmiana |
|------|--------|
| `app/services/warehouse_item_service.py` | `_balance_entry_from_row`: `unit_price_net` i `value_net` opcjonalne; `cost_pending: bool` lub `source_document_number` null dla draft |
| `app/schemas/warehouse_item.py` | `WarehouseBalanceEntryResponse`: `unit_price_net: Decimal \| None`, `value_net: Decimal \| None`, `cost_pending: bool = False` |
| `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx` | `validateForm`: cena opcjonalna dla draft PZ; osobna walidacja przy akcji „Zaksięguj” (jeśli jest) |
| `frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx` | agregacja: suma qty zawsze; suma value tylko wiersze z ceną; UI „koszt nieustalony” |
| `frontend-react/src/pages/warehouse/WarehousePage.module.css` | opcjonalnie klasa badge draft/cost-pending — **reuse** istniejących `.badgeDraft` |

**Bez zmian:** router API (response z schema wystarczy).

## Kolejność commitów (dev)

```
commit E5-a: warehouse balance API: optional cost on draft layers
  - app/schemas/warehouse_item.py
  - app/services/warehouse_item_service.py
  - tests/unit/test_warehouse_balance_layers.py
  - tests/unit/test_warehouse_items.py

commit E5-b: warehouse UI: PZ draft optional price; balance cost pending
  - frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx
  - frontend-react/src/pages/warehouse/tabs/BalanceTab.jsx
  - (opcjonalnie) WarehousePage.module.css
```

E5-a **przed** E5-b; oba w tym samym tagu co E4 na prod.

## Ryzyka

| Ryzyko | Poziom | Mitigacja |
|--------|--------|-----------|
| `_balance_entry_from_row(None)` TypeError | **wysoki** | E5-a przed pierwszym draft bez ceny w prod |
| Frontend dist nie odświeżony | średni | `npm run build` przed up (DS723 checklist) |
| Agregacja BalanceTab dzieli przez zero | niski | warunek `price != null` |

## Wpływ na istniejące testy

| Plik | Testy |
|------|-------|
| `test_warehouse_balance_layers.py` | `test_maps_row_to_layer_response` — rozszerzyć o wiersz NULL price |
| `test_warehouse_items.py` | `test_two_pz_same_item_returns_two_balance_rows` — może wymagać draft layer w helperze |
| `test_warehouse_documents.py` | brak bezpośredni — po E4 |

## Testy do aktualizacji / dodać (E5)

- `test_balance_entry_null_price_sets_cost_pending` (nowy)
- `test_balance_entry_null_price_value_net_is_none` (nowy)
- `test_list_balance_layers_includes_draft_pz_without_value` (nowy)
- `TestBalanceEndpointLayers` — dostosować mock rows z NULL price
- Frontend: brak unit testów w scope — smoke manual DocumentsTab + BalanceTab

## Wdrożenie DS723+ (E5)

```bash
cd /volume1/docker/ifg/ifg_standalone/frontend-react
npm ci && npm run build
cd ..
docker compose -f docker/docker-compose.prod.yml --env-file .env.production \
  up -d --force-recreate api
# UI: http://IP:8000/ui → Magazyn → Stany, Dokumenty
```

**Smoke po E5:**
- PZ draft bez ceny → zapis OK, Stany pokazuje qty, wartość „—”
- Post PZ → wartość się pojawia
- Stary posted PZ → bez regresji wizualnej

---

## Mapa commitów end-to-end (repo dev)

```text
E1-a   schema nullable + unique index
E2-a   backfill script
E3-a   verify SQL (optional)
E4-a   layer repository lookup
E4-b   warehouse_document_service PZ semantics
E4-c   test_warehouse_documents.py
E5-a   balance API + tests balance/items
E5-b   frontend DocumentsTab + BalanceTab
```

**Tag release prod:** po merge E1–E5-b, np. `vX.Y.Z-pz-draft-stock`.

---

## Harmonogram jednego okna maintenance (DS723+)

| Min | Etap | Działanie |
|-----|------|-----------|
| T+0 | E0 | Komunikat; opcjonalnie stop worker |
| T+5 | E0 | `pg_dump` backup |
| T+15 | E1 | `alembic upgrade head` |
| T+20 | E2 | backfill `--dry-run` → `--execute` |
| T+35 | E3 | `verify_pz_draft_backfill.sql` — STOP jeśli fail |
| T+40 | E4+E5 | `git pull` tag; `npm run build`; `docker compose up --build --force-recreate api worker` |
| T+55 | smoke | curl health; PZ draft; post; WZ; Stany UI |
| T+60 | | Koniec okna; włączenie worker |

---

## Macierz ryzyk zbiorcza E1–E5

| Etap | Ryzyko dominujące | Poziom |
|------|-------------------|--------|
| E1 | duplikaty przed UNIQUE | średni |
| E2 | backfill + post na starym kodzie | **krytyczny** |
| E3 | pominięcie gate | **krytyczny** |
| E4 | podwójna warstwa / desync update-cancel | **wysoki** |
| E5 | API crash na NULL price | **wysoki** |

**Ryzyko całości E1–E5:** **wysokie** — akceptowalne wyłącznie w jednym oknie z E3 gate i backup.

**Złożoność całości E1–E5:** **średnia–wysoka** — logika skupiona w jednym serwisie, ale wiele testów i ścisła kolejność operacji na prod.

---

## Checklist przed startem implementacji

- [ ] SQL prod: liczba draft PZ (§ Produkcja)
- [ ] Backup restore przetestowany na kopii
- [ ] Jeden PR / tag obejmujący E1+E2 skrypt+E4+E5
- [ ] Okno maintenance uzgodnione (60–90 min)
- [ ] Po wdrożeniu: query E3-3 przez 48h (balance vs layers)
