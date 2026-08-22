# GWO-IFG-STOCK-0002A — Rozstrzygnięcie kanonicznego modelu magazynu IFG

**Data:** 2026-08-04  
**Repo kanoniczne:** `~/projekty/ifg_standalone` (`ifg.git`)  
**Źródło analizy (fork):** `~/projekty/program-do-faktur` @ `31c64ea`  
**Produkcja:** read-only; **brak implementacji i deployu**

Powiązane:  
- `docs/reports/2026-08-04_GWO-IFG-STOCK-0001_REPOSITORY_PRODUCTION_COMPATIBILITY_AUDIT.md`  
- `docs/gwo/GWO-IFG-STOCK-0002_BLOCKERS.md`  
- Plan portu: `docs/gwo/GWO-IFG-STOCK-0002B_CANONICAL_INVOICE_WAREHOUSE_PORT_PLAN.md`

---

## STATUS

**COMPLETE**

## VERDICT

**B. WAREHOUSE_CANONICAL**

Źródłem prawdy stanu magazynowego IFG jest tor **`warehouse_items` + `warehouse_documents` + `warehouse_balance` + warstwy FIFO (`inventory_layers`)**.

Tor **`products` / `stock` / `stock_movements`** jest **legacy / MVP równoległy** (API+StockPage nadal pod `ENABLE_WAREHOUSE`), **nie** jest używany w aktywnym przepływie faktury i **nie** powinien stać się drugim źródłem prawdy przy porcie `31c64ea`.

---

## CANONICAL REPOSITORY

`github.com/lukaszwyszom-creator/ifg.git` → lokalnie `~/projekty/ifg_standalone`  
Produkcja: `DS723+:/volume1/docker/ifg_v2/ifg_standalone`

`program-do-faktur` = historyczny fork; commit `31c64ea` = **źródło analizy / selektywnego portu logiki**, nie obiekt do pull/cherry-pick na prod.

---

## FAZA 1 — Inwentaryzacja modeli

### A. Stock (`products`, `stock`, `stock_movements`, `StockService`)

| Kryterium | Stan |
|-----------|------|
| Przeznaczenie | Prosty stan ilościowy + ruchy PURCHASE/SALE/ADJUSTMENT/TRANSFER |
| API | `app/api/routers/stock.py` — products, stock, movement, history |
| Frontend | `StockPage` nadal w `App.jsx`; **Sidebar** prowadzi wyłącznie do `/warehouse` („Magazyn”) |
| Feature flag | Włączany razem z warehouse (`ENABLE_WAREHOUSE`) |
| Multi-warehouse | Tak (tabela `warehouses` + `warehouse_id`) |
| FIFO | **Nie** |
| Powiązanie z FV | Hook `handle_invoice_created` + `invoice_id` na ruchu; **brak** `product_id` na `InvoiceItem` → w praktyce **martwe** |
| Idempotencja FV | Brak (na poziomie item) |
| Korekty / anulowanie FV | Brak |
| Kompletność | MVP; TRANSFER semantycznie słaby (signed qty) |
| Testy | **Brak** dedykowanych testów stock↔invoice w IFG |

### B. Warehouse_* (katalog + dokumenty + FIFO)

| Kryterium | Stan |
|-----------|------|
| Przeznaczenie | Katalog towarów/usług, dokumenty PZ/WZ/KK, stany, FIFO |
| API | `warehouse_items`, `warehouse_documents` |
| Frontend | Pełny `WarehousePage` (Catalog / Documents / Balance) — **kanoniczny UX Magazyn** |
| Feature flag | `ENABLE_WAREHOUSE` |
| Multi-warehouse | Model dokumentów / balance (tor produkcyjny IFG) |
| FIFO | **Tak** (`InventoryLayer`, post WZ zdejmuje warstwy) |
| Powiązanie z FV | `warehouse_documents.source_invoice_id` (TRYB A WZ: FV = SoT cen/ilości); katalog używany w `InvoiceForm` (nazwa/ISBN/cena) **bez trwałego FK** |
| Idempotencja | Na poziomie dokumentów/warstw (draft/post), nie na `invoice_item` |
| Zakup / sprzedaż | PZ (przyjęcie), WZ (rozchód), KK± |
| Stan aktualny | `warehouse_balance` + warstwy |
| Testy | `test_warehouse_items`, `test_warehouse_documents`, `test_warehouse_balance_layers` |

