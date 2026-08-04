# GWO-IFG-STOCK-0002C — IMPLEMENTACJA TRWAŁEGO POWIĄZANIA FAKTURA ↔ KANONICZNY MAGAZYN IFG — ETAP 1

**Data:** 2026-08-04  
**STATUS:** SUCCESS  
**VERDICT:** PASS — trwałe FK `InvoiceItem → WarehouseItem` E2E; zapis FV bez efektów magazynowych; martwy stock hook odłączony; produkcja nietknięta.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Identyfikatory

| Pole | Wartość |
|------|---------|
| BRANCH | `gwo/ifg-stock-0002c-invoice-warehouse-link` |
| PREV_HEAD | `5d07d6b148bf9f88dce12fadd44250a6b37b4268` |
| FINAL_HEAD | 3edcf9f1ebe35ee999ffcd83a7297fac8cc5147f |
| Worktree | `/Users/lukasz/projekty/ifg_standalone_gwo_0002c` (izolowany od dirty `production`) |
| Origin | `git@github.com:lukaszwyszom-creator/ifg.git` |
| ALEMBIC BEFORE | `p6q7r8s9t0u1` |
| ALEMBIC AFTER | `q7r8s9t0u1v2` |
| MIGRATION | `q7r8s9t0u1v2_invoice_items_warehouse_item_id.py` |
| PRODUCTION MODIFIED | NO |
| DEPLOY EXECUTED | NO |

## Preflight

- Kanoniczne repo: `~/projekty/ifg_standalone` (HEAD production = PREV_HEAD).
- Dirty worktree użytkownika (~200 wpisów docs/archive) **nietknięty**.
- Branch utworzony w izolowanym git worktree od czystego PREV_HEAD.
- Uwaga: checkout na macOS powoduje szum CRLF na części plików FE — do commita dodano wyłącznie pliki GWO.

## Kontrakt (Faza 1) — werdykt zgodny

| Temat | Odkrycie | Decyzja |
|-------|----------|---------|
| `InvoiceItem` | brak `product_id` / `warehouse_item_id` | dodano `warehouse_item_id: UUID \| None` |
| Picker FE | `warehouseItemsApi` + `catalogItemToLineFields` | rozszerzono o persist FK |
| Stock hook | `hasattr(product_id)` + `StockService.handle_invoice_created` | usunięty z `InvoiceService` i `deps` |
| `source_invoice_id` | istnieje; brak UNIQUE 1:1 | zachowane; jawny flow → 0002D |
| Auto PZ/WZ przy create FV | brak | **pozostaje brak** |
| ON DELETE warehouse_items | soft deactivate; hard delete | FK **RESTRICT** |

Brak sprzeczności wymagającej BLOCKED.

## Kontrakt `warehouse_item_id`

1. Kolumna `invoice_items.warehouse_item_id UUID NULL`.
2. FK → `warehouse_items.id` **ON DELETE RESTRICT**.
3. Indeks `ix_invoice_items_warehouse_item_id`.
4. Round-trip: API request → domain → ORM → DB → domain → API response.
5. `NULL` = usługa / pozycja ręczna / import KSeF bez mapowania.
6. Nie-null: musi istnieć i być `is_active=True` przy create/update.
7. Historyczna FV z później dezaktywowanym elementem: **GET czytelny**.
8. **Nie** używa `product_id` jako aliasu.

## Odłączenie stock hooka

- Usunięto blok `hasattr(item, "product_id")` + `handle_invoice_created` z `InvoiceService.create_invoice`.
- Usunięto parametr `stock_service` z konstruktora `InvoiceService`.
- `get_invoice_service` w `app/api/deps.py` nie wstrzykuje już `StockService`.
- Legacy router `/stock` pozostaje (ENABLE_WAREHOUSE) — poza ścieżką faktur.

## Potwierdzenie braku automatycznego PZ/WZ

- Create FV nie wywołuje `WarehouseDocumentService`.
- Testy PG: liczniki `warehouse_documents`, `warehouse_balance`, `inventory_layers`, `stock_movements` bez zmian po create FV.
- Smoke lokalny: `warehouse_documents=0`, `stock_movements=0` dla świeżej sesji testowej.

## Zmienione pliki

- `alembic/versions/q7r8s9t0u1v2_invoice_items_warehouse_item_id.py` **(new)**
- `app/domain/models/invoice.py`
- `app/persistence/models/invoice_item.py`
- `app/persistence/mappers/invoice_mapper.py`
- `app/schemas/invoice.py`
- `app/services/invoice_totals.py`
- `app/services/invoice_service.py`
- `app/api/deps.py`
- `scripts/seed_demo_april_2026.py`
- `scripts/smoke_gwo_0002c_preview.py` **(new)**
- `frontend-react/src/components/invoice/InvoiceForm.jsx`
- `frontend-react/src/components/invoice/InvoiceForm.module.css`
- `tests/unit/test_invoice_mapper.py`
- `tests/unit/test_invoice_warehouse_item_link.py` **(new)**
- `tests/integration/test_invoice_warehouse_item_postgres.py` **(new)**
- `docs/gwo/GWO-IFG-STOCK-0002D_EXPLICIT_INVOICE_WAREHOUSE_DOCUMENT_FLOW_PLAN.md` **(new)**
- `docs/reports/2026-08-04_GWO-IFG-STOCK-0002C_INVOICE_WAREHOUSE_LINK_IMPLEMENTATION.md` **(this)**

## Wyniki testów

### Unit (GWO + mapper)

