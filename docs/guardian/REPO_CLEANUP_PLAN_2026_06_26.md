# Plan sprzątania worktree IFG — 2026-06-26

**Kontekst:** poprawka KSeF (NrRB w XML) jest już w HEAD `04ea2c9`.  
**Cel:** uporządkować worktree **bez** commitowania refaktoryzacji Guardiana.  
**Źródła:** `docs/guardian/REPO_AUDIT_2026_06_26.md`, `git status` (2026-06-26).

---

## 1. Pliki CRLF-only — bezpieczne `git restore`

`git diff -w` pusty — **tylko końce linii**, brak zmian logicznych:

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

**Dodatkowo restore (śledzony, ale w `.gitignore`):**

| Plik | Powód |
|------|-------|
| `frontend-react/dist/index.html` | `frontend-react/dist/` — nie commitować |

---

## 2. `frontend-react/src` — werdykt

| Plik | Werdykt |
|------|---------|
| `frontend-react/src/api/invoices.js` | **Tylko CRLF** — restore |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | **Tylko CRLF** — restore |
| `frontend-react/vite.config.js` | **Tylko CRLF** — restore |
| `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | **?? nieśledzony** — osobny feature (numeracja FV), **nie w commicie KSeF** |

**Brak realnych zmian merytorycznych w `frontend-react/src` w worktree.**

---

## 3. Nieśledzone raporty `docs/*.md` — warto zachować (commit docs)

### 3a. KSeF / bank account / sync (commit razem — temat bieżący)

| Plik | Status |
|------|--------|
| `docs/KSEF_METADATA_PAGINATION_ROOT_CAUSE.md` | ?? |
| `docs/KSEF_METADATA_PROBE_COMMANDS_2026_06.md` | ?? |
| `docs/KSEF_MISSING_PURCHASES_AFTER_2026_06_05.md` | ?? |
| `docs/KSEF_PAGINATION_COMMIT_STATE.md` | ?? |
| `docs/KSEF_PERMANENTSTORAGE_VS_INVOICING_TEST.md` | ?? |
| `docs/KSEF_PROD_RESUME_RETEST_2026_06.md` | ?? |
| `docs/KSEF_PROD_SYNC_VERIFICATION_2026_06.md` | ?? |
| `docs/KSEF_PURCHASE_METADATA_50_LIMIT_DIAG_2026_06_23.md` | ?? |
| `docs/KSEF_PURCHASE_MISSING_INVOICES_ROOT_CAUSE.md` | ?? |
| `docs/KSEF_PURCHASE_NO_NEW_INVOICES_DIAG_2026_06.md` | ?? |
| `docs/KSEF_PURCHASE_SYNC_BROKEN_DIAG_2026_06.md` | ?? |
| `docs/KSEF_PURCHASE_SYNC_PROGRESS_DIAG.md` | ?? |
| `docs/KSEF_PURCHASE_TOTALS_ZERO_FIX_IMPLEMENTATION.md` | ?? |
| `docs/KSEF_RESUME_AUDIT_2026_06.md` | ?? |
| `docs/KSEF_RESUME_VERIFICATION.md` | ?? |
| `docs/KSEF_WORKER_QUEUE_BLOCKING_ANALYSIS.md` | ?? |

### 3b. Zmodyfikowane docs (diff merytoryczny — commit)

| Plik | Status |
|------|--------|
| `docs/KSEF_METADATA_PAGINATION_FIX_2026_06_23.md` | M |
| `docs/KSEF_PURCHASE_SYNC_ADD_ISSUE_DATE_2026_06_23.md` | M |
| `docs/PURCHASE_PDF_BANK_ACCOUNT_FIX_2026_06_24.md` | M |

### 3c. Meta / housekeeping (opcjonalny osobny commit docs)

| Plik |
|------|
| `docs/REPO_HOUSEKEEPING_AUDIT_2026_06.md` |
| `docs/guardian/REPO_AUDIT_2026_06_26.md` |
| `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md` |

*(Już w HEAD, bez akcji: `docs/KSEF_BANK_ACCOUNT_*.md` — commit `04ea2c9`.)*

---

## 4. Czego NIE ruszać (w tym sprzątaniu)

| Obszar | Pliki | Powód |
|--------|-------|-------|
| **Guardian v3 (defer)** | `scripts/guardian.py`, `scripts/guardian2.py`, `scripts/ifg_guardian/` | Refaktoryzacja frameworku — **osobny commit/branch**, nie mieszać z KSeF cleanup |
| **Guardian architektura (defer)** | `docs/GUARDIAN_V3_ARCHITECTURE.md`, `docs/GUARDIAN_V3_ARCHITECTURE_REVISED.md` | Dokumentacja frameworku — commit po decyzji o Guardian |
| **Inne feature'y (defer)** | `docs/FV_*`, `docs/PZ_DRAFT_*`, `docs/WAREHOUSE_*`, `docs/WZ_*`, `docs/KK_*`, `docs/UI_DEPLOY_*`, `docs/GUARDIAN_PZ_*` | Osobne tematy — osobne commity po review |
| **Frontend test numeracji** | `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | Feature FV numbering — nie KSeF |
| **Kod KSeF w HEAD** | `app/integrations/ksef/mapper.py`, `app/services/settings_service.py`, `tests/unit/test_ksef_mapper.py` | Już w `04ea2c9`, czyste — **nie modyfikować** |
| **Baza / deploy** | brak `git clean`, `reset`, `push` | Poza scope |

---

## 5. Komendy (NIE wykonane — do ręcznego uruchomienia)

### Krok A — restore szumu CRLF + dist

```bash
cd /Users/lukasz/projekty/ifg_standalone

git restore -- \
  app/api/deps.py \
  app/domain/enums.py \
  app/persistence/mappers/invoice_mapper.py \
  app/persistence/models/invoice.py \
  app/persistence/repositories/transmission_repository.py \
  app/services/invoice_number_policy.py \
  app/services/payment_service.py \
  frontend-react/src/api/invoices.js \
  frontend-react/src/components/invoice/InvoiceActions.jsx \
  frontend-react/vite.config.js \
  frontend-react/dist/index.html
```

### Krok B — commit dokumentacji KSeF (batch 1)

```bash
git add \
  docs/KSEF_METADATA_PAGINATION_FIX_2026_06_23.md \
  docs/KSEF_PURCHASE_SYNC_ADD_ISSUE_DATE_2026_06_23.md \
  docs/PURCHASE_PDF_BANK_ACCOUNT_FIX_2026_06_24.md \
  docs/KSEF_METADATA_PAGINATION_ROOT_CAUSE.md \
  docs/KSEF_METADATA_PROBE_COMMANDS_2026_06.md \
  docs/KSEF_MISSING_PURCHASES_AFTER_2026_06_05.md \
  docs/KSEF_PAGINATION_COMMIT_STATE.md \
  docs/KSEF_PERMANENTSTORAGE_VS_INVOICING_TEST.md \
  docs/KSEF_PROD_RESUME_RETEST_2026_06.md \
  docs/KSEF_PROD_SYNC_VERIFICATION_2026_06.md \
  docs/KSEF_PURCHASE_METADATA_50_LIMIT_DIAG_2026_06_23.md \
  docs/KSEF_PURCHASE_MISSING_INVOICES_ROOT_CAUSE.md \
  docs/KSEF_PURCHASE_NO_NEW_INVOICES_DIAG_2026_06.md \
  docs/KSEF_PURCHASE_SYNC_BROKEN_DIAG_2026_06.md \
  docs/KSEF_PURCHASE_SYNC_PROGRESS_DIAG.md \
  docs/KSEF_PURCHASE_TOTALS_ZERO_FIX_IMPLEMENTATION.md \
  docs/KSEF_RESUME_AUDIT_2026_06.md \
  docs/KSEF_RESUME_VERIFICATION.md \
  docs/KSEF_WORKER_QUEUE_BLOCKING_ANALYSIS.md

git commit -m "$(cat <<'EOF'
docs: KSeF sync, pagination and purchase diagnostics.

EOF
)"
```

### Krok C — opcjonalny commit meta/housekeeping (batch 2)

```bash
git add \
  docs/REPO_HOUSEKEEPING_AUDIT_2026_06.md \
  docs/guardian/REPO_AUDIT_2026_06_26.md \
  docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md

git commit -m "$(cat <<'EOF'
docs: repo housekeeping and guardian audit reports.

EOF
)"
```

### Krok D — weryfikacja po sprzątaniu

```bash
git status --short
python3 scripts/guardian.py repo audit   # jeśli Guardian już wdrożony lokalnie
```

**Po kroku A** oczekiwany status: dirty tylko `scripts/guardian.py`, `scripts/guardian2.py`, `?? scripts/ifg_guardian/`, pozostałe `?? docs/` (FV/PZ/warehouse/Guardian arch), `?? invoiceCardListNumbering.test.js`.

---

## 6. Podsumowanie

| Akcja | Liczba plików |
|-------|----------------|
| `git restore` | 11 |
| Commit KSeF docs (batch 1) | 19 |
| Commit meta (batch 2, opcjonalnie) | 3 |
| Defer / nie ruszać | Guardian (3 obszary) + ~20 docs innych feature'ów + 1 test JS |