### Ryzyko dwóch modeli

Obecnie **nie** ma aktywnego podwójnego zapisu FV→stock + FV→warehouse (stock hook jest pusty).  
Ryzyko powstanie, jeśli port `31c64ea` doda ruchy `stock_movements` **oraz** nadal będzie używany tor PZ/WZ — **zakazane** w tym werdykcie.

---

## FAZA 2 — Martwy hook

Kod (`InvoiceService.create` po zapisie):

```python
if self.stock_service is not None:
    self.stock_service.handle_invoice_created(
        ...
        items=[
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in saved.items
            if hasattr(item, "product_id")
        ],
    )
```

**Potwierdzenia:**

1. `InvoiceItem` (domain) i `InvoiceItemORM` **nie mają** atrybutu `product_id` (mają m.in. `isbn`, kwoty, `sort_order`).  
2. `hasattr(item, "product_id")` → **False** → lista items zawsze pusta → **żadne ruchy stock nie powstają** przy zapisie FV.  
3. Nawet gdyby `hasattr` było True bez pola w ORM, nie byłoby trwałego powiązania w DB.  
4. Testy IFG **nie** potwierdzają żywej integracji stock↔invoice; istnieją testy warehouse i osobno invoice.  
5. Usunięcie / zastąpienie hooka **jest wymagane** w porcie: zastąpić wywołaniem toru warehouse (lub usunąć do czasu implementacji).

---

## FAZA 3 — Klasyfikacja plików `31c64ea` (rodzic..commit)

| Plik | Klasyfikacja | Uzasadnienie |
|------|-------------|--------------|
| `alembic/...0011_k1l2...idempotency.py` | **ODRZUCIĆ — migracja forka** | Kolizja ID `k1l2`; DDL pod `products`/`stock_movements`, nie pod warehouse |
| `app/domain/models/invoice.py` (+`product_id`) | **PORT_LOGIKI_BEZ KOPIOWANIA** | W IFG: `warehouse_item_id` (nie `product_id`→products) |
| `app/domain/models/stock.py` (+`invoice_item_id`) | **ODRZUCIĆ — konflikt architektury** / ewentualnie later deprecation | Nie wzmacniać stock jako SoT |
| `app/persistence/models/invoice_item.py` | **PORT_LOGIKI_BEZ KOPIOWANIA** | Kolumna FK do `warehouse_items` |
| `app/persistence/models/stock.py` | **ODRZUCIĆ — konflikt** | |
| `app/persistence/mappers/invoice_mapper.py` | **PORT_LOGIKI_BEZ KOPIOWANIA** | Mapowanie nowego FK |
| `app/persistence/repositories/stock_repository.py` | **ODRZUCIĆ / NIE PORT** | Idempotencja ma żyć przy dokumentach warehouse |
| `app/schemas/invoice.py` | **PORT_LOGIKI_BEZ KOPIOWANIA** | |
| `app/schemas/stock.py` (reject TRANSFER) | **ODRZUCIĆ lub osobny cleanup** | TRANSFER stock nie jest tematem warehouse FIFO |
| `app/services/invoice_service.py` | **PORT_LOGIKI_BEZ KOPIOWANIA** | Zastąpić martwy hook orchestracją PZ/WZ |
| `app/services/stock_service.py` (idempotencja, reverse) | **PORT_LOGIKI_BEZ KOPIOWANIA** (wzorce) | Przenieść *zachowania*: oversell, atomowość, idempotencja — do `WarehouseDocumentService` / nowego orchestratora |
| `InvoiceForm.jsx` + CSS (picker stock products) | **ODRZUCIĆ — konflikt UX** | IFG już ma picker `warehouseItemsApi`; należy **utrwalić ID katalogu**, nie podmieniać na `products` |
| `StockPage.jsx` (hide TRANSFER) | **ODRZUCIĆ / cleanup legacy** | Poza ścieżką kanoniczną Magazyn |
| `tests/...invoice_stock_integration.py` | **WYMAGA NOWEGO PROJEKTU W IFG** | Przepisać na warehouse + PostgreSQL |
| `tests/...invoice_mapper.py` | **PORT_BEZPOŚREDNI_PO_ADAPTACJI** | Po zmianie nazwy pola |

