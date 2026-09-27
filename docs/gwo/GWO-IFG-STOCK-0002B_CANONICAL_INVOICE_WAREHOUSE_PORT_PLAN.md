# GWO-IFG-STOCK-0002B — Plan portu: faktura ↔ kanoniczny magazyn (warehouse_*)

**Status planu:** **READY_FOR_IMPLEMENTATION_GWO** (nie BLOCKED)  
**Podstawa:** werdykt **WAREHOUSE_CANONICAL** z  
`docs/reports/2026-08-04_GWO-IFG-STOCK-0002A_WAREHOUSE_DOMAIN_DECISION.md`

**Zakaz w tym dokumencie / w GWO implementacyjnym bez osobnego gate:**  
deploy DS723+, migracja na produkcji, cherry-pick `31c64ea`, kopiowanie migracji `k1l2m3n4o5p6`.

**Repo implementacji:** `~/projekty/ifg_standalone` (`ifg.git`)  
**Źródło zachowań (nie plików migracji):** `program-do-faktur` @ `31c64ea`

---

## 0. Cel biznesowo-techniczny

Utrwalić powiązanie pozycji faktury z pozycją katalogu magazynowego (`warehouse_items`) oraz **atomowo** tworzyć odpowiadający dokument magazynowy (PZ/WZ) w torze FIFO — **bez** zapisu do `stock_movements` jako drugiego źródła prawdy.

---

## 1. Gałąź

```bash
cd ~/projekty/ifg_standalone
git fetch origin
git checkout production   # lub aktualny kanoniczny branch roboczy IFG
git pull --ff-only origin production
git checkout -b gwo/ifg-stock-0002b-invoice-warehouse-port
# Potwierdź: alembic heads == oczekiwany parent migracji
```

Zarejestruj `PREV_HEAD` i `alembic heads` w raporcie GWO.

---

## 2. Port wyłącznie zaakceptowanych zachowań

### Brać (logika, nie kopiuj 1:1 plików PDF)

- Trwałe FK pozycji FV → produkt katalogu.  
- Pomiń usługi (`null`).  
- Auto księgowanie zakupu/sprzedaży w tej samej transakcji co zapis FV.  
- Oversell → błąd + rollback całości.  
- Idempotencja ponownego przetworzenia tej samej FV.  
- Brak kasowania historii warstw/dokumentów.

### Nie brać

- `product_id` → `products`.  
- `invoice_item_id` na `stock_movements`.  
- Migracja `k1l2…`.  
- Picker `stockApi.listProducts` (IFG ma już warehouse catalog).  
- Wzmacnianie `StockPage` / TRANSFER.  
- `reverse_invoice_stock_movements` na stock — zastąpić regułami KK/odwrócenia dokumentów warehouse.

### Usunąć / zastąpić w IFG

- Blok `hasattr(item, "product_id")` + `handle_invoice_created` stock w `InvoiceService`.

---

## 3. Nowa migracja (po aktualnym head IFG)

1. Sprawdź `alembic heads` na branchu (obecnie w drzewie: **`p6q7r8s9t0u1`** — **zweryfikuj ponownie** przed generacją).  
2. Utwórz **nowy** plik revision (unikatowy ID ≠ `k1l2…`).  
3. Zawartość zgodna z projektem w 0002A:  
   - `invoice_items.warehouse_item_id` NULL + FK RESTRICT + index  
   - (zalecane) `warehouse_document_items.invoice_item_id` NULL + FK SET NULL + unique  
   - (warunkowo) UNIQUE `(source_invoice_id, doc_type)` po **prechecku** duplikatów  
4. Napisz `downgrade()`.  
5. **Nie** uruchamiaj na prod; lokalnie: upgrade na kopii PG.

---

## 4. Domain / ORM / mapper / repository / services

### Domain + ORM + schemas + mapper

- `InvoiceItem.warehouse_item_id: UUID | None`  
- ORM + request/response schemas  
- Mapper round-trip  
- Walidacja: jeśli ustawione → `warehouse_items` istnieje; opcjonalnie odrzuć itemy nie-aktywne magazynowo przy FV towarowej

### Orchestrator (nowy lub rozszerzenie)

Np. `InvoiceWarehousePostingService` wywoływany z `InvoiceService` po `flush` faktury, **ta sama sesja SQLAlchemy**:

| direction | Dokument | Zachowanie |
|-----------|----------|------------|
| `sale` | WZ | Utwórz + **post** (FIFO); `source_invoice_id=invoice.id`; linie z itemów z `warehouse_item_id` |
| `purchase` | PZ | Utwórz (+ post kosztów wg reguł IFG / ceny z FV); `source_invoice_id` |
| item null | — | pomiń |

**Idempotencja:** jeśli dokument `(source_invoice_id, doc_type)` już istnieje → skip lub zwróć istniejący (bez drugiego postu).

**Oversell:** wyjątek z post WZ → propaguj jako błąd domenowy → rollback transakcji requestu (faktura nie commitowana).

### Repository

- Lookup dokumentów po `source_invoice_id` + typ.  
- Nie używać `StockRepository.find_movement_by_invoice_item` jako SoT.

---

## 5. API i frontend

### API

- Przyjmij `warehouse_item_id` na pozycji create invoice.  
- Zwróć pole w response.  
- Nie dodawaj endpointów stock „pod FV”.

