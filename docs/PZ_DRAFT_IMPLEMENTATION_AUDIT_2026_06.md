# Audyt kodu vs plan PZ draft jako stan magazynowy

**Data:** 2026-06-19  
**Podstawa planu:** [`docs/PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md`](PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md)  
**Zakres audytu:** wyłącznie wskazane pliki (bez implementacji, bez refaktoru).

---

## Pliki przeanalizowane

| Plik w zleceniu | Status | Uwaga |
|-----------------|--------|-------|
| `app/services/warehouse_document_service.py` | istnieje | główna logika PZ/WZ/FIFO |
| `app/persistence/models/inventory_layer.py` | istnieje | model warstw i ruchów |
| `app/persistence/models/warehouse_balance.py` | **nie istnieje** | model `WarehouseBalanceORM` jest w `app/persistence/models/warehouse_document.py` (linie 110–129); `upsert_balance` w `app/persistence/repositories/warehouse_document_repository.py` |
| `app/repositories/inventory_layer_repository.py` | **nie istnieje** | faktyczna ścieżka: `app/persistence/repositories/inventory_layer_repository.py` |
| `app/services/warehouse_item_service.py` | istnieje | API balance (warstwy) |
| `tests/unit/test_warehouse_documents.py` | istnieje | testy kontraktu obecnego modelu |

---

## 1. Czy założenia planu wdrożenia są nadal aktualne?

**Tak — w 100%.** Kod nie wprowadził żadnej zmiany w kierunku „PZ draft = stan magazynowy”. Plan operacyjny (E0–E7, backfill, nullable cena, okno maintenance) pozostaje **w pełni aktualny i konieczny**.

| Założenie planu | Stan kodu (2026-06) | Zgodność |
|-----------------|---------------------|----------|
| PZ draft zwiększa ilość | `create_document` explicite **nie** zmienia stanu | ❌ do zrobienia (E4) |
| PZ posted tylko uzupełnia koszt | `_post_pz` **tworzy** warstwę + balance +qty | ❌ do zrobienia (E4) |
| Koszt nullable do post | `purchase_unit_price` NOT NULL w modelu i DB | ❌ do zrobienia (E1) |
| Backfill draft PZ przed nowym kodem | brak skryptu / logiki backfill w kodzie | ❌ do zrobienia (E2) |
| UNIQUE `source_document_item_id` | brak w repozytorium i modelu | ❌ do zrobienia (E1) |
| WZ schodzi z warstw draft | warstw przy draft **nie ma** — WZ widzi tylko post PZ | ❌ blokada do E4 |
| Idempotencja post | drugi `post` = no-op dla POSTED | ✅ częściowo (chroni przed duplikatem przy **drugim** post, nie przy przejściu draft→post z backfillem) |
| Blokada sprzedaży / auto-WZ | poza analizowanymi plikami | ❌ nie zaimplementowane (E6–E7) |

**Wniosek:** plan wdrożenia nie wymaga zmiany kierunku — wymaga **realizacji od zera** w analizowanym zakresie.

---

## 2. Gdzie tworzona jest warstwa FIFO dla PZ?

**Jedynie w `_post_pz()`**, wywoływanym z `post_document()` gdy `doc_type == 'PZ'`.

```227:248:app/services/warehouse_document_service.py
    def _post_pz(self, doc: WarehouseDocumentORM, today: date) -> None:
        for item in doc.doc_items:
            ...
            layer = InventoryLayerORM(
                id=uuid4(),
                item_id=item.item_id,
                source_document_item_id=item.id,
                ...
                remaining_quantity=qty,
                purchase_unit_price=price,
                ...
            )
            self.layer_repo.add_layer(layer)
            self.doc_repo.upsert_balance(item.item_id, qty)
```

`create_document()` (linie 142–172) zapisuje tylko `WarehouseDocumentORM` + `WarehouseDocumentItemORM` — **zero** wywołań `layer_repo.add_layer`.

Komentarz modułu (linie 3–5) i docstring `create_document` (linia 143) potwierdzają: draft nie dotyka magazynu.

**KK+** tworzy warstwy analogicznie w `_post_kk()` (linie 303–315) — poza zakresem PZ, bez zmian w planie PZ.