### Ocena zachowań z PDF

| Zachowanie | Werdykt w IFG |
|------------|---------------|
| Trwałe powiązanie pozycji z produktem | **TAK** → `warehouse_item_id` |
| Auto ruch przy FV | **TAK** → dokument PZ/WZ (nie `stock_movements`) |
| Usługa bez produktu | **TAK** → `warehouse_item_id=null` / pozycja nie-warehouse |
| Oversell + rollback FV | **TAK** → post WZ FIFO musi failować w tej samej transakcji co commit FV (lub jawny 2-phase z dokumentacją) |
| Idempotencja | **TAK** → unique na powiązaniu FV↔dokument (np. `(source_invoice_id, doc_type)`) +/lub `invoice_item_id` na pozycji dokumentu |
| TRANSFER stock | **ODRZUCIĆ** |
| Kopiowanie migracji `k1l2` | **ODRZUCIĆ** |
| Picker produktu stock | **ODRZUCIĆ** (zastąpione już katalogiem warehouse) |

---

## FAZA 4 — Decyzja architektoniczna (rekomendowany wariant)

### Werdykt: **WAREHOUSE_CANONICAL**

| Temat | Decyzja |
|-------|---------|
| Źródło prawdy stanu | `warehouse_balance` + `inventory_layers` (FIFO) |
| Katalog produktu | `warehouse_items` |
| Relacja InvoiceItem → produkt | **`invoice_items.warehouse_item_id`** NULL FK → `warehouse_items.id` |
| Relacja FV → dokument | Istniejące `warehouse_documents.source_invoice_id`; wzmocnić idempotencję i opcjonalnie `warehouse_document_items.invoice_item_id` |
| PURCHASE | FV `direction=purchase` + pozycje z `warehouse_item_id` → dokument **PZ** (draft/post wg reguł IFG) powiązany z FV |
| SALE | FV `direction=sale` → dokument **WZ** (post) zdejmujący FIFO |
| Usługa | `warehouse_item_id=null` lub item `is_warehouse_active=false` → **bez** dokumentu/warstwy |
| Idempotencja | Nie dublować PZ/WZ dla tej samej FV; unique / lookup po `source_invoice_id`+typ |
| Oversell | Istniejąca walidacja FIFO przy post WZ; błąd → rollback całej transakcji FV+dokument |
| Edycja FV | Bez „update in place” ruchów; reverse/korekta dokumentami (KK) lub zakaz edycji pozycji magazynowych po zaksięgowaniu (jak create-only w PDF) — do dopięcia w 0002B |
| Anulowanie | Dokument odwracający / KK; **nie** kasować historii warstw |
| Korekty | Tor KK± już w warehouse |
| Import KSeF | Pozycje bez `warehouse_item_id` → brak auto-dokumentu (oczekiwane); przyszłe mapowanie osobnym GWO |
| Zgodność danych | Stare FV bez FK pozostają ważne; brak backfill obowiązkowy |
| Stock tables | **Freeze** wobec FV; osobne GWO deprecacji UI/API stock (nie w 0002B implementacji minimalnej) |
| Zakaz | Równoległy zapis do `stock_movements` i `warehouse_*` dla tego samego zdarzenia FV |

### Dlaczego nie STOCK_CANONICAL / CONSOLIDATION teraz

