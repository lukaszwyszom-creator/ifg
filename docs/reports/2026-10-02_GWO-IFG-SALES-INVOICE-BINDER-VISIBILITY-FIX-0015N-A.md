# GWO-IFG-SALES-INVOICE-BINDER-VISIBILITY-FIX-0015N-A

**Date:** 2026-10-02 (completed 2026-10-22 continuation)  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=BINDER_VISIBILITY_FIX_VISUAL_REVIEW_REQUIRED
```

## Root cause (measured)

1. **BUG A:** `overflow:hidden` in ~62 px `vat_summary` slot clipped value row (title+thead consumed height); text remained in PDF text layer → raster looked empty.
2. **BUG A (stacking):** items `table-wrap` at `z-index:40` could cover summary at shared edge `SUMMARY_TOP`.
3. **BUG B:** multipage `PAGE_FIRST` showed baked underlay `KSeF:` / QR placeholder; no runtime mask.

## Fix (visibility only)

- Compact VAT/payable paint inside existing slots; `overflow:visible`; `z-index:45`.
- Cream overprint of `ksef_number` + `ksef_qr` slots on non-final `PAGE_FIRST` only (below ornamental line ~y=1389).
- **No** changes to: underlay PNG, `fields.json`, paginator, FIRST/CONTINUATION budgets, anti-orphan, production `pdf_service`.

## Gates

```
SUMMARY_VISUALLY_PAINTED_1=true
PAYABLE_VISUALLY_PAINTED_1=true
SUMMARY_VISUALLY_PAINTED_REMAINING0=true
PAYABLE_VISUALLY_PAINTED_REMAINING0=true
MULTIPAGE_FIRST_KSEF_LABEL_VISIBLE=false
MULTIPAGE_FIRST_QR_PLACEHOLDER_VISIBLE=false
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

## Artefacts

`/Volumes/WorkspaceSSD/temp/`:

- `IFG-0015NA-1-P1.png`
- `IFG-0015NA-REMAINING0-P1.png`
- `IFG-0015NA-10-P1.png`
- `IFG-0015NA-10-LAST.png`
- matching PDFs + `IFG-0015NA-report.json`

## Tests

`tests/unit/test_sale_invoice_locked_visibility_0015n_a.py` — 3 passed  
Pixel gates via `scripts/render_sale_invoice_locked_poc_0015n_a.py` — PASS

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Visual OK na `IFG-0015NA-1-P1.png` / `…-REMAINING0-P1.png` / `…-10-P1.png` vs `…-10-LAST.png`?
2. KSeF mask coverage (bez linii ornamentu) akceptowalna?

## Changed files

- `app/services/sale_invoice_locked_poc.py` — summary visibility + KSeF mask
- `scripts/render_sale_invoice_locked_poc_0015n_a.py`
- `tests/unit/test_sale_invoice_locked_visibility_0015n_a.py`
- this report