---

## 3. Czy post PZ tworzy nowe warstwy czy aktualizuje istniejące?

**Tworzy nowe warstwy (INSERT)** — zawsze `InventoryLayerORM(...)` + `add_layer()`. Brak:

- wyszukiwania warstwy po `source_document_item_id`,
- UPDATE `purchase_unit_price` / `remaining_quantity` na istniejącej warstwie,
- guarda „warstwa już istnieje”.

Idempotencja `post_document` (linie 186–188) dotyczy wyłącnie dokumentu **już POSTED** — nie rozwiązuje scenariusza backfill + post na tym samym draft PZ (ryzyko podwójnej warstwy opisane w planie).

---

## 4. Czy `purchase_unit_price` jest nullable czy NOT NULL?

### Model ORM

```43:44:app/persistence/models/inventory_layer.py
    # purchase_unit_price — cena zakupu; NIEZMIENNA po zaksięgowaniu
    purchase_unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
```

**NOT NULL** na warstwie. Komentarz zakłada niezmienność po zaksięgowaniu — sprzeczne z docelowym UPDATE ceny przy post po draft.

### Ruch WZ

```80:81:app/persistence/models/inventory_layer.py
    purchase_unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
```

**NOT NULL** — `_consume_fifo` zawsze zapisuje `_to_dec(layer.purchase_unit_price)` (linia 354); przy NULL na warstwie kod **nie obsłuży** tego dziś.

### Linia dokumentu PZ

W `_build_item_orm` cena na linii może być `None` (linie 84–87), ale `_validate_items_for_type` dla PZ **wymusza** `purchase_unit_price` przy create (linie 476–481).

**Podsumowanie:** warstwa i snapshot — NOT NULL; linia dokumentu — nullable w ORM, wymagana walidacją przy create PZ.

---

## 5. Jak liczony jest `warehouse_balance`?

Model (w `warehouse_document.py`, nie w osobnym pliku):

```118:121:app/persistence/models/warehouse_document.py
    # quantity_available — READ MODEL / cache dla UI.
    # ŹRÓDŁEM PRAWDY jest suma inventory_layers.remaining_quantity.
    # TODO: zaimplementować recalculate_balance(item_id) ...
```

### Aktualizacja (z `warehouse_document_service.py`)

Przyrost/dekrement **delta**, nie przeliczenie z warstw:

| Operacja | Wywołanie | Delta |
|----------|-----------|-------|
| post PZ | `_post_pz` | `+qty` |
| post WZ | `_post_wz` | `−qty` |
| post KK+ | `_post_kk` | `+qty` |
| post KK− | `_post_kk` | `−qty` |

`create_document`, `update_document`, `cancel_document` — **nie** wywołują `upsert_balance`.

### Odczyt stanu w API balance

`WarehouseItemService.list_balance_layers()` (linie 86–120) czyta **wyłącznie `inventory_layers`** z `remaining_quantity != 0` — **nie** używa tabeli `warehouse_balance`.

Wartość netto w `_balance_entry_from_row` (linie 123–144):

```python
value_net = qty * price  # zawsze; brak obsługi price=NULL
```

**Niespójność znana:** cache `warehouse_balance` vs suma warstw — TODO w modelu; plan E2/E3 (recalculate / query 4.3) nadal aktualny.

---

## 6. Zabezpieczenia przed duplikacją warstw

| Mechanizm | Obecny stan | Skuteczność dla planu PZ draft |
|-----------|-------------|--------------------------------|
| Idempotencja `post_document` (POSTED → no-op) | ✅ linie 186–188 | Chroni tylko **powtórny** post tego samego posted |
| UNIQUE `source_document_item_id` | ❌ brak | Plan E1 — **nie wdrożone** |
| `get_layer_by_source_document_item_id` | ❌ brak w `InventoryLayerRepository` | Plan E4 — **nie wdrożone** |
| `_post_pz` — lookup przed insert | ❌ zawsze INSERT | **Brak** |
| Test `test_second_post_is_noop` | ✅ 1 warstwa po 2× post | Nie obejmuje draft+backfill+post |

