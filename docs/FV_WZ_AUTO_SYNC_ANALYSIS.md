# Analiza: FV sprzedaży a ruchy magazynowe (WZ)

**Data:** 2026-06-19  
**Zakres:** `invoice_service.py`, `warehouse_document_service.py`, modele `warehouse_document` / `inventory_layer`  
**Uwaga:** `warehouse_posting_service.py` **nie istnieje** w repozytorium.

---

## 1. Czy zatwierdzenie FV sprzedaży tworzy automatycznie WZ?

**Nie.**

`InvoiceService` nie importuje ani nie wywołuje `WarehouseDocumentService`. W analizowanym pliku brak odniesień do `warehouse`, `WZ`, `source_invoice_id`.

Przepływ FV sprzedaży w `invoice_service.py`:

| Moment | Co się dzieje | WZ / magazyn V1 |
|--------|----------------|-----------------|
| `create_invoice()` | status `READY_FOR_SUBMISSION`, numer lokalny, audit | opcjonalnie `stock_service.handle_invoice_created()` — **legacy Stock**, nie magazyn FIFO |
| `mark_as_ready()` / `_assign_number_local()` | nadanie `number_local` | brak |
| `update_invoice()` | edycja pozycji | brak |
| `delete_sale_invoice()` | usunięcie | brak |

Jedyna integracja „magazynowa” w `create_invoice`:

```python
if self.stock_service is not None:
    self.stock_service.handle_invoice_created(
        invoice_id=saved.id,
        direction=saved.direction,
        items=[
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in saved.items
            if hasattr(item, "product_id")
        ],
    )
```

To dotyczy starego modułu `StockService` (`product_id`), **nie** warstw `inventory_layers` ani dokumentów `warehouse_documents`.

Ruch magazynowy FIFO powstaje wyłącnie przez **`WarehouseDocumentService.post_document()`** po ręcznym utworzeniu PZ/WZ/KK (API magazynu).

---

## 2. Gdzie powinno powstawać WZ?

Architektura magazynu V1 (komentarze w `warehouse_document_service.py`) zakłada **Tryb A**:

> WZ z FV: `source_invoice_id` ustawione; **FV jest source of truth** cen/ilości.

Logiczne miejsca hooka (poza obecnym zakresem plików, do decyzji produktowej):

| Wariant | Trigger | Uzasadnienie |
|---------|---------|--------------|
| **A (zalecany)** | Po `post_document(WZ)` utworzonym z FV | Stan schodzi dopiero przy księgowaniu WZ — spójne z PZ |
| **B** | Przy `create_invoice` / `mark_as_ready` FV sale | Wcześniejsza rezerwacja — wymaga osobnej logiki rezerwacji (brak w modelu) |
| **C** | Po statusie `ACCEPTED` (KSeF) | Wydanie dopiero po formalnym zatwierdzeniu — wymaga hooka w ścieżce transmisji |

**Minimalna implementacja zgodna z obecnym modelem:**

1. Nowa metoda w `WarehouseDocumentService` (np. `create_wz_from_invoice(invoice_id)`) — buduje draft WZ z pozycji FV, ustawia `source_invoice_id`.
2. Wywołanie + `post_document()` z jednego miejsca w cyklu życia FV (np. po nadaniu numeru / po ACCEPTED).
3. Mapowanie pozycji FV → `warehouse_items` (ISBN / powiązanie kartoteki — **poza analizowanymi plikami**, wymagane do działania).

Obecnie WZ powstaje **tylko ręcznie** przez UI/API magazynu (`create_document` + opcjonalnie `post_document`).

---

## 3. Czy istnieje mechanizm powiązania `source_invoice_id` → WZ?

**Częściowo — tylko infrastruktura, bez automatyzacji.**

### Model `WarehouseDocumentORM`

- Pole `source_invoice_id` → FK `invoices.id` (nullable, indeks).
- Brak UNIQUE na `(source_invoice_id, doc_type)` — DB nie blokuje wielu WZ do jednej FV.

### `WarehouseDocumentService`

- `create_document()` **zapisuje** `source_invoice_id` z body requestu.
- `_validate_doc_header()` dla WZ: jeśli brak `source_invoice_id`, wymaga `issue_reason` (tryb B — WZ ręczny).
- `_post_wz()`: przy `source_invoice_id` **nie wymaga** `issue_reason`; wykonuje FIFO (`_consume_fifo` → `InventoryLayerMovementORM`).

