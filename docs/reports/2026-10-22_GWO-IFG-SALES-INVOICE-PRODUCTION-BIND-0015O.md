# GWO-IFG-SALES-INVOICE-PRODUCTION-BIND-0015O

**Date:** 2026-10-22  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**HEAD:** `b6e82da866cee7f920a58d7b2bb943f7f17fa42d`

## PRECHECK

```
pwd=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015
branch=gwo/ifg-sales-invoice-elegant-0015
```

### Dirty-state inventory (not discarded)

| Bucket | Contents |
|--------|----------|
| 0015N-D / binder chain | `sale_invoice_locked_poc.py`, paginator/measure, sale_locked assets, 0015N* scripts/tests/reports |
| Earlier PR #6 | `pdf_sale_elegant.py`, `frozen_sales_invoice.py`, layout_shell/sale_template, stained_glass.png, README |
| 0015O (this GWO) | `sale_invoice_locked_bind.py`, `pdf_service.py` sale dispatch, tests/scripts/report |
| Unrelated dirty | `test_pdf_service.py` (adapted for locked), prior docs/reports |

## Production flow audit

```
GET /invoices/{id}/preview  → render_invoice_html(InvoiceResponse, bank, ksef_xml, env)
GET /invoices/{id}/pdf      → render_invoice_pdf → same render_invoice_html → WeasyPrint
```

- Sale: **now** `sale_invoice_locked_bind.render_sale_locked_html` → locked underlay binder (0015N-D)
- Purchase: unchanged `_render_classic_modern_html`
- Data: `InvoiceResponse.from_domain` + `compute_remaining_amounts` + `resolve_seller_bank_account_for_render` + `_ksef_xml_bytes_for_invoice`

## Architecture after bind

```
InvoiceResponse
 → adapt_invoice_response_to_locked()
 → LockedInvoiceData (PocInvoiceFixture)
 → render_locked_invoice()  [paginator 0015M-C + locked layers]
 → HTML
 → WeasyPrint PDF
```

Production no longer depends on POC fixtures, hardcoded parties, or `/temp` PNG SoT for rendering.

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=PRODUCTION_BIND_VISUAL_REVIEW_REQUIRED
```

## Gates

```
PRODUCTION_BIND_IMPLEMENTED=true
PRODUCTION_RENDERER=sale_invoice_locked_bind via pdf_service
PREVIEW_BOUND=true
PDF_BOUND=true
REAL_INVOICE_MODEL_BOUND=true
REAL_ITEMS_BOUND=true
REAL_VAT_SUMMARY_BOUND=true
REAL_REMAINING_AMOUNT_BOUND=true
REAL_KSEF_NUMBER_BOUND=true
REAL_KSEF_QR_BOUND=true
ONE_ITEM_PAGES=1
EIGHT_ITEMS_PAGES=1
NINE_ITEMS_PAGES=2
TEN_ITEMS_PAGES=2
FIFTY_ITEMS_PAGES=3
REMAINING_ZERO_RENDERED_AS=0,00 PLN
FAKE_QR_PRESENT=false
BACKGROUND_ASSET_MUTATED=NO
FIELDS_JSON_MUTATED=NO
BINDING_PROFILE_MUTATED=NO
PAGINATOR_CHANGED=NO
PURCHASE_TEMPLATE_CHANGED=NO
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

## Known mapping gaps

1. **Document title for KOR/ZAL/ROZ** — locked underlay paints baked `FAKTURA VAT`; no `fields.json` title slot. Correction reason not painted on locked sheet (reported, not redesigned in 0015O).

## Tests

| Suite | Result |
|-------|--------|
| `test_sale_invoice_production_bind_0015o.py` + `test_pdf_service.py` | **57 passed** |
| sale_locked + invoice_items + pdf + ksef* unit | **477 passed**, 5 failed in `test_ksef_status_api.py` (session probe — unrelated to PDF bind) |
| Purchase markers | PASS (`sale-locked` absent on purchase) |

## Artefacts (production path)

```
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-1.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-1-P1.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-10.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-10-P1.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-10-LAST.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-50.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-50-P1.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-REAL-50-LAST.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-REMAINING0.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015O-REMAINING0-P1.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-KSEF.pdf
/Volumes/WorkspaceSSD/temp/IFG-0015O-KSEF-LAST.png
/Volumes/WorkspaceSSD/temp/IFG-0015O-report.json
```

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Visual OK production PNGs vs 0015N-D SoT geometry?
2. Accept KOR title mapping gap until a later title-slot / polish GWO?
3. Proceed to commit/PR gate after HUMAN VISUAL PASS?

## Changed files (0015O)

- `app/services/sale_invoice_locked_bind.py` (new)
- `app/services/sale_invoice_locked_poc.py` (vat_rows, total_gross, QR INCOMPLETE, production markers)
- `app/services/pdf_service.py` (sale → locked bind)
- `tests/unit/test_sale_invoice_production_bind_0015o.py`
- `tests/unit/test_pdf_service.py` (sale assertions → locked contracts)
- `scripts/render_sale_invoice_production_bind_0015o.py`
- this report