**Wniosek:** jedyna realna ochrona to no-op na już zaksięgowanym dokumencie. **Brak ochrony** przed duplikatem warstwy dla jednej linii PZ — plan E1 (UNIQUE) + zmiana `_post_pz` na UPDATE są **krytyczne** przed wdrożeniem.

---

## 7. Co z planu jest już wykonane w kodzie?

### Zrealizowane (infrastruktura wspólna — nie specyficzna dla PZ draft)

| Element | Lokalizacja | Znaczenie dla planu |
|---------|-------------|---------------------|
| Pole `source_document_item_id` na warstwie | `inventory_layer.py` L32–36 | Gotowe pod 1:1 linia PZ ↔ warstwa |
| `upsert_balance(item_id, delta)` | wywoływane z `_post_pz/_post_wz/_post_kk` | Mechanizm cache — do użycia przy create draft |
| FIFO `get_available_fifo` po `remaining_quantity > 0` | `inventory_layer_repository.py` L19–28 | Algorytm bez zmian (plan OK) |
| `_consume_fifo` + `InsufficientStockError` | `warehouse_document_service.py` L325–340 | WZ po E4 będzie mógł schodzić z warstw draft |
| Idempotencja post (no-op) | L186–188 | Do zachowania |
| `_assert_mutable` / immutability POSTED | L114–126, testy L615–637 | Bez zmian |
| Walidacja ilości całkowitej PZ/WZ/KK | L464–504 | Bez zmian |
| Testy FIFO, WZ tryb A/B, numeracja | `test_warehouse_documents.py` | Baza regresji — wymaga rozszerzenia, nie usunięcia |

### Niewykonane (całość E1–E5 w analizowanym zakresie)

- Migracja nullable `purchase_unit_price` (E1)
- Backfill draft PZ (E2)
- `create_document(PZ)` → warstwa + balance (E4)
- `_post_pz` → UPDATE zamiast INSERT (E4)
- Sync warstw w `update_document` / `cancel_document` (E4)
- Opcjonalna cena przy create PZ (E4)
- Wymóg FV zakupu przy post PZ (E4 — plan biznesowy, brak w kodzie)
- `get_layer_by_source_document_item_id` (E4)
- Obsługa NULL w `_balance_entry_from_row` / Stany (E5)
- Nowe testy z planu §6 E4 (E4)

Etapy E6 (blokada FV) i E7 (auto-WZ) — **poza** analizowanymi plikami; **0%** w tym audycie.

---

## 8. Co w planie wymaga korekty (nieaktualne / nieprecyzyjne)

| Punkt planu | Problem | Korekta |
|-------------|---------|---------|
| Ścieżka `app/repositories/inventory_layer_repository.py` | plik nie istnieje | **`app/persistence/repositories/inventory_layer_repository.py`** |
| Ścieżka `app/persistence/models/warehouse_balance.py` | plik nie istnieje | model: **`warehouse_document.py`** (`WarehouseBalanceORM`); logika upsert: **`warehouse_document_repository.py`** |
| Plan E4: „repozytorium `get_layer_by_source_doc_item`” | metoda nie istnieje | nadal **do dodania** — nie „już jest” |
| Plan zakłada `recalculate_balance` | TODO w modelu, brak implementacji | E2/E3 nadal wymagają skryptu/SQL; nie można polegać na metodzie w repo |
| Test planu: „zastępuje `test_create_draft_does_not_change_balance`” | test **nadal obowiązuje** i przechodzi na obecnym kodzie | przy implementacji E4 test **musi** zostać zastąpiony — plan poprawny, ale audyt potwierdza: **nic nie zastąpiono** |
| `test_update_draft_does_not_touch_inventory_layers` (L733–741) | dokumentuje **obecne** zachowanie | po E4 test stanie się **fałszywy** — plan powinien explicite wymienić ten test obok `test_cancel_draft_does_not_change_balance` |
| `test_cancel_draft_does_not_change_balance` (L789–796) | to samo | j.w. — do zmiany w E4 |
| Post PZ wymaga FV zakupu (`source_invoice_id`) | w `_post_pz` brak walidacji FV; pole istnieje na nagłówku dokumentu | plan biznesowy OK; implementacja **dodatkowa** — nie mylić z obecnym kodem |
| `_consume_fifo` + NULL price | `_to_dec(None)` → błąd | plan E1/E4 musi **poprzedzić** WZ na warstwach bez ceny — kolejność etapów w planie poprawna |
| API balance vs `warehouse_balance` | plan mówi o balance ogólnie | doprecyzować: **UI Stany** idzie z warstw (`list_balance_layers`), tabela `warehouse_balance` to cache aktualizowany tylko przy **post** — po E4 create draft musi też aktualizować cache |