### Czego brakuje

- Brak metody `get_by_source_invoice_id()` w serwisie/repozytorium (w analizowanym kodzie).
- Brak tworzenia WZ z FV.
- Brak odwrotnego linku na `Invoice` (FV nie wie, czy ma WZ).
- `inventory_layers` wiążą się z **pozycją dokumentu magazynowego** (`warehouse_document_items`), nie z fakturą bezpośrednio.

---

## 4. Czy możliwy jest bezpieczny backfill istniejących FV?

**Tak, warunkowo** — wymaga reguł idempotencji i audytu, nie jest możliwy „ślepy” backfill.

### Warunki bezpieczeństwa

| Ryzyko | Mitigacja |
|--------|-----------|
| Podwójne zdjęcie stanu | Przed backfill: `EXISTS (WZ POSTED WHERE source_invoice_id = invoice.id)` → pomiń |
| Ręczne WZ bez `source_invoice_id` dla tej samej sprzedaży | Backfill tylko dla FV **bez** powiązanego WZ; opcjonalnie heurystyka daty/ pozycji (poza scope) |
| Brak stanu magazynowego | `post_document` rzuci `InsufficientStockError` — FV do ręcznej weryfikacji |
| Brak mapowania pozycji FV → kartoteka | Pozycje bez `warehouse_item_id` pomijać lub mapować po ISBN |
| FV anulowane / korekty | Backfill tylko `direction=sale`, status końcowy; korekty osobna ścieżka (KK) |

### Idempotencja

- `post_document()` jest idempotentny **per dokument** (drugi POST = no-op).
- Brak globalnej idempotencji „1 FV = max 1 WZ” na poziomie DB — **zalecany** unikalny partial index `(source_invoice_id) WHERE doc_type='WZ' AND status='posted'` przy wdrożeniu.

### Rekomendowany backfill (koncepcja)

1. Dla każdej FV sprzedaży bez WZ z `source_invoice_id`.
2. Utwórz draft WZ + pozycje z FV.
3. `post_document()` w transakcji; przy błędzie stanu — log + raport wyjątków.
4. **Nie** backfillować FV, dla których już istnieje ręczny WZ (nawet bez linku) bez review.

---

## 5. Ile zmian wymaga wdrożenie automatycznego WZ przy FV?

Szacunek **minimalnego** wdrożenia (MVP, bez pełnego Magazyn V1):

| # | Plik / element | Zakres |
|---|----------------|--------|
| 1 | `warehouse_document_service.py` | `create_wz_from_invoice()`, ewent. `get_wz_for_invoice()` |
| 2 | `warehouse_document_repository.py` | query po `source_invoice_id` |
| 3 | Hook cyklu FV | `invoice_service.py` **lub** serwis transmisji/KSeF przy ACCEPTED — **1 plik** |
| 4 | Mapowanie FV item → `warehouse_item` | helper (ISBN) — **1 plik** |
| 5 | Migracja Alembic (opcjonalna, zalecana) | UNIQUE partial index na WZ↔FV |
| 6 | Testy jednostkowe | 2–3 pliki testów |
| 7 | Skrypt/komenda backfill | 1 plik (opcjonalnie) |

**Razem: ~6–8 plików** (+ migracja, + testy).  
Sam hook w `invoice_service` to **2–3 pliki backend** jeśli mapowanie i repozytorium już istnieją; pełne MVP z idempotencją i backfill: **~8 plików**.

Bez mapowania pozycji FV na kartotekę magazynową feature **nie zadziała** mimo dodania hooka.

---

## Werdykt

Istniejące FV sprzedaży **nie generują ruchów magazynowych**, ponieważ:

1. `InvoiceService` nie tworzy dokumentów magazynowych.
2. `WarehouseDocumentService` obsługuje WZ z FV **tylko gdy** ktoś ręcznie utworzy WZ z `source_invoice_id` i zaksięguje go.
3. Legacy `StockService` (jeśli włączony) to osobny model, nie FIFO `inventory_layers`.
4. Brak `warehouse_posting_service` — księgowanie jest w `post_document()` w `warehouse_document_service.py`.

**Raport:** `docs/FV_WZ_AUTO_SYNC_ANALYSIS.md`
