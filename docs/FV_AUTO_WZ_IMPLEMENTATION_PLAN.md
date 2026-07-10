# Plan wdrożenia: Automatyczne WZ przy FV sprzedaży

**Data:** 2026-06-19  
**Podstawa:** `docs/FV_WZ_AUTO_SYNC_ANALYSIS.md`  
**Zakres:** projekt — bez kodu, bez migracji w tym dokumencie

---

## Cel

Po zatwierdzeniu FV sprzedaży system automatycznie tworzy i księguje WZ (Tryb A: `source_invoice_id` ustawione, FV = source of truth ilości i cen netto), schodząc ze stanów FIFO bez ręcznej pracy w Magazyn → Dokumenty.

---

## 1. Miejsce w cyklu życia FV

### Rekomendacja: **ACCEPTED (KSeF)** — hook w ścieżce zmiany statusu na `accepted`

| Moment | Ocena | Uzasadnienie |
|--------|-------|--------------|
| `create_invoice` | **Odrzucone** | FV od razu `ready_for_submission`, ale jest **edytowalna** i możliwa do usunięcia; zdjęcie stanu przy zapisie draftu byłoby przedwczesne i trudne do cofnięcia bez KK. |
| `mark_as_ready` | **Odrzucone** | Tylko nadaje `number_local`; FV nadal przed wysyłką do KSeF, może wrócić do edycji / odrzucenia. |
| **`ACCEPTED` (KSeF)** | **Wybrane** | Faktura **formalnie zatwierdzona** — wydanie towaru jest uzasadnione biznesowo i prawnie. Spójne z Trybem A (FV jako źródło prawdy). |
| Inne (np. pierwsze `SENDING`) | **Nie** | Wysłanie ≠ akceptacja; retry/reject wymagałyby skomplikowanego rollbacku WZ. |

### Dokładny punkt integracji

**Plik docelowy hooka:** serwis obsługujący przejście FV → `accepted` (np. `TransmissionService` / `KSeF sync` — miejsce, gdzie dziś ustawiany jest status po pozytywnej odpowiedzi KSeF).

**Sekwencja (jedna transakcja biznesowa, dwie domeny):**

1. FV przechodzi na `accepted` (istniejąca logika).
2. Jeśli `direction == 'sale'` i magazyn włączony (`enable_warehouse`):
   - wywołanie `WarehouseDocumentService.ensure_posted_wz_for_invoice(invoice_id)` (nazwa robocza).
3. Przy `InsufficientStockError` lub błędzie mapowania:
   - **FV pozostaje accepted** (KSeF nie cofamy),
   - WZ nie powstaje / zostaje draft + wpis w logu/audit + flaga do ręcznej obsługi (patrz § ryzyka).

**Dlaczego nie w `invoice_service.py` bezpośrednio:** zmiana statusu na `accepted` nie przechodzi przez `mark_as_ready` ani `create_invoice`; hook musi być tam, gdzie faktycznie kończy się transmisja KSeF.

**Opcja konfiguracyjna (faza 2):** feature flag `AUTO_WZ_ON_INVOICE_ACCEPTED=true` w settings — umożliwia wyłączenie na prod przed backfillem.

---

## 2. Mapowanie pozycji FV → `warehouse_items`

### Kolejność dopasowania (od najpewniejszego)

| Priorytet | Klucz | Reguła |
|-----------|-------|--------|
| **1** | **`isbn`** | Normalizacja formatu `xxx-xx-xxxxxx-x-x` (jak w kartotece). Dopasowanie do `warehouse_items.isbn` gdzie `is_active=true` i `is_warehouse_active=true`. |
| **2** | **`item_id`** (opcjonalnie, faza 2) | Jeśli w przyszłości pozycja FV zapisze `warehouse_item_id` przy wyborze z kartoteki w `InvoiceForm` — użyć wprost, bez ISBN. **MVP: tylko ISBN** (pole już jest na pozycji FV). |
| **3** | **Pominięcie pozycji** | Usługi (`item_type=service`), pozycje bez ISBN, brak trafienia w kartotece — **nie wchodzą do WZ**; reszta FV może iść na magazyn częściowo (patrz § walidacja). |

### Pola WZ budowane z FV (Tryb A)

Dla każdej zmapowanej pozycji:

| Pole WZ | Źródło FV |
|---------|-----------|
| `item_id` | `warehouse_items.id` z mapowania ISBN |
| `quantity` | `invoice_item.quantity` (całkowita, dodatnia) |
| `unit_price_net` | cena netto z linii FV (FV = source of truth) |
| `vat_rate` | stawka VAT z linii FV |
| `purchase_unit_price` | **null** (nie dotyczy WZ z FV) |

Nagłówek WZ:

| Pole | Wartość |
|------|---------|
| `doc_type` | `WZ` |
| `source_invoice_id` | `invoice.id` |
| `issue_reason` | **null** (Tryb A — wystarczy `source_invoice_id`) |
| `notes` | opcjonalnie: `number_local` FV + data |

### Walidacja przed `post_document`

- **Tryb strict (zalecany na start):** jeśli choć jedna pozycja FV z ISBN nie mapuje się na kartotekę → **całe WZ nie powstaje**, raport błędu (unikamy „cichego” pomijania towarów).
- **Tryb partial (faza 2):** tylko zmapowane pozycje — wymaga akceptacji biznesowej.

---

## 3. Zabezpieczenie przed podwójnym WZ

### Warstwa bazy (zalecana)

Partial unique index:

```text
UNIQUE (source_invoice_id)
WHERE doc_type = 'WZ' AND status IN ('draft', 'posted')
```

- Blokuje drugi WZ (draft lub posted) dla tej samej FV.
- `cancelled` WZ nie blokuje ponownej próby (np. po błędnym backfillu).

### Warstwa serwisu (obowiązkowa)

Metoda `ensure_posted_wz_for_invoice(invoice_id)`:

1. `SELECT` istniejący WZ po `source_invoice_id` + `doc_type='WZ'`, status ≠ `cancelled`.
2. Jeśli **posted** → return (idempotentność, no-op).
3. Jeśli **draft** → `post_document()` (idempotentny POST per dokument).
4. Jeśli brak → `create_wz_from_invoice()` + `post_document()`.

Całość w **jednej transakcji DB** z `SELECT … FOR UPDATE` na FV lub na wierszu WZ (zapobiega race przy równoległym sync KSeF).

### Warstwa operacyjna

- Audit log: `warehouse_document.auto_created_from_invoice` z `invoice_id`, `wz_id`.
- Monitoring: alert gdy ACCEPTED FV bez WZ posted po N minutach.

### Ręczne WZ bez `source_invoice_id`

- Backfill i auto-WZ **nie** eliminują ryzyka duplikatu z ręcznym WZ sprzed wdrożenia.
- Przed backfillem: ręczna weryfikacja listy 27 FV vs istniejące WZ (data, pozycje, ilości).

---

## 4. Bezpieczny backfill 27 historycznych FV

### Założenia

- 27 FV sprzedaży bez powiązanego WZ (`source_invoice_id IS NULL` w `warehouse_documents`).
- Backfill **jednorazowy**, po wdrożeniu kodu + migracji indexu, **przed** włączeniem auto-hooka na prod (lub z flagą off).

### Procedura (5 kroków)

**Krok 0 — inwentaryzacja (read-only)**

```text
Lista 27 FV: id, number_local, issue_date, status, pozycje (isbn, qty).
Lista WZ POSTED bez source_invoice_id w tym samym okresie — kandydaci na duplikat ręczny.
```

**Krok 1 — dry-run**

- Skrypt/komenda admin: dla każdej FV symuluje mapowanie ISBN → kartoteka, sprawdza dostępność stanu FIFO (`sum remaining_quantity`).
- Output: CSV `invoice_id | ok | missing_isbn | no_catalog_match | insufficient_stock | manual_wz_conflict`.

**Krok 2 — review biznesowy**

- Pozycje `manual_wz_conflict` — ręczna decyzja: pominąć FV lub powiązać istniejący WZ retroaktywnie (`UPDATE source_invoice_id`) **bez** ponownego `post`.
- Pozycje `insufficient_stock` — decyzja: KK+, PZ uzupełniający, lub WZ częściowy (faza 2).

**Krok 3 — wykonanie (transakcja per FV)**

Dla każdej zatwierdzonej FV:

1. Ponowny check: brak WZ z `source_invoice_id = invoice.id`.
2. `create_wz_from_invoice(invoice_id)`.
3. `post_document(wz_id)`.
4. Commit + audit.
5. Przy błędzie: rollback **tylko tej FV**, kontynuacja kolejnych.

**Krok 4 — weryfikacja**

- 27 FV → 27 WZ POSTED z `source_invoice_id` (lub udokumentowane wyjątki).
- Spot-check: `warehouse_balance` / warstwy FIFO vs oczekiwane ilości dla 2–3 tytułów.

