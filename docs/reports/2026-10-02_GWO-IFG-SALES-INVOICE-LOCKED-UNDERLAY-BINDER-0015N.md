# GWO-IFG-SALES-INVOICE-LOCKED-UNDERLAY-BINDER-0015N

**Date:** 2026-10-02  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015` @ `b6e82da`  
**Underlay source:** `/Volumes/WorkspaceSSD/temp/IFG_invoice_graphic_underlay_v1.zip`

## STATUS / VERDICT

```
STATUS=DONE
VERDICT=LOCKED_UNDERLAY_BINDER_VISUAL_REVIEW_REQUIRED
```

## Import + immutability

Runtime assets in `app/assets/invoice/sale_locked/`:

| File | SHA256 |
|------|--------|
| `sale_invoice_background_locked.png` | `35a9b10e…e1d2` (1024×1536) |
| `sale_invoice_fields.json` | `873534e8…930f` |
| `stained_glass_current.png` | present |
| `stained_glass_module.json` | present |

Pre/post render SHA identical → `BACKGROUND_ASSET_MUTATED=NO`, `FIELDS_JSON_MUTATED=NO`.

**Not used:** `~/Downloads/IFG_invoice_frozen_base.zip` (rejected 0015J artefact).

## Binding profile (from fields.json + PNG bands)

| Anchor | px |
|--------|---:|
| TABLE_HEADER_TOP | 942 |
| TABLE_ITEMS_TOP | 990 |
| TABLE_LEFT / RIGHT | 118 / 999 |
| SUMMARY_TOP / BOTTOM | 1216 / 1278 |
| KSEF_TOP (QR) | 1360 |
| FIRST final / normal items H | 226 / 370 |
| CONT top / normal / final H | 124 / 1208 / 1064 |

A4 map: 198×297 mm, offset_x=6 mm, scale=297/1536.

## Architecture

POC only: `app/services/sale_invoice_locked_poc.py`  
Layers: locked BG → stained glass module → scalar slots → items overprint → VAT/due → KSeF/QR.  
Paginator 0015M-C algorithm + underlay `PaginationGeometry`.  
QR: existing `ksef_qr` helpers; fixture without FA(3) XML → `QR_NOT_AVAILABLE_FOR_FIXTURE` (no fake QR).

## Distributions

| N | Pages | Plan |
|---|------:|------|
| 1 | 1 | `[1]`+summary |
| 8 | 2 | P1`[1..6]` @990; P2`[7,8]`+summary @124 |
| 9 | 2 | P1`[1..7]`; P2`[8,9]` |
| 10 | 2 | P1`[1..8]`; P2`[9,10]` (anti-orphan) |
| 50 | 3 | P1`[1..10]`; P2`[11..41]`; P3`[42..50]`+summary |

## Artefacts (`/Volumes/WorkspaceSSD/temp/`)

PDFs: `IFG-0015N-{1,8,10,50}.pdf` (+9/partial/remaining variants)  
PNGs: `IFG-0015N-1-P1.png`, `…-10-P1/LAST.png`, `…-50-P1/P2/LAST.png`

## Tests

`test_sale_invoice_locked_poc_0015n.py` + paginator suite — PASS.

## GIT DIFF GATE

```
PRODUCTION_PDF_SERVICE_CHANGED=NO   # pdf_service.py not touched this GWO
PURCHASE_TEMPLATE_CHANGED=NO
COMMIT_PERFORMED=NO
```

Note: pre-existing dirty `pdf_sale_elegant.py` / `test_pdf_service.py` / README on branch from earlier GWOs — not modified by 0015N binder work.

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Visual OK na `IFG-0015N-1-P1.png` / `…-10-*.png` / `…-50-*.png`?  
2. Akceptacja binding profile (ITEMS_TOP=990, FIRST budgets 226/370)?  
3. Następne GWO = production InvoiceResponse bind?

## Changed / added (0015N)

- `app/assets/invoice/sale_locked/**` (imported + binding profile)
- `app/services/sale_invoice_locked_poc.py`
- `app/services/invoice_items_paginator.py` (`PaginationGeometry`)
- `app/services/invoice_items_row_measure.py` (optional table width)
- `scripts/render_sale_invoice_locked_poc_0015n.py`
- `tests/unit/test_sale_invoice_locked_poc_0015n.py`
- this report
