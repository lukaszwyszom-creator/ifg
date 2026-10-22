# GWO-IFG-SALES-INVOICE-TABLE-POLISH-0015H

**Data:** 2026-10-01  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015`  
**HEAD bazowy:** `b6e82da` (bez commit/merge)

---

## OUTPUT

```
STATUS=DONE
VERDICT=FINAL_VISUAL_REVIEW_REQUIRED
COLUMN_WIDTHS_BEFORE=LP:13.6 NAZWA:200.2 ILOŚĆ:40.8 JM:32.6 CN:71.3 CB:71.3 VAT:23.6 WN:71.3 KV:71.3 WB:71.4
COLUMN_WIDTHS_AFTER=LP:17.7 NAZWA:142.0 ILOŚĆ:35.5 JM:31.9 CN:78.1 CB:78.1 VAT:35.5 WN:85.2 KV:78.1 WB:85.3
ILOSC_JM_COLLISION=NO
FINANCIAL_HEADER_COLLISIONS=0
TABLE_OVERFLOW=NO
ORNAMENT_X_UNCHANGED=YES
CONTENT_LEFT_UNCHANGED=YES
STAINED_GLASS_BBOX_UNCHANGED=YES
INVOICE_TITLE_BBOX_UNCHANGED=YES
X_ALIGNMENT_DELTA=0
DATE_SEPARATOR_HEIGHT_DELTA=0
TESTS=46 passed
SALE_PDF_PAGES=1
PURCHASE_REGRESSION=PASS
QR_REGRESSION=PASS
MULTIPAGE_REGRESSION=PASS (3 pages / 51 items)
FINAL_PREVIEW=/tmp/ifg-0015h-final/sale-page-1.png
DESKTOP_PREVIEW=/Users/lukasz/Desktop/IFG-invoice-FINAL-0015h.jpg
COMMIT_PERFORMED=NO
MERGE_PERFORMED=NO
DEPLOY_PERFORMED=NO
```

### Zmiana (tylko CSS kolumn w `pdf_sale_elegant.py`)
- NAZWA: 30% → 20%
- kolumny finansowe: jawne % (11–12%) + padding VAT
- ILOŚĆ/JM: kompaktowe %, zachowany gap tekstu (~8.4px)

Witraż / ornament / branding / QR — **nietknięte** (bbox gates YES).

---

🩷 STATUS KOŃCOWY

✅ Co działa — tabela luźniejsza po prawej; 46 PASS; regression gates YES  
⚠️ Znane problemy — uncommitted w worktree  
❌ Co nie działa — merge/deploy (STOP)

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

A. Root cause — prawa część nagłówka ściśnięta przy NAZWA=30%  
B. Zmienione pliki — wyłącznie szerokości kolumn w `app/services/pdf_sale_elegant.py`  
C. Deploy — brak  
D. Testy — 46 passed; geometry vs 0015G unchanged outside table  
E. Następny krok — review `~/Desktop/IFG-invoice-FINAL-0015h.jpg`

## Decyzje dla ChatGPT

1. Czy szerokości kolumn 0015H są wizualnie OK do finalnego merge gate?
2. Po akceptacji: jedno GWO commit (0015F+G+H) + merge?

GENERATED REPORTS

`/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/docs/reports/2026-10-01_GWO-IFG-SALES-INVOICE-TABLE-POLISH-0015H.md`
