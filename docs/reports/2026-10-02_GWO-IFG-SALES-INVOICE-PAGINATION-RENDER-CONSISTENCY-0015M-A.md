# GWO-IFG-SALES-INVOICE-PAGINATION-RENDER-CONSISTENCY-0015M-A

**Date:** 2026-10-02  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**Output:** `/Volumes/WorkspaceSSD/temp/ifg/0015M-A/`

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=PAGINATION_RENDER_CONSISTENT
```

## Root cause (measured)

1. **Height mismatch:** POC used `estimate_row_height_px` (optimistic char-wrap) while WeasyPrint rendered taller rows under equal-width `table-layout:fixed` → last-page assigned rows were clipped by fixed-height + overflow.
2. **Final-suffix packing:** `_ensure_final_suffix` took the *largest* FINAL suffix → near-empty page 1 (10 items: LP=1 only on P1, LP=2..10 on P2 with clip around LP≈7).

## Fixes (mechanics only)

1. **Single height SoT:** `invoice_items_row_measure.py` — WeasyPrint layout boxes → MASTER px; same CSS as renderer (incl. name col 34%).
2. **Efficient final split:** smallest valid FINAL suffix → first pages fill NORMAL budget.
3. **Render invariants:** per-page `ASSIGNED_LP` vs DOM/layout `RENDERED_LP`; physical `ROW_BOTTOM` vs region / `SUMMARY_TOP`.
4. **No Desktop copies;** artefacts only under `/Volumes/WorkspaceSSD/temp/ifg/0015M-A/`.
5. **No production bind / commit / merge / deploy.**

## OUTPUT

```
TEN_ITEMS_ASSIGNED_LP=[1..10]
TEN_ITEMS_RENDERED_LP=[1..10]
TEN_ITEMS_MISSING_LP=[]
TEN_ITEMS_DUPLICATED_LP=[]
FIFTY_ITEMS_ASSIGNED_LP=[1..50]
FIFTY_ITEMS_RENDERED_LP=[1..50]
FIFTY_ITEMS_MISSING_LP=[]
FIFTY_ITEMS_DUPLICATED_LP=[]
ROW_HEIGHT_SOURCE=weasyprint_layout_master_px
RENDER_HEIGHT_SOURCE=weasyprint_layout_master_px
CLIPPING_DETECTED=false
SUMMARY_OVERLAP_DETECTED=false
ONE_ITEM_PAGES=1
TEN_ITEMS_PAGES=2
FIFTY_ITEMS_PAGES=4
TOTAL_RENDERED_10=10
TOTAL_RENDERED_50=50
LP_SEQUENCE_PASS=true
NO_ITEM_LOSS=true
NO_ITEM_DUPLICATION=true
NO_ROW_SPLIT=true
NO_SUMMARY_OVERLAP=true
OUTPUT_DIR=/Volumes/WorkspaceSSD/temp/ifg/0015M-A/
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

### Page plans (post-fix)

| Case | Pages | Plan |
|------|-------|------|
| 1 | 1 | [1] + summary |
| 7 | 1 | [1..7] + summary |
| 8 | 1 | [1..8] + summary |
| 9 | 2 | P1 [1..8]; P2 [9]+summary |
| 10 | 2 | P1 [1..9]; P2 [10]+summary |
| 11 | 2 | P1 [1..10]; P2 [11]+summary |
| 50 | 4 | P1[1..15] P2[16..30] P3[31..46] P4[47..50]+summary |

## Tests

- `tests/unit/test_invoice_items_paginator.py` + `test_invoice_items_pagination_render_0015m_a.py` → **24 passed**

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Akceptacja `VERDICT=PAGINATION_RENDER_CONSISTENT` po review PNG w `/Volumes/WorkspaceSSD/temp/ifg/0015M-A/`?
2. Kolejne GWO = wpięcie measured-height paginatora do elegant/frozen production renderer?

## Changed files

- `app/services/invoice_items_paginator.py` — smallest final suffix
- `app/services/invoice_items_row_measure.py` — new
- `scripts/render_invoice_pagination_poc_0015m_a.py` — new POC
- `tests/unit/test_invoice_items_pagination_render_0015m_a.py` — new
- `docs/reports/2026-10-02_GWO-IFG-SALES-INVOICE-PAGINATION-RENDER-CONSISTENCY-0015M-A.md` — this report
