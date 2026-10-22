# GWO-IFG-SALES-INVOICE-CONTINUATION-PAGES-0015M-B

**Date:** 2026-10-02  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**Output:** `/Volumes/WorkspaceSSD/temp/` (flat — no subdirs, no Desktop)

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=CONTINUATION_PAGINATION_VISUAL_REVIEW_REQUIRED
```

## Problem

0015M-A used `TABLE_TOP_FIRST=780` on every page → huge empty upper region on pages 2+.

## Solution

Three page kinds with measured budgets:

| Constant | Value | Source |
|----------|------:|--------|
| TABLE_TOP_FIRST | 780 | frozen MASTER |
| TABLE_TOP_CONTINUATION | 124 | measured continuation ID chrome (~103.4) + 4 mm gap |
| FIRST_NORMAL_ITEMS_HEIGHT | 577 | 1385−780−28 |
| FIRST_FINAL_ITEMS_HEIGHT | 330 | 1138−780−28 (single-page only) |
| CONTINUATION_NORMAL_ITEMS_HEIGHT | 1233 | 1385−124−28 |
| CONTINUATION_FINAL_ITEMS_HEIGHT | 986 | 1138−124−28 |

- **PAGE_FIRST** — frozen page-1 chrome; table at 780  
- **PAGE_CONTINUATION** — invoice # + „Ciąg dalszy”; table at 124; no summary  
- **PAGE_FINAL_CONTINUATION** — same top; reserves VAT + DO ZAPŁATY + KSeF/QR  

WeasyPrint remains height SoT (0015M-A). No production bind.

## OUTPUT

```
TABLE_TOP_FIRST=780
TABLE_TOP_CONTINUATION=124
FIRST_NORMAL_ITEMS_HEIGHT=577
CONTINUATION_NORMAL_ITEMS_HEIGHT=1233
CONTINUATION_FINAL_ITEMS_HEIGHT=986
TEN_ITEMS_PAGES=2
FIFTY_ITEMS_PAGES=3
TEN_ITEMS_PAGE_DISTRIBUTION=P1[1..9]@780; P2[10]+summary@124
FIFTY_ITEMS_PAGE_DISTRIBUTION=P1[1..15]@780; P2[16..48]@124; P3[49..50]+summary@124
NO_ITEM_LOSS=true
NO_ITEM_DUPLICATION=true
NO_ROW_SPLIT=true
NO_CLIPPING=true
NO_SUMMARY_OVERLAP=true
SUMMARY_COUNT_10=1
SUMMARY_COUNT_50=1
PAYABLE_COUNT_10=1
PAYABLE_COUNT_50=1
QR_COUNT_10=1
QR_COUNT_50=1
OUTPUT_DIR=/Volumes/WorkspaceSSD/temp/
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

## Tests

32 passed (`paginator` + `0015M-A` + `0015M-B` continuation).

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Akceptacja `TABLE_TOP_CONTINUATION=124` i continuation chrome (numer + „Ciąg dalszy”)?  
2. Visual OK na `IFG-0015MB-10-LAST.png` / `IFG-0015MB-50-P2.png` / `IFG-0015MB-50-LAST.png`?  
3. Następne GWO = production bind?

## Changed files

- `app/services/invoice_items_paginator.py` — page kinds + budgets  
- `scripts/render_invoice_pagination_poc_0015m_b.py` — POC  
- `tests/unit/test_invoice_items_pagination_continuation_0015m_b.py`  
- `tests/unit/test_invoice_items_paginator.py` / `…_0015m_a.py` — budget asserts  
- `docs/reports/2026-10-02_GWO-IFG-SALES-INVOICE-CONTINUATION-PAGES-0015M-B.md`
