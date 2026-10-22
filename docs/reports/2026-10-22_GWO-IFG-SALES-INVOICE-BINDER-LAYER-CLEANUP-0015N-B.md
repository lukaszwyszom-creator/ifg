# GWO-IFG-SALES-INVOICE-BINDER-LAYER-CLEANUP-0015N-B

**Date:** 2026-10-22  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=BINDER_LAYER_CLEANUP_VISUAL_REVIEW_REQUIRED
```

## Root cause (measured)

1. **Payable duplication:** dynamic `_summary_html` painted a second `DO ZAPŁATY` label + bordered cream box over locked underlay chrome.
2. **VAT title covered:** PAGE_FIRST_FINAL items cream used full `items_budget_px` down to SUMMARY_TOP (~1216), covering static `PODSUMOWANIE VAT` ink at y≈1143–1154.
3. **KSeF mask cut line:** QR cream previously started at/above horizontal separator (y≈1389/1391); right segment of line disappeared under mask.

## Fix (layer cleanup only)

1. **Payable:** dynamic slot = amount only (`border:none`, transparent bg, no label text).
2. **VAT:** dynamic slot = value row only (no `<thead>`); items cream on `PAGE_FIRST`+`show_summary` visually capped at `_VAT_TITLE_TOP_PX=1140` (pagination budgets unchanged).
3. **KSeF mask:** tight label rect `[128,1422,210,1448]` + QR body `[820,1395,990,1518]` (both strictly below `_KSEF_LINE_Y_PX=1389`).

**Unchanged:** paginator, budgets, underlay PNG, `fields.json`, table geometry, production `pdf_service`, purchase template.

## Gates (PNG evidence)

```
SINGLE_PAGE_PAYABLE_LABEL_COUNT=1
SINGLE_PAGE_PAYABLE_BOX_COUNT=1
SINGLE_PAGE_VAT_TITLE_VISIBLE=true
MULTIPAGE_FIRST_KSEF_LABEL_VISIBLE=false
MULTIPAGE_FIRST_BOTTOM_LINE_CONTINUOUS=true
MULTIPAGE_FIRST_ORNAMENT_INTACT=true
TEN_ITEMS_DISTRIBUTION_UNCHANGED=true
FIFTY_ITEMS_DISTRIBUTION_UNCHANGED=true
BACKGROUND_ASSET_MUTATED=NO
FIELDS_JSON_MUTATED=NO
PAGINATOR_CHANGED=NO
PRODUCTION_PDF_SERVICE_CHANGED=NO
PURCHASE_TEMPLATE_CHANGED=NO
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

Proof artefacts under `/Volumes/WorkspaceSSD/temp/`:

- `IFG-0015NB-1-P1.png` — single page: one DO ZAPŁATY, VAT title visible, amount only
- `IFG-0015NB-REMAINING0-P1.png`
- `IFG-0015NB-10-P1.png` — KSeF hidden, bottom line continuous
- `IFG-0015NB-10-LAST.png`
- machine report: `IFG-0015NB-report.json`

## Tests

- `tests/unit/test_sale_invoice_locked_layer_cleanup_0015n_b.py`
- `tests/unit/test_sale_invoice_locked_visibility_0015n_a.py` (aligned to amount-only / values-only)
- Pixel gates: `scripts/render_sale_invoice_locked_poc_0015n_b.py` → PASS / exit 0

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Visual OK na czterech PNG `IFG-0015NB-*` (payable / VAT title / KSeF mask / linia)?
2. Akceptowalne skrócenie wizualnego cream items do y=1140 na PAGE_FIRST_FINAL (budżet paginacji bez zmian)?

## Changed files

- `app/services/sale_invoice_locked_poc.py`
- `scripts/render_sale_invoice_locked_poc_0015n_b.py`
- `tests/unit/test_sale_invoice_locked_layer_cleanup_0015n_b.py`
- `tests/unit/test_sale_invoice_locked_visibility_0015n_a.py`
- this report