### Frontend

- Rozszerz istniejący picker katalogu (`warehouseItemsApi` / `catalogItemToLineFields`):  
  - przy wyborze ustaw **`warehouse_item_id`** w stanie pozycji i w payloadzie;  
  - **nie** nadpisuj nazwy/opisu gdy użytkownik już wpisał (reguła z PDF);  
  - pokaż ISBN / jednostkę / (opcjonalnie) stan z balance API jeśli już dostępne.  
- Pozycja ręczna bez wyboru katalogu → `warehouse_item_id=null`.  
- **Nie** podmieniaj UI na `StockPage` products.

---

## 6. Testy jednostkowe

- Mapper: `warehouse_item_id` null/set.  
- Walidacja nieistniejącego ID.  
- Orchestrator: sale→WZ, purchase→PZ, skip usług.  
- Idempotencja drugiego wywołania.  
- Usunięcie martwego hooka stock (brak wywołań `StockService.handle_invoice_created` z create FV).

---

## 7. Testy integracyjne PostgreSQL

Minimum (odpowiednik S1–S8 z preview PDF, ale na warehouse):

1. PURCHASE z `warehouse_item_id` → PZ + wzrost balance/warstwy.  
2. SALE → WZ + spadek stanu FIFO.  
3. `warehouse_item_id=null` → brak dokumentu.  
4. Oversell → błąd, **brak** faktury i **brak** częściowego WZ.  
5. Reprocess / ponowny posting tej samej FV → brak duplikatu dokumentu.  
6. `source_invoice_id` / `invoice_item_id` poprawne.  
7. Współistnienie starych FV bez FK.  
8. (Regresja) ręczne dokumenty warehouse nadal działają.

---

## 8. Test migracji na kopii schematu IFG

1. Restore dump IFG (np. z `/volume1/docker/ifg_v2/backups/`) do lokalnego PG.  
2. `alembic upgrade head`.  
3. Sprawdź kolumny/FK/unique.  
4. `alembic downgrade -1` na kopii (opcjonalnie) + ponowny upgrade.  
5. Precheck SQL pod unique `(source_invoice_id, doc_type)`.

---

## 9. Scenariusze obowiązkowe (checklista GWO)

- [ ] PURCHASE  
- [ ] SALE  
- [ ] oversell + rollback  
- [ ] brak `warehouse_item_id`  
- [ ] idempotencja  
- [ ] import KSeF (pozycje bez FK → brak auto-dokumentu)  
- [ ] edycja / ponowny zapis: **zdefiniowana polityka** (rekomendacja v1: brak edycji pozycji magazynowych po create; jak PDF create-only)  
- [ ] usunięcie/anulowanie: v1 dokumentacja + KK/reverse w osobnym follow-up jeśli brak API cancel  
- [ ] stare dane bez FK  

---

## 10. Lokalny preview

- API + FE przeciwko lokalnej kopii PG ze schematem IFG po migracji.  
- Smoke UI: wybór z katalogu ustawia FK; zapis FV tworzy dokument widoczny w Magazyn → Dokumenty.  
- **Bez** DS723.

---

## 11. Zakaz deployu

GWO implementacyjne kończy się na:

- merge-ready branch / PR,  
- testy PASS,  
- raport `.md`,  
- **RELEASE STATE = LOCAL_REVIEW_REQUIRED** (lub READY_FOR_DEPLOY dopiero po review).

Kontrolowany deploy IFG = **osobne GWO** (po usunięciu blokerów z 0002 / nowy 0003 deploy), wyłącznie na runtime `ifg`.

---

## 12. Warunki gotowości do GWO deployu

- [ ] Branch zmergowany do kanonicznej gałęzi `ifg`  
- [ ] Migracja unikalna, parent = head IFG  
- [ ] Brak zapisu FV→`stock_movements`  
- [ ] Testy §7–§9 PASS  
- [ ] Precheck unique dokumentów PASS lub zaadresowany  
- [ ] Backup location potwierdzona: `/volume1/docker/ifg_v2/backups/`  
- [ ] Plan rollback (restore dump + revert commit) spisany  

---

## Kolejność prac implementacyjnych (checklist developera)

1. Branch + zapis head/alembic  
2. Migracja  
3. Domain/ORM/schema/mapper  
4. Orchestrator + podmiana hooka w `InvoiceService`  
5. FE: persist `warehouse_item_id`  
6. Testy unit → PG integration → migration copy  
7. Preview lokalny  
8. Raport GWO + lista wygenerowanych plików  
9. **Stop** — czekaj na GWO deploy  

---

## Ryzyka residualne

- Istniejące multi-WZ przy jednej FV vs unique constraint.  
- Semantyka PZ post (cena z FV zakupu) vs obecny flow draft warstw.  
- Stock UI nadal dostępne pod `/stock` — komunikat „legacy” / follow-up deprecacji.  
- Dirty worktree Mac IFG (archiwum docs / Guardian WIP) — nie mieszać z tym branchiem.

---

## RELEASE STATE (dla przyszłego raportu implementacji)

- [ ] LOCAL_REVIEW_REQUIRED  
- [ ] READY_FOR_DEPLOY  
- [ ] DEPLOYED_TO_DS723  
- [ ] PRODUCTION_VERIFIED
