# GWO-IFG-SALES-INVOICE-VISUAL-REGRESSION-FIX-0015G

**Data:** 2026-10-01  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**HEAD bazowy:** `b6e82da866cee7f920a58d7b2bb943f7f17fa42d` (bez commit/merge)

---

## OUTPUT

```
STATUS=DONE
VERDICT=FINAL_VISUAL_REVIEW_REQUIRED
WITRAZ_BBOX={x:14.03,y:-42.91,w:219.2,h:219.2,r:233.23,b:176.3}
ORNAMENT_X=60.47px (CSS --ornament-x: 16mm)
CONTENT_LEFT=98.27px (CSS --content-left: 26mm)
INVOICE_TITLE_BBOX={x:161.42,y:192.13,w:667.42,h:27.06,r:828.84,b:219.19}
STAINED_GLASS_INVOICE_TITLE_COLLISION=0
ORNAMENT_TEXT_COLLISIONS=0
ILOSC_BBOX={x:375.23,y:474.06,w:40.8,h:31.34}
JM_BBOX={x:416.03,y:474.06,w:32.63,h:31.34}
TABLE_HEADER_COLLISIONS=0
QTY_JM_TEXT_GAP_PX=13.75
X_ALIGNMENT_DELTA=0
DATE_SEPARATOR_HEIGHT_DELTA=0
TESTS=46 passed
SALE_PDF_PAGES=1
PURCHASE_REGRESSION=PASS
QR_REGRESSION=PASS
FINAL_PREVIEW=/tmp/ifg-0015g-final/sale-page-1.png
DESKTOP_PREVIEW=/Users/lukasz/Desktop/IFG-invoice-final-review-0015g.jpg
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

### Naprawy (minimalny CSS w `pdf_sale_elegant.py`)

| Problem | Fix |
|---------|-----|
| Witraż jak ikonka (18mm) | `--stained-glass-size: 58mm`, `top: -20mm`, centrum na `--ornament-x` |
| Linia za blisko treści | `--ornament-x: 16mm`, `--content-left: 26mm` (treść wyraźnie na prawo) |
| FAKTURA VAT × witraż | `.doc-head { margin-top: 28mm }`, z-index tekstu 2 |
| ILOŚĆJM | szersze kolumny + padding; gap tekstu 13.75px |

Asset `stained_glass.png` **nietknięty**. QR / purchase / logika — freeze.

### Geometry self-check (Playwright, bez vision)

- Glass overhang: `y=-42.91` (poza górą)
- `CONTENT_LEFT > ORNAMENT_X` (+37.8px)
- Title below glass (`title.y=192.13 > glass.b=176.3`)
- Ornament nie przecina tekstu
- ILOŚĆ/JM text gap > 0

---

🩷 STATUS KOŃCOWY

✅ Co działa — 46 PASS; geometry gates 0; smoke + Desktop JPEG  
⚠️ Znane problemy — zmiany nadal **uncommitted** w worktree (oczekiwany review)  
❌ Co nie działa — merge/deploy celowo STOP

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

A. Root cause — zbyt mały viewport witraża + ornament wewnątrz content padding (0015F)  
B. Zmienione pliki — `app/services/pdf_sale_elegant.py` (CSS only; asset/PNG bez zmian)  
C. Deploy — brak  
D. Testy — 46 passed; geometry OK  
E. Następny krok — human review `~/Desktop/IFG-invoice-final-review-0015g.jpg`

## Decyzje dla ChatGPT

1. Czy wizualnie 0015G przywraca zaakceptowany charakter (duży witraż + szeroki binder)?
2. Po akceptacji: osobne GWO commit (0015F+0015G) + merge gate?

GENERATED REPORTS

`/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/docs/reports/2026-10-01_GWO-IFG-SALES-INVOICE-VISUAL-REGRESSION-FIX-0015G.md`