- FE i procesy biznesowe (PZ/WZ/FIFO, powiązanie WZ↔FV) już stoją na warehouse.  
- Konsolidacja stock→warehouse to osobny, duży projekt migracji danych; nie blokuje poprawnego portu FV↔warehouse.  
- Port `product_id`→`products` **utrwaliłby** dualizm względem katalogu używanego w formularzu FV.

---

## FAZA 5 — Projekt migracji (tylko projekt; **nie uruchamiać**)

**Uwaga:** `revision` musi być **nowy**; przykład roboczy (do weryfikacji względem head w chwili implementacji):

- Przykładowa nazwa pliku: `q7r8s9t0u1v2_invoice_item_warehouse_item_link.py`  
- `down_revision = "p6q7r8s9t0u1"` **lub aktualny `alembic heads` IFG w momencie brancha**  
- **Zakaz** reuse `k1l2m3n4o5p6`

### DDL (propozycja minimalna)

1. `invoice_items.warehouse_item_id UUID NULL`  
   - FK → `warehouse_items.id`  
   - `ON DELETE RESTRICT` (produkt użyty na FV nie do twardego delete; deaktywacja katalogu już istnieje)  
   - index `ix_invoice_items_warehouse_item_id`

2. Opcjonalnie (zalecane dla idempotencji pozycji):  
   `warehouse_document_items.invoice_item_id UUID NULL`  
   - FK → `invoice_items.id` ON DELETE SET NULL  
   - UNIQUE `(invoice_item_id)` WHERE NOT NULL **lub** UNIQUE `(invoice_item_id, document_id)` wg wybranej semantyki

3. Opcjonalnie wzmocnienie dokumentu:  
   UNIQUE `(source_invoice_id, doc_type)` WHERE `source_invoice_id IS NOT NULL`  
   (jedna FV → max jeden PZ i jeden WZ auto)

### Precheck

- Brak ORPHAN: wszystkie nie-null `warehouse_item_id` istnieją w `warehouse_items`.  
- Stare faktury: NULL OK.  
- Brak destrukcyjnych DROP.

### Downgrade

Drop FK/index/columns w odwrotnej kolejności; bez kasowania dokumentów.

### Ryzyka

- Lock `invoice_items` przy ADD COLUMN (PostgreSQL zwykle szybki dla NULL).  
- Unique na `(source_invoice_id, doc_type)` może kolidować z **istniejącymi** wieloma WZ do jednej FV — **wymagany precheck COUNT** przed unique; jeśli >1, najpierw cleanup/reguła wyjątków.

### Test migracji

Na kopii schematu PostgreSQL IFG (dump z `/volume1/docker/ifg_v2/backups/`), nie na preview PDF.

---

## FAZA 6 — Gotowość implementacyjna

Plan wykonywalny: **`GWO-IFG-STOCK-0002B_CANONICAL_INVOICE_WAREHOUSE_PORT_PLAN.md`**.  
Implementacja i deploy: **poza** tym GWO; osobny gate.

---

## PRODUCTION MODIFIED

**NO**

## DEPLOY EXECUTED

**NO**

## NEXT ACTION

Uruchomić GWO implementacyjne wg 0002B na branchu `ifg` (port logiki + nowa migracja + testy), bez deployu DS723 do czasu osobnego GWO deploy.

## Decyzje dla ChatGPT

Brak blokujących — werdykt **WAREHOUSE_CANONICAL** jest rekomendacją wiążącą do 0002B.  
Opcjonalnie potwierdzić: czy auto-post WZ/PZ przy `invoice.created`, czy tylko trwały FK + ręczne/dokumentowe księgowanie z walidacją powiązania (0002B zakłada **auto-dokument w tej samej transakcji** jako domyślny target zachowania z PDF).

## Wygenerowane raporty

- ten dokument  
- `docs/gwo/GWO-IFG-STOCK-0002B_CANONICAL_INVOICE_WAREHOUSE_PORT_PLAN.md`
