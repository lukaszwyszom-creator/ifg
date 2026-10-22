# GWO-IFG-SALES-INVOICE-PIXEL-FAITHFUL-REBUILD-0015I

**Data:** 2026-10-01  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**HEAD:** `b6e82da866cee7f920a58d7b2bb943f7f17fa42d` (bez commit/merge)

---

## OUTPUT

```
STATUS=DONE
VERDICT=MASTER_VISUAL_REVIEW_REQUIRED
MASTER_REFERENCE=docs/design_refs/projektfv_master.jpg
LAYOUT_MAP=docs/reports/2026-10-01_GWO-IFG-SALES-INVOICE-PIXEL-FAITHFUL-REBUILD-0015I-layout-map.json
FILES_CHANGED=app/services/pdf_sale_elegant.py (presentation rebuild); docs/design_refs/projektfv_master.jpg (+ layout-map)
TESTS=46 passed
PURCHASE_REGRESSION=PASS
QR_REGRESSION=PASS
MULTIPAGE_REGRESSION=PASS (3 pages / 51 items)
ORNAMENT_X_DELTA=-4.67pp (vs master glass-center ~18.9%; CSS --ornament-x:30mm)
STAINED_GLASS_SCALE_DELTA=-0.75pp
BRAND_POSITION_DELTA=+1.03pp
INVOICE_TITLE_POSITION_DELTA=+1.84pp
META_SCALE_DELTA=-3.99pp
PARTIES_SCALE_DELTA=-1.65pp
TABLE_SCALE_DELTA=-5.09pp
SUMMARY_POSITION_DELTA=-3.49pp
X_ALIGNMENT_DELTA=0
DATE_SEPARATOR_HEIGHT_DELTA=0
SALE_PDF_PAGES=1
FINAL_PREVIEW=/tmp/ifg-0015i-final/sale-page-1.png
DESKTOP_PREVIEW=/Users/lukasz/Desktop/IFG-invoice-MASTER-REBUILD.jpg
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

### Prestatus (zachowane 0015F/G/H)
```
 M app/assets/invoice/README.md
 M app/services/pdf_sale_elegant.py
 M tests/unit/test_pdf_service.py
?? app/assets/invoice/stained_glass.png
?? docs/design_refs/
?? docs/reports/...0015F/G/H...
```

### Rebuild (nie patch 0015H)
- Nowa geometria CSS: `--ornament-x:30mm`, `--content-left:40mm`, `--stained-glass-size:78mm`, horizon przez środek witraża
- Większa typografia (brand ~34pt, FAKTURA VAT ~22pt, body 11pt)
- Tabela z piaskowym thead + pionowe separatory
- Semantyka obowiązkowa: CENA NETTO+CENA BRUTTO; DO ZAPŁATY; Kod I QR
- `stained_glass.png` / QR / purchase — nietknięte

### Artefakty
- `/tmp/ifg-0015i-final/sale.{html,pdf}` + `sale-page-1.png`
- `~/Desktop/IFG-invoice-MASTER-REBUILD.jpg` (q≈90, max 1600)

---

🩷 STATUS KOŃCOWY

✅ Co działa — 46 PASS; QR/purchase/multipage PASS; preview Desktop  
⚠️ Znane problemy — TABLE/META deltas ~4–5pp (więcej kolumn niż master); wymaga human review vs MASTER  
❌ Co nie działa — merge/deploy (STOP)

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

A. Root cause — 0015F/G/H były „skompresowanym” layoutem, nie skalą MASTER  
B. Zmienione pliki — `pdf_sale_elegant.py` (presentation), design_refs + layout-map  
C. Deploy — brak  
D. Testy — 46 passed  
E. Następny krok — porównaj `IFG-invoice-MASTER-REBUILD.jpg` z `projektfv_master.jpg`

## Decyzje dla ChatGPT

1. Czy 0015I jest wystarczająco wierny MASTER do akceptacji merge gate?
2. Jeśli TAK — osobne GWO commit (asset+presentation+testy) bez deploy?

GENERATED REPORTS

`/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/docs/reports/2026-10-01_GWO-IFG-SALES-INVOICE-PIXEL-FAITHFUL-REBUILD-0015I.md`  
`/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/docs/reports/2026-10-01_GWO-IFG-SALES-INVOICE-PIXEL-FAITHFUL-REBUILD-0015I-layout-map.json`
