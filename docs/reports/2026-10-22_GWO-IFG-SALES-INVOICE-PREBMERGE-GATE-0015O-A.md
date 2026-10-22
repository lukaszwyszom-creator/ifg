# GWO-IFG-SALES-INVOICE-PREBMERGE-GATE-0015O-A

**Date:** 2026-10-22  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**HEAD:** `b6e82da866cee7f920a58d7b2bb943f7f17fa42d` (uncommitted 0015O-A deltas)

## PRECHECK

```
pwd=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015
branch=gwo/ifg-sales-invoice-elegant-0015
NO COMMIT / NO MERGE / NO DEPLOY
```

## Zakres wykonany

### 1. KOR TITLE (dynamic slot)

- Runtime cream mask + paint over baked underlay title text only.
- Geometry: `_DOC_TITLE_RECT = [118, 380, 720, 412]`, style `serif_bold_36_navy`.
- Binding: `adapt_invoice_response_to_locked` → `document_title=_document_title(invoice)` (`pdf_service._DOC_TITLES`).
- VAT → `FAKTURA VAT`; KOR → `FAKTURA KORYGUJĄCA`.
- `fields.json` / underlay PNG / paginator **not** modified.

### 2. REMAINING_AMOUNT 400,00

0015O REAL-10 fixture intentionally sets:

```python
_short_items_invoice(10, remaining=Decimal("400"))
# total_gross = 10 × 105.00 = 1050.00
```

Evidence (production path HTML):

| Field | Value |
|-------|-------|
| `invoice.total_gross` | `1050.00` |
| `invoice.remaining_amount` | `400` (explicit) |
| DO ZAPŁATY (`data-visual-text="amount_due"`) | `400,00 PLN` |

**Verdict:** PASS — not a binding bug. Semantics unchanged: explicit `remaining_amount` wins; else fallback `total_gross`.

### 3. 5× `ksef_status_api` failures

Reproduced on worktree **and** clean `ifg_standalone` baseline (identical files: `diff -q` empty).

| # | Test | Result |
|---|------|--------|
| 1 | `TestKSeFConnectionStatusService::test_connected_for_active_non_expired_session` | FAIL |
| 2 | `TestKSeFConnectionStatusService::test_disconnected_for_expired_session` | FAIL |
| 3 | `TestKSeFConnectionStatusService::test_disconnected_for_missing_session` | FAIL |
| 4 | `TestKSeFConnectionStatusService::test_probe_failure_below_threshold_keeps_connected_status` | FAIL |
| 5 | `TestKSeFConnectionStatusService::test_probe_counter_resets_after_success` | FAIL |

**Root cause (test drift, not PR #6 / not 0015O binder):**

- Tests mock `service._get_active_db_session = MagicMock(...)`.
- Production `get_connection_status` calls `self._get_active_online_session(nip)` directly (line ~423).
- `_get_active_db_session` is only a thin wrapper → mock never applied.
- Real `_get_active_online_session` against `MagicMock()` session returns a MagicMock ORM → `expires_at <= now` raises `TypeError` → caught → `ui_status=ERROR`.

**PR-related:** NO. Same failure on baseline `ifg_standalone` without sale-invoice locked binder changes. Not fixed in this GWO.

Log: `/Volumes/WorkspaceSSD/temp/IFG-0015OA-ksef-status-failures.txt`

## Gates

| Gate | Result |
|------|--------|
| sale targeted (`test_sale_invoice_*` + locked + paginator + `test_pdf_service`) | **116 passed** |
| KOR title / remaining A+B (`test_sale_invoice_prebmerge_0015o_a`) | **4 passed** |
| purchase regression (`sale-locked` absent; ZAKUP path) | **PASS** (+ 6 pdf_service purchase-filtered) |
| layout geometry / paginator / underlay / fields.json | **unchanged** |
| production sale preview/PDF same binder | **PASS** (`pdf_service` → `render_sale_locked_html`) |

### Asset SHA256 (unchanged vs 0015O)

```
FIELDS  873534e8faa39ada916f92835bc16657dd591ca3b4fd9d380b62c0b68a8f930f
BG      35a9b10ef2fccbae17051b310a5788e70284c4abe6f7796a5c16501c9080e1d2
PROFILE 1ee2c8024d22f77f08e03c0c4976fb789f9a0a871a94eb7eee70fe6740b5a8bd
```

## Artefacts

```
/Volumes/WorkspaceSSD/temp/IFG-0015OA-FV-P1.png   # title: FAKTURA VAT
/Volumes/WorkspaceSSD/temp/IFG-0015OA-KOR-P1.png  # title: FAKTURA KORYGUJĄCA
/Volumes/WorkspaceSSD/temp/IFG-0015OA-FV.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015OA-KOR.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015OA-ksef-status-failures.txt
```

## STATUS FIELDS

```
STATUS=DONE
VERDICT=PREBMERGE_GATE_PASS
KOR_TITLE=FAKTURA KORYGUJĄCA
NORMAL_TITLE=FAKTURA VAT
REMAINING_400_SOURCE=explicit fixture remaining_amount=400 (total_gross=1050); NOT binding bug
REMAINING_EXPLICIT_TEST=PASS
REMAINING_FALLBACK_TEST=PASS
KSEF_STATUS_FAILURES_REPRODUCED=YES (5/5)
KSEF_STATUS_FAILURES_PR_RELATED=NO (identical on ifg_standalone baseline; mock wrong method)
LAYOUT_GEOMETRY_UNCHANGED=YES
PURCHASE_TEMPLATE_CHANGED=NO
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Czy zamykać PR #6 / branch gate przy znanych 5 FAIL `ksef_status_api` (udokumentowane jako baseline drift — mock `_get_active_db_session` vs `_get_active_online_session`), bez naprawy w tym PR?
2. Czy osobne GWO na fix testów KSeF status (mock `_get_active_online_session`) przed merge do main?

## Changed files (0015O-A)

- `app/services/sale_invoice_locked_poc.py` — dynamic title mask/paint
- `app/services/sale_invoice_locked_bind.py` — `document_title=_document_title(invoice)`
- `tests/unit/test_pdf_service.py` — assert dynamic titles
- `tests/unit/test_sale_invoice_prebmerge_0015o_a.py` — NEW
- `scripts/render_sale_invoice_prebmerge_0015o_a.py` — NEW
- `docs/reports/2026-10-22_GWO-IFG-SALES-INVOICE-PREBMERGE-GATE-0015O-A.md` — this report
