# GWO-IFG-SALES-INVOICE-CONTINUATION-FINAL-CHROME-PARITY-0015N-D

**Date:** 2026-10-22  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**HEAD:** `b6e82da866cee7f920a58d7b2bb943f7f17fa42d`

## PRECHECK

```
pwd=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015
branch=gwo/ifg-sales-invoice-elegant-0015
```

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=CONTINUATION_FINAL_CHROME_VISUAL_REVIEW_REQUIRED
```

## Root cause

0015N-C painted HTML recreation of summary chrome on `PAGE_CONTINUATION_FINAL`.  
That was structurally complete but not the same visual language as locked underlay chrome on `PAGE_FIRST_FINAL`.

## Fix

- Runtime crop of locked underlay region `_SUMMARY_CHROME_RECT=[118,1140,987,1278]`
- Place as chrome image on continuation final only
- Shared `_summary_values_overlay_html` for values + amount (same as PAGE_FIRST_FINAL)
- PAGE_FIRST / single-page path unchanged (`data-summary-chrome="underlay"`)

**Immutable:** underlay PNG, fields.json, stained glass, binding profile, paginator, budgets, production pdf_service.

## Chrome match (auto)

```
vat_mad≈2.76  → CONTINUATION_FINAL_SUMMARY_CHROME_MATCH=true
pay_mad≈3.56  → CONTINUATION_FINAL_PAYABLE_CHROME_MATCH=true
```

(SoT: `IFG-0015NC-1-P1.png` title/headers + payable-label regions)

## Gates

```
SINGLE_PAGE_SUMMARY_UNCHANGED=true
SINGLE_PAGE_PAYABLE_UNCHANGED=true
MULTIPAGE_FIRST_UNCHANGED=true
CONTINUATION_FINAL_VAT_TITLE_VISIBLE=true
CONTINUATION_FINAL_VAT_HEADERS_VISIBLE=true
CONTINUATION_FINAL_VAT_VALUES_VISIBLE=true
CONTINUATION_FINAL_PAYABLE_LABEL_VISIBLE=true
CONTINUATION_FINAL_PAYABLE_AMOUNT_VISIBLE=true
CONTINUATION_FINAL_SUMMARY_CHROME_MATCH=true
CONTINUATION_FINAL_PAYABLE_CHROME_MATCH=true
SUMMARY_COUNT_10=1
SUMMARY_COUNT_50=1
PAYABLE_COUNT_10=1
PAYABLE_COUNT_50=1
TEN_ITEMS_DISTRIBUTION_UNCHANGED=true
FIFTY_ITEMS_DISTRIBUTION_UNCHANGED=true
NO_ITEM_LOSS=true
NO_ITEM_DUPLICATION=true
NO_ROW_SPLIT=true
NO_CLIPPING=true
NO_SUMMARY_OVERLAP=true
BACKGROUND_ASSET_MUTATED=NO
FIELDS_JSON_MUTATED=NO
STAINED_GLASS_ASSET_MUTATED=NO
PAGINATOR_CHANGED=NO
PRODUCTION_PDF_SERVICE_CHANGED=NO
PURCHASE_TEMPLATE_CHANGED=NO
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

## PNG

- `/Volumes/WorkspaceSSD/temp/IFG-0015ND-1-P1.png`
- `/Volumes/WorkspaceSSD/temp/IFG-0015ND-10-P1.png`
- `/Volumes/WorkspaceSSD/temp/IFG-0015ND-10-LAST.png`
- `/Volumes/WorkspaceSSD/temp/IFG-0015ND-50-LAST.png`
- `/Volumes/WorkspaceSSD/temp/IFG-0015ND-REMAINING0-P1.png`

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Visual OK: `IFG-0015ND-10-LAST.png` / `IFG-0015ND-50-LAST.png` vs SoT `IFG-0015NC-1-P1.png`?
2. Regresja P1 (`IFG-0015ND-1-P1`, `IFG-0015ND-10-P1`) akceptowana jako unchanged?

## Changed files

- `app/services/sale_invoice_locked_poc.py`
- `scripts/render_sale_invoice_locked_poc_0015n_d.py`
- `tests/unit/test_sale_invoice_locked_chrome_parity_0015n_d.py`
- `tests/unit/test_sale_invoice_locked_final_summary_0015n_c.py` (aligned to underlay-crop)
- this report
