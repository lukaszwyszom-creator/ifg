# GWO-IFG-SALES-INVOICE-FINAL-PAGE-ANTI-ORPHAN-0015M-C

**Date:** 2026-10-02  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Output:** `/Volumes/WorkspaceSSD/temp/` (flat)

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=FINAL_PAGE_ANTI_ORPHAN_PASS
```

## Rule

After pagination, if `len(pages) > 1` and last page has exactly 1 row:
- try move last row of previous page onto final page
- iff both fit `CONTINUATION_FINAL_ITEMS_HEIGHT`
- and previous page keeps ≥1 row
- else leave orphan

## Distributions

| N | Result |
|---|--------|
| 8 | 1 page `[1..8]` |
| 9 | P1=`[1..7]` P2=`[8,9]`+summary |
| 10 | P1=`[1..8]` P2=`[9,10]`+summary |
| 11 | P1=`[1..9]` P2=`[10,11]`+summary |
| 50 | P3 already ≥2 rows — unchanged |

## Invariants

All true: NO_ITEM_LOSS / DUPLICATION / ROW_SPLIT / CLIPPING / SUMMARY_OVERLAP; SUMMARY=PAYABLE=QR=1.

## Tests

`test_invoice_items_anti_orphan_0015m_c.py` + prior pagination suite — PASS.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## Changed files

- `app/services/invoice_items_paginator.py` — `_anti_orphan_rebalance`
- `scripts/render_invoice_pagination_poc_0015m_c.py`
- `tests/unit/test_invoice_items_anti_orphan_0015m_c.py`
- `docs/reports/2026-10-02_GWO-IFG-SALES-INVOICE-FINAL-PAGE-ANTI-ORPHAN-0015M-C.md`