```
tests/unit/test_invoice_warehouse_item_link.py + test_invoice_mapper.py → 33 passed
```

Zakres: NULL/set round-trip, schema API, totals build, dead stock hook not called, missing FK rejected.

### PostgreSQL integration (lokalny kontener `ifg-gwo-0002c-pg:55432`)

```
tests/integration/test_invoice_warehouse_item_postgres.py → 8 passed
```

Pokrycie: persist+reread, NULL, missing→rollback, RESTRICT delete, deactivate+read, no warehouse side-effects, manual PZ OK, purchase NULL (KSeF-style).

### Migracja

- `alembic upgrade head` na pustej kopii schematu IFG → `q7r8s9t0u1v2` **PASS**
- `downgrade p6q7r8s9t0u1` + ponowny `upgrade head` **PASS**
- `\d invoice_items` potwierdza FK `ON DELETE RESTRICT` + indeks

### Frontend build

```
npx vite build → PASS (967 modules)
```

Bundle zawiera `warehouse_item_id` / „Odłącz”.

### Lokalny preview smoke

```
DATABASE_URL=postgresql+psycopg://ifg:ifg_test@127.0.0.1:55432/ifg_gwo_0002c
python scripts/smoke_gwo_0002c_preview.py → SMOKE_OK
```

- FK zapisane i odczytane
- pozycja ręczna NULL
- brak zmiany `warehouse_balance` / brak `stock_movements` / brak auto dokumentów

Interaktywny przegląd UI (picker / reopen / clear) → **LOCAL_REVIEW_REQUIRED** (checklist poniżej).

### Regresja IFG (szersza)

- `test_invoice_*` + `test_warehouse_*` + domain: **264 passed**
- **6 failed** — preexisting na `production` HEAD (regex `number_local` / numbering regression); **nie wprowadzone przez 0002C** (potwierdzone na czystym `ifg_standalone`).

## Checklista UI (lokalny przegląd)

- [ ] Wybór pozycji katalogu ustawia badge „Katalog” i wysyła `warehouse_item_id`
- [ ] Ponowne otwarcie FV pokazuje powiązanie
- [ ] „Odłącz” / ręczna edycja nazwy czyści FK
- [ ] Pozycja ręczna bez FK zapisuje się
- [ ] Magazyn → Katalog / Dokumenty / Stany bez regresji
- [ ] Zapis FV nie tworzy PZ/WZ

## Ryzyka i otwarte decyzje Etapu 2

Zob. `docs/gwo/GWO-IFG-STOCK-0002D_EXPLICIT_INVOICE_WAREHOUSE_DOCUMENT_FLOW_PLAN.md`:

- draft vs auto-post,
- soft vs hard 1:1 `source_invoice_id`+`doc_type`,
- częściowe wydania (`invoice_item_id` na pozycji dokumentu),
- polityka KSeF ≠ przyjęcie towaru,
- oversell tylko na post WZ.

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Trwałe FK `invoice_items.warehouse_item_id` E2E (migracja, domain, ORM, API, FE payload).
- Stare FV z NULL pozostają zgodne.
- Martwy stock hook usunięty z toru create FV.
- Create FV nie pisze `stock_movements` i nie zmienia stanu kanonicznego magazynu.
- Testy PG + migracja + FE build + smoke PASS.
- Plan 0002D zapisany.
- Produkcja / DS723+ nietknięte.

### ⚠️ Znane problemy

- Preexisting failing unit tests (`number_local` message regex) na HEAD — poza zakresem.
- CRLF szum w worktree na nieskorelowanych plikach FE — nie commitowany.
- Pełny interaktywny UI review jeszcze do wykonania przez człowieka.

### ❌ Co nie działa

- Brak (krytyczne warunki SUCCESS spełnione).

## A. Root cause

IFG miał picker katalogu bez trwałego FK oraz martwy hook legacy stock (`product_id`), który nigdy nie działał na `InvoiceItem`. Brakowało kolumny i round-tripu do kanonicznego `warehouse_items`.

## B. Zmienione pliki

Patrz sekcja „Zmienione pliki”.

## C. Deploy

**NIE wykonano.** RELEASE STATE = LOCAL_REVIEW_REQUIRED. Brak push/merge bez przeglądu ChatGPT.

## D. Testy

Patrz sekcja „Wyniki testów” (dowody PASS).

## E. Następny krok

1. Przegląd ChatGPT / LOCAL_REVIEW (UI checklist).
2. Po akceptacji: osobne GWO deploy (migracja `q7r8s9t0u1v2`) — **nie** w tym GWO.
3. Implementacja Etapu 2 wg `GWO-IFG-STOCK-0002D_…`.

## Decyzje dla ChatGPT

1. Czy zaakceptować soft-1:1 (ostrzeżenie) zamiast UNIQUE na `source_invoice_id`+`doc_type` w 0002D?
2. Czy create WZ/PZ z FV ma zawsze kończyć jako DRAFT (rekomendacja), czy dopuścić opcjonalny natychmiastowy post?
3. Czy READY_FOR_DEPLOY po samym review kodu, czy wymagany najpierw interaktywny UI smoke na lokalnym preview?

## Wygenerowane raporty

- `docs/reports/2026-08-04_GWO-IFG-STOCK-0002C_INVOICE_WAREHOUSE_LINK_IMPLEMENTATION.md`
- `docs/gwo/GWO-IFG-STOCK-0002D_EXPLICIT_INVOICE_WAREHOUSE_DOCUMENT_FLOW_PLAN.md`
