# GWO-IFG-STOCK-0002D — Plan jawnego przepływu Faktura → dokument magazynowy

**Status:** PLAN ONLY (nie implementować w 0002C)  
**Zależność:** GWO-IFG-STOCK-0002C (`invoice_items.warehouse_item_id`)  
**Model kanoniczny:** WAREHOUSE_CANONICAL (`warehouse_items` + `warehouse_documents` + FIFO)  
**Data:** 2026-08-04

## 1. Cel Etapu 2

Dodać **jawną** akcję użytkownika:

- „Utwórz WZ z faktury sprzedaży”
- „Utwórz PZ z faktury zakupu”

Bez automatycznego postowania przy `InvoiceService.create()` / `update()`.

## 2. Kontrakt odkryty w IFG (faktyczny)

| Element | Stan |
|--------|------|
| `warehouse_documents.source_invoice_id` | Istnieje (nullable FK → `invoices`) |
| Tworzenie WZ/PZ z FV | **Ręczne** przez UI dokumentów (`DocumentsTab`) + opcjonalne `source_invoice_id` |
| Automatyczne PZ/WZ przy FV | **Brak** (po 0002C odłączony też legacy stock hook) |
| Relacja 1:1 `source_invoice_id`+`doc_type` | **NIE** wymuszona UNIQUE — możliwe wiele dokumentów na jedną FV |
| Mapowanie pozycji FV → kartoteka | Po 0002C: `invoice_items.warehouse_item_id` |
| FIFO / post | `WarehouseDocumentService.create_document` (draft) + `post_document` |

## 3. Decyzje do rozstrzygnięcia w implementacji 0002D

### 3.1 Akcje UI

- Przycisk na szczegółach faktury sprzedaży: **Utwórz WZ**.
- Przycisk na szczegółach faktury zakupu: **Utwórz PZ**.
- Ukryć / disabled gdy brak pozycji z `warehouse_item_id` (tylko usługi/ręczne → komunikat).
- Nie używać `stockApi` / `products`.

### 3.2 Draft vs posted

**Rekomendacja:** tworzyć dokument jako **DRAFT**, potem osobny „Zaksięguj”.

Uzasadnienie:

- zgodne z istniejącym kontraktem PZ draft (warstwy ilościowe bez kosztu do postu),
- pozwala skorygować ilości przed ruchem FIFO,
- unika dublowania przy pomyłce.

### 3.3 Kontrola istniejących dokumentów (`source_invoice_id`)

Przed create:

1. Wyszukaj `warehouse_documents` gdzie `source_invoice_id = invoice.id` i `doc_type` zgodny.
2. Jeśli istnieją:
   - pokaż listę (numer, status),
   - domyślnie **blokuj** kolejne create z opcją „Utwórz mimo to” (świadome 1:N),
   - albo nawiguj do istniejącego draftu.

**Nie wprowadzać UNIQUE(source_invoice_id, doc_type)** dopóki produktowo nie potwierdzimy relacji 1:1.

### 3.4 Relacja 1:1 vs 1:N

| Scenariusz | Semantyka |
|------------|-----------|
| Pełne wydanie / przyjęcie | Preferowane 1 dokument / typ / FV |
| Częściowe WZ/PZ | 1:N uzasadnione |
| Korekta magazynowa | Osobny KK, nie drugi WZ „z FV” bez decyzji |

**Rekomendacja startowa:** soft 1:1 (ostrzeżenie + potwierdzenie), hard UNIQUE dopiero po GWO decyzyjnym.

### 3.5 Idempotencja

- Endpoint: `POST /api/v1/invoices/{id}/warehouse-documents` z `doc_type` + opcjonalnym `Idempotency-Key`.
- Przy istniejącym draft powiązanym: zwrócić istniejący (opcjonalny query `reuse_existing=true`).
- Post dokumentu pozostaje idempotentny (już w serwisie).

### 3.6 Częściowe wydania / przyjęcia

- Domyślnie ilości = ilości z pozycji FV z niepustym `warehouse_item_id`.
- UI Etapu 2a: pełne ilości; Etap 2b: edytowalne ilości ≤ pozostałej do wydania/przyjęcia.
- Tracking residual: suma `warehouse_document_items.quantity` dla `source_invoice_id` vs FV (follow-up; wymaga `invoice_item_id` na pozycji dokumentu — patrz §5).

