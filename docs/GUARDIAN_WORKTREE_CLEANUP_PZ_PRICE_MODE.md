# Guardian — cleanup worktree po CRLF / reset (PZ + price_mode)

**Data audytu:** 2026-06-17  
**Branch:** `production` @ `752992f` (Document KSeF retryable status stuck fix)  
**DS723+:** nie dotykane  
**Akcje wykonane:** tylko odczyt (`git status`, `git diff`); brak `add` / `commit` / `push` / `reset` / `clean`

---

## 1. `git status --short` (skrót)

### Zmodyfikowane (`M`) — 10 plików

| Plik |
|------|
| `app/api/deps.py` |
| `app/domain/enums.py` |
| `app/persistence/mappers/invoice_mapper.py` |
| `app/persistence/models/invoice.py` |
| `app/persistence/repositories/transmission_repository.py` |
| `app/services/invoice_number_policy.py` |
| `app/services/payment_service.py` |
| `frontend-react/src/api/invoices.js` |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` |
| `frontend-react/vite.config.js` |

### Nowe (`??`) — istotne dla PZ / price_mode

| Plik | Status |
|------|--------|
| `alembic/versions/e7f8a9b0c1d2_add_suggested_sale_price_mode.py` | untracked |
| `tests/unit/test_suggested_sale_price_mode.py` | untracked |
| `frontend-react/src/components/invoice/catalogItemLineFromWarehouse.js` | untracked |
| `frontend-react/src/components/invoice/catalogItemLineFromWarehouse.test.js` | untracked |
| `docs/SUGGESTED_SALE_PRICE_MODE_FIX.md` | untracked |
| `docs/PZ_CARTOTEKA_FV_PRICE_FIX.md` | untracked |

### Nowe (`??`) — poza zakresem PZ (szum worktree)

`docs/FV_*`, `docs/KSEF_PURCHASE_*`, `docs/KSEF_WORKER_*`, `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js`

---

## 2. Wykrywanie CRLF-only

| Metoda | Wynik |
|--------|--------|
| `git diff --numstat` | 10 plików: **add == del** (np. `229/229` deps.py) → typowy wzorzec EOL |
| `git diff -w --quiet <plik>` | exit **0** dla `app/api/deps.py` → **brak diff merytorycznego** |
| `git diff -w --numstat` | **pusty** dla wszystkich 10 plików `M` |
| `git diff --ignore-space-at-eol --name-only` | nadal listuje te same 10 plików (Git traktuje CRLF↔LF jako zmianę linii, nie „space-at-eol”) |

**Wniosek:** wszystkie 10 plików `M` to **wyłącznie końce linii (CRLF↔LF)** — brak zmian logicznych po ignorowaniu whitespace (`-w`).

### Lista CRLF-only (do ewentualnego `git restore`, po Twojej zgodzie)

1. `app/api/deps.py`
2. `app/domain/enums.py`
3. `app/persistence/mappers/invoice_mapper.py`
4. `app/persistence/models/invoice.py`
5. `app/persistence/repositories/transmission_repository.py`
6. `app/services/invoice_number_policy.py`
7. `app/services/payment_service.py`
8. `frontend-react/src/api/invoices.js`
9. `frontend-react/src/components/invoice/InvoiceActions.jsx`
10. `frontend-react/vite.config.js`

---

## 3. Kompletność vs raporty

### `docs/SUGGESTED_SALE_PRICE_MODE_FIX.md`

| Element | W worktree | Uwagi |
|---------|------------|--------|
| Migracja `e7f8a9b0c1d2` | ✅ untracked | OK |
| ORM `warehouse_item` | ❌ brak pola | reset → HEAD |
| ORM `warehouse_document_item` | ❌ brak pola | reset → HEAD |
| Schemas API | ❌ brak `suggested_sale_price_mode` | reset → HEAD |
| `warehouse_document_service` post→gross | ❌ brak | reset → HEAD |
| `DocumentsTab` wysyła `gross` | ❌ brak | reset → HEAD |
| `InvoiceForm` → helper | ❌ stara wersja inline | mapuje na `unit_price_net` |
| `catalogItemLineFromWarehouse.js` | ✅ untracked | niepodpięty do FV |
| Test backend | ✅ untracked | **nie przejdzie** bez serwisu/ORM |
| Test frontend | ✅ untracked (8 testów) | OK w izolacji |

### `docs/PZ_CARTOTEKA_FV_PRICE_FIX.md`

| Element | W worktree |
|---------|------------|
| `DocumentsTab` — kolumny PZ, `NORMATYWNA CENA…` | ❌ nadal „Cena suger.” |
| `WarehousePage.module.css` — `.pzItemsTable` | ❌ brak |
| `InvoiceForm` — gross + helper | ❌ stara logika netto |
| `warehouseItems.js` — komentarz mode | ❌ brak zmian vs HEAD |

---

## 4. Stan kodu źródłowego (HEAD + untracked)

- **Migracja Alembic:** tylko jako plik untracked — **nie w indeksie, nie na HEAD**.
- **Pola ORM / schemas / serwis PZ:** **utracone** w tracked files (zgodne z HEAD sprzed price_mode).
- **Frontend PZ UI:** **utracone** (DocumentsTab/CSS).
- **InvoiceForm:** `catalogItemToLineFields()` w HEAD — `suggested_sale_price` → `unit_price_net` (semantyka **netto**, bez `mode`).
- **Testy:** pliki untracked; backend test wymaga odtworzenia serwisu.

**Ryzyko:** sam untracked migration + test bez reszty kodu → **niespójny, niebezpieczny do deployu**.

---

## 5. Czy worktree jest bezpieczny?

| Aspekt | Ocena |
|--------|--------|
| DS723+ / dane prod | ✅ nie dotykane |
| CRLF szum | ⚠️ 10 plików `M` — noise, nie commitować razem z feature |
| Feature price_mode | 🔴 **niekompletny** po `reset --hard` |
| Deploy z tego stanu | 🔴 **niebezpieczny** |

**Ogólnie:** worktree jest **bezpieczny do dalszej pracy lokalnej**, o ile **nie deployujesz** i **nie commitujesz** CRLF-only razem z migracją bez odtworzenia kodu.

---

## 6. Minimalny plan odtworzenia (bez wykonania)

1. **Oczyść CRLF-only** (po zgodzie):  
   `git restore app/api/deps.py app/domain/enums.py …` (10 plików z listy §2).

2. **Odtwórz tracked changes** (jeden logiczny commit docelowo):
   - `app/persistence/models/warehouse_item.py`
   - `app/persistence/models/warehouse_document.py`
   - `app/schemas/warehouse_item.py`
   - `app/schemas/warehouse_document.py`
   - `app/services/warehouse_document_service.py`
   - `frontend-react/src/pages/warehouse/tabs/DocumentsTab.jsx`
   - `frontend-react/src/pages/warehouse/WarehousePage.module.css`
   - `frontend-react/src/components/invoice/InvoiceForm.jsx` (import helpera)
   - `frontend-react/src/api/warehouseItems.js`

3. **Dodaj untracked do tego samego commita** (po odtworzeniu):
   - migracja, testy, `catalogItemLineFromWarehouse.*`, docs.

4. **Weryfikacja przed commit:**
   ```bash
   pytest tests/unit/test_suggested_sale_price_mode.py tests/unit/test_warehouse_documents.py tests/unit/test_warehouse_items.py -q
   node --test frontend-react/src/components/invoice/catalogItemLineFromWarehouse.test.js
   cd frontend-react && npm run build
   ```

5. **Migracja na środowisku:** dopiero po pełnym commicie i review — **nie na DS723+** bez planu okna.

---

## 7. Zalecany następny krok

1. `git restore` na 10 plikach CRLF-only (czyści szum).  
2. Ręcznie / z Cursor **odtwórz brakujące 9 tracked plików** price_mode + PZ UI.  
3. Dopiero potem jeden commit + testy — **bez push** do czasu review.
