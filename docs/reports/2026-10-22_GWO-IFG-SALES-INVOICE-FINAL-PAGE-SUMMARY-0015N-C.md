# GWO-IFG-SALES-INVOICE-FINAL-PAGE-SUMMARY-0015N-C

**Date:** 2026-10-22  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=FINAL_PAGE_SUMMARY_VISUAL_REVIEW_REQUIRED
```

## Root cause

`PAGE_FIRST_FINAL` gets VAT title / column headers / DO ZAPŁATY from locked underlay; dynamic layer paints values only (0015N-B).  
`PAGE_CONTINUATION_FINAL` has **no underlay**, so the same values-only paint left a truncated end-block (amounts floating without chrome).

## Fix (continuation final only)

- `_summary_html(..., include_static_chrome=True)` when `page.page_kind != FIRST`
- Paints: frame + `PODSUMOWANIE VAT` + headers + values (in `vat_summary` rect) + `DO ZAPŁATY` + amount
- Items cream visually capped above `_VAT_TITLE_TOP_PX` when `show_summary` (budgets unchanged)
- `PAGE_FIRST` / single-page path unchanged (`data-summary-chrome="underlay"`)

**Unchanged:** underlay PNG, `fields.json`, paginator, budgets, LP distribution, KSeF/QR architecture, production `pdf_service`, purchase template.

## Gates

```
FINAL_PAGE_VAT_TITLE_VISIBLE=true
FINAL_PAGE_VAT_HEADERS_VISIBLE=true
FINAL_PAGE_VAT_VALUES_VISIBLE=true
FINAL_PAGE_PAYABLE_LABEL_COUNT=1
FINAL_PAGE_PAYABLE_AMOUNT_VISIBLE=true
TEN_ITEMS_DISTRIBUTION_UNCHANGED=true
FIFTY_ITEMS_DISTRIBUTION_UNCHANGED=true
NO_ITEM_LOSS=true
NO_ITEM_DUPLICATION=true
NO_ROW_SPLIT=true
NO_CLIPPING=true
NO_SUMMARY_OVERLAP=true
BACKGROUND_ASSET_MUTATED=NO
FIELDS_JSON_MUTATED=NO
PAGINATOR_CHANGED=NO
PRODUCTION_PDF_SERVICE_CHANGED=NO
PURCHASE_TEMPLATE_CHANGED=NO
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

## PNG paths (visual review)

1. `/Volumes/WorkspaceSSD/temp/IFG-0015NC-10-LAST.png`
2. `/Volumes/WorkspaceSSD/temp/IFG-0015NC-50-LAST.png`
3. `/Volumes/WorkspaceSSD/temp/IFG-0015NC-1-P1.png`
4. `/Volumes/WorkspaceSSD/temp/IFG-0015NC-10-P1.png`

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Visual OK na `IFG-0015NC-10-LAST.png` / `IFG-0015NC-50-LAST.png` vs regresja `IFG-0015NC-1-P1.png`?
2. Chrome continuation final wystarczająco bliski zaakceptowanemu PAGE_FIRST_FINAL?

## Changed files

- `app/services/sale_invoice_locked_poc.py`
- `scripts/render_sale_invoice_locked_poc_0015n_c.py`
- `tests/unit/test_sale_invoice_locked_final_summary_0015n_c.py`
- this report