**Krok 5 — włączenie auto-hooka**

- Feature flag ON na prod.
- Nowe FV accepted → WZ automatycznie.

### FV wyłączone z auto-backfillu

| Warunek | Działanie |
|---------|-----------|
| `direction != 'sale'` | pomiń |
| status ≠ `accepted` | pomiń (lub osobna polityka po review) |
| już istnieje WZ z `source_invoice_id` | pomiń |
| istnieje ręczny WZ POSTED tego samego dnia/pozycji | **ręczny review** |
| korekta / storno FV | poza scope MVP — osobny projekt (KK) |

---

## 5. Pliki wymagające zmian

### Backend — must have

| Plik | Zmiana |
|------|--------|
| `app/services/warehouse_document_service.py` | `create_wz_from_invoice()`, `ensure_posted_wz_for_invoice()`, mapowanie pozycji |
| `app/persistence/repositories/warehouse_document_repository.py` | `get_wz_by_source_invoice_id()`, ewent. lock |
| `app/services/invoice_warehouse_mapper.py` *(nowy, robocza nazwa)* | ISBN → `warehouse_item`, budowa body pozycji WZ |
| Serwis KSeF / transmisji *(1 plik — hook ACCEPTED)* | wywołanie `ensure_posted_wz_for_invoice` po `accepted` |
| `alembic/versions/…_unique_wz_per_invoice.py` | partial unique index |
| `app/core/config.py` lub settings | flaga `auto_wz_on_invoice_accepted` |

### Backend — testy

| Plik | Zakres |
|------|--------|
| `tests/unit/test_wz_from_invoice.py` *(nowy)* | mapowanie, idempotencja, duplicate guard |
| `tests/unit/test_warehouse_documents.py` | rozszerzenie o WZ z `source_invoice_id` + post |

### Backfill (jednorazowo)

| Plik | Zmiana |
|------|--------|
| `scripts/backfill_wz_from_invoices.py` *(nowy)* | dry-run + execute, CSV raport |

### Bez zmian w MVP

| Plik | Powód |
|------|-------|
| `invoice_service.py` | hook nie na create/mark_ready |
| `frontend-react/*` | proces w pełni backendowy |
| `inventory_layer` model | wystarczy istniejący `_post_wz` / `_consume_fifo` |

### Opcjonalnie (faza 2)

| Plik | Zmiana |
|------|--------|
| `app/schemas/invoice.py` + `InvoiceForm.jsx` | zapis `warehouse_item_id` na pozycji FV |
| Panel admin / lista FV | badge „brak WZ” dla accepted |

---

## Ryzyka i decyzje do akceptacji

| Ryzyko | Mitygacja |
|--------|-----------|
| ACCEPTED bez stanu magazynowego | strict mode → brak WZ + alert; nie blokujemy FV w KSeF |
| Duplikat z ręcznym WZ sprzed wdrożenia | review 27 FV + dry-run |
| Częściowe mapowanie ISBN | strict mode na start |
| Korekty FV | poza MVP; później WZ/KK od korekty |
| Legacy `StockService` | nie wyłączać w MVP bez analizy — może dublować logikę; rozważyć wyłączenie dla sale |

---

## Kolejność wdrożenia

1. Migracja partial unique index  
2. Repository + mapper + `warehouse_document_service`  
3. Testy jednostkowe  
4. Skrypt backfill dry-run na kopii prod / staging  
5. Backfill 27 FV (execute)  
6. Hook ACCEPTED + feature flag  
7. Weryfikacja na prod (1 nowa FV testowa)

---

## Odpowiedzi skrócone (checklist)

1. **Trigger:** `ACCEPTED` (KSeF), nie `create_invoice` ani `mark_as_ready`.  
2. **Mapowanie:** ISBN → `warehouse_items`; opcjonalnie `item_id` w fazie 2; pominięcie usług i nierozpoznanych pozycji (strict = fail całości).  
3. **Anty-duplikat:** partial UNIQUE + `ensure_posted_wz_for_invoice` idempotentny + FOR UPDATE.  
4. **Backfill 27 FV:** dry-run → review → per-FV transakcja → weryfikacja → włączenie hooka.  
5. **Pliki:** ~6–8 backend (+ migracja, skrypt backfill, 2 pliki testów); hook w serwisie transmisji/KSeF, nie w `invoice_service.create`.