### 3.7 Oversell (WZ)

- Post WZ już rzuca `InsufficientStockError` (FIFO).
- Przy create draft: opcjonalny soft-check stanu (`warehouse_balance`) z ostrzeżeniem, bez blokady draftu.
- Hard block tylko na post (bez zmian polityki FIFO).

### 3.8 Ceny i koszt PZ

- FV zakupu: `unit_price_net` pozycji FV → `purchase_unit_price` na pozycji PZ (draft może mieć NULL koszt do postu — respektować istniejący kontrakt PZ draft).
- FV sprzedaży → WZ: ceny sprzedaży z FV jako `unit_price_net` pozycji WZ; koszt FIFO z warstw przy post.

### 3.9 Anulowanie faktury

- Anulowanie / usunięcie FV **nie kasuje** historii FIFO ani POSTED dokumentów.
- Draft WZ/PZ z `source_invoice_id`: orphan policy — zostaw draft + ostrzeżenie albo wymuś odpięcie `source_invoice_id` (SET NULL już na FK dokumentów).
- Zakaz hard-delete POSTED.

### 3.10 Korekty (KOR)

- Osobna ścieżka: nie generować automatycznie WZ/PZ z KOR w 0002D v1.
- Follow-up: korekta ilości → KK lub nowe dokumenty z linkiem do korekty.

### 3.11 Edycja pozycji FV po utworzeniu dokumentu

- Jeśli istnieje dokument DRAFT: przy edycji FV pokazać warning „Dokument magazynowy wymaga synchronizacji”.
- Jeśli POSTED: edycja FV nie zmienia magazynu; ewentualna korekta tylko przez KK / nowy dokument.
- Nie synchronizować automatycznie w tle.

### 3.12 Zakaz kasowania historii FIFO

- Bez delete warstw / movements.
- Bez „cofnij post” usuwającego historię — tylko kompensata (KK / przeciwny dokument) wg istniejącego modelu.

### 3.13 Import KSeF

- Faktura zakupowa z KSeF = dokument księgowy, **nie** potwierdzenie fizycznego przyjęcia.
- `warehouse_item_id` może być NULL po imporcie; użytkownik mapuje ręcznie, potem jawnie „Utwórz PZ”.
- Żadnego auto-PZ w workerze sync.

## 4. Proponowany przepływ techniczny

```
Invoice (sale/purchase)
  └─ UI: Utwórz WZ/PZ
       ├─ precheck source_invoice_id + doc_type
       ├─ filter items where warehouse_item_id IS NOT NULL
       ├─ WarehouseDocumentService.create_document(
       │     doc_type, source_invoice_id=invoice.id,
       │     items=[{item_id: warehouse_item_id, qty, prices…}]
       │   ) → DRAFT
       └─ (opcjonalnie) navigate → dokument; post osobno
```

Granice transakcji: osobna transakcja od create faktury; nie wywoływać z `InvoiceService.create`.

## 5. Follow-upy schematu (poza 0002C)

Dodawać **tylko** gdy semantyka 1:1 / partials jest potwierdzona:

1. `warehouse_document_items.invoice_item_id` (nullable FK) — śledzenie częściowych wydań.
2. UNIQUE(`source_invoice_id`, `doc_type`) — **tylko** po decyzji produktowej 1:1.
3. Backfill historycznych FV → `warehouse_item_id` (ISBN/name match) — osobny GWO.

## 6. Testy wymagane w 0002D

- Create WZ z FV sale z FK; brak auto przy samym zapisie FV.
- Create PZ z FV purchase.
- Precheck istniejącego dokumentu.
- Oversell na post WZ.
- KSeF purchase bez FK → brak create / komunikat.
- Brak zapisu do `stock_movements`.
- Brak kasowania FIFO.

## 7. Kryteria gotowości do startu 0002D

- [x] 0002C: FK `warehouse_item_id` E2E
- [ ] Review ChatGPT / LOCAL_REVIEW 0002C
- [ ] Decyzja: draft-only vs draft+optional post
- [ ] Decyzja: soft vs hard 1:1
- [ ] Makiety UI przycisków na fakturze