**Plan nie wymaga zmiany kolejności E0→E7.** Wymaga doprecyzowania ścieżek plików i rozszerzenia listy testów do zastąpienia o `TestDraftEditAndCancel` (update/cancel).

---

## 9. Macierz: plan vs kod (skrót)

| Obszar | Plan (docelowo) | Kod (dziś) | Gap |
|--------|-----------------|------------|-----|
| Moment warstwy PZ | create draft | post PZ | **krytyczny** |
| post PZ | UPDATE ceny | INSERT warstwy | **krytyczny** |
| `purchase_unit_price` | NULL do post | NOT NULL | **bloker E1** |
| Duplikaty warstw | UNIQUE + lookup | brak | **wysokie ryzyko wdrożenia** |
| cancel/update draft | sync warstw | tylko status / linie | **średni** |
| Balance API | qty bez ceny, value opcjonalnie | qty × price zawsze | **E5** |
| Testy | nowy kontrakt draft=stan | stary kontrakt draft≠stan | **do przebudowy** |

---

## 10. Ocena ryzyka wdrożenia (stan przed implementacją)

| Kategoria | Ocena | Uzasadnienie |
|-----------|-------|--------------|
| **Ogólna gotowość kodu** | **WYSOKA** (ryzyko) | Zero implementacji PZ draft; wdrożenie bez E1–E3 grozi podwójnym stanem |
| **Zgodność planu z kodem** | **NISKA** (ryzyko) | Plan trafnie opisuje obecny stan — nic nie jest „już zrobione” poza infrastrukturą FIFO |
| **Ryzyko regresji posted PZ/WZ** | **ŚREDNIA** | Zmiana `_post_pz` musi zachować idempotencję i nie dotykać historycznych warstw |
| **Ryzyko danych prod (draft bez warstw)** | **WYSOKA** | Backfill E2 obowiązkowy; bez niego drafty „na magazynie” biznesowo nie istnieją w FIFO |
| **Ryzyko NULL w balance API** | **ŚREDNIA** | `_balance_entry_from_row` nie obsłuży NULL bez E5 |

### Ocena końcowa audytu: **WYSOKA**

Wdrożenie jest **bezpieczne wyłącznie** według planu etapowego (maintenance window, E1→E2→E3 przed E4). Próba wdrożenia samego E4 bez migracji i backfillu = **podwójne warstwy i rozjechany balance**.

---

## 11. Rekomendacje operacyjne (bez refaktoru)

1. **Nie wdrażać częściowego E4** — create warstw przy draft bez zmiany `_post_pz` = gwarantowany duplikat przy post.
2. **E1 (nullable + UNIQUE) przed jakimkolwiek backfillem** — UNIQUE blokuje przypadkowy double-insert.
3. **Zaktualizować plan:** ścieżki plików (§8) + lista testów do wymiany: `test_create_draft_does_not_change_balance`, `test_update_draft_does_not_touch_inventory_layers`, `test_cancel_draft_does_not_change_balance`, `test_draft_does_not_change_balance`.
4. **Przed E5:** `_balance_entry_from_row` — guard na `purchase_unit_price IS NULL` (inaczej TypeError/Decimal error po E1).
5. **Po E4:** uruchomić query spójności z planu §4.3 — `recalculate_balance` nadal ręczny/SQL.

---

## Podsumowanie jednym zdaniem

Kod nadal realizuje model **„stan tylko po post PZ”**; plan wdrożenia PZ draft jako rzeczywistego stanu jest **w pełni aktualny**, a **żaden z kluczowych kroków E1–E5 nie został rozpoczęty** w analizowanych plikach — ryzyko wdrożenia bez ścisłej kolejności planu oceniamy jako **wysokie**.
