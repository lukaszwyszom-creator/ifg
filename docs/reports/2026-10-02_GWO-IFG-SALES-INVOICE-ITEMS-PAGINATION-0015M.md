# GWO-IFG-SALES-INVOICE-ITEMS-PAGINATION-0015M

**Data:** 2026-10-02  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Branch:** `gwo/ifg-sales-invoice-elegant-0015` @ `b6e82da`

## CEL

Mechanika: dynamiczna wysokość obszaru ITEMS + podział stron + VAT/DO ZAPŁATY wyłącznie na ostatniej stronie.  
**Bez** zmiany zamrożonych anchorów layoutu (X/ornament/header/parties/summary X/KSeF/witraż).

## ANCHORY (z `master_geometry.json`)

| Stała | px |
|-------|-----|
| TABLE_TOP | 780 |
| TABLE_LEFT | 120 |
| TABLE_RIGHT | 977 |
| SUMMARY_TOP | 1138 |
| SUMMARY_BOTTOM | 1260 |
| PAGE_CONTENT_BOTTOM / KSEF_FOOTER_TOP | 1385 |
| THEAD_HEIGHT | 28 |

**Budżety wierszy (bez thead):**

- `NORMAL_PAGE_ITEMS_HEIGHT` = 1385 − 780 − 28 = **577**
- `FINAL_PAGE_ITEMS_HEIGHT` = 1138 − 780 − 28 = **330**

## IMPLEMENTACJA

- `app/services/invoice_items_paginator.py` — dwufazowy plan stron (świadomy o final budget)
- `tests/unit/test_invoice_items_paginator.py` — 15 testów PASS
- `scripts/render_invoice_pagination_poc_0015m.py` — POC render (nie production path)

## POC WYNIKI

| Case | Pages | SUMMARY | PAYABLE | QR | items in/out |
|------|-------|---------|---------|-----|--------------|
| 1 item | 1 | 1 | 1 | 1 | 1/1 |
| 10 items | 2 | 1 | 1 | 1 | 10/10 |
| 50 items | 4 | 1 | 1 | 1 | 50/50 |

LP 1..N continuous; no loss/duplication; summary only on last page.

## GEOMETRY FREEZE GATE

| Gate | Value |
|------|-------|
| ORNAMENT_GEOMETRY_CHANGED | NO |
| HEADER_GEOMETRY_CHANGED | NO |
| PARTIES_GEOMETRY_CHANGED | NO |
| TABLE_X_GEOMETRY_CHANGED | NO |
| SUMMARY_X_GEOMETRY_CHANGED | NO |
| KSEF_GEOMETRY_CHANGED | NO |
| STAINED_GLASS_CHANGED | NO |

## ARTEFAKTY

`/tmp/ifg-0015m/{one,ten,fifty}-item(s).pdf` + per-page PNG  
Desktop:

- `~/Desktop/IFG-PAGINATION-1.jpg`
- `~/Desktop/IFG-PAGINATION-10-P1.jpg` / `...-LAST.jpg`
- `~/Desktop/IFG-PAGINATION-50-P1.jpg` / `...-LAST.jpg`

## STOP

Production binder / pdf_service path / purchase — **nietknięte**  
commit / merge / deploy — **NO**

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- Paginator z FINAL vs NORMAL budget  
- VAT + DO ZAPŁATY + QR raz, na ostatniej stronie  
- LP ciągłe; 15 unit testów PASS  
- POC 1/10/50 + Desktop  

⚠️ Znane problemy  
- Continuation pages = funkcjonalny chrome (nie redesign) — osobne GWO  
- POC HTML nie jest production elegant template  

❌ Co nie działa  
- Brak w zakresie STOP  

### A. Root cause
Potrzeba rezerwacji SUMMARY na last page przed packingiem wierszy.

### B. Zmienione pliki
`invoice_items_paginator.py`, `test_invoice_items_paginator.py`, `render_invoice_pagination_poc_0015m.py`, raport

### C. Deploy — nie  
### D. Testy — 15 PASS; POC invariants  
### E. Następny krok — review Desktop; potem osobne GWO podpięcia do elegant/frozen binder

## Decyzje dla ChatGPT

1. Czy budżety 577 / 330 px (z MASTER anchors) akceptujemy?  
2. Czy 10 items → 2 pages (z długimi nazwami fixture) jest OK vs oczekiwanie 1 strony dla krótkich?  
3. Czy kolejny GWO ma wpiąć paginator w production elegant renderer?

---

STATUS=DONE  
VERDICT=PAGINATION_LOGIC_VISUAL_REVIEW_REQUIRED  
NORMAL_PAGE_ITEMS_HEIGHT=577  
FINAL_PAGE_ITEMS_HEIGHT=330  
ONE_ITEM_PAGES=1  
TEN_ITEMS_PAGES=2  
FIFTY_ITEMS_PAGES=4  
SUMMARY_COUNT_1=1  
SUMMARY_COUNT_10=1  
SUMMARY_COUNT_50=1  
PAYABLE_COUNT_1=1  
PAYABLE_COUNT_10=1  
PAYABLE_COUNT_50=1  
QR_COUNT_1=1  
QR_COUNT_10=1  
QR_COUNT_50=1  
ITEMS_INPUT_50=50  
ITEMS_RENDERED_50=50  
LP_SEQUENCE_PASS=YES  
NO_ITEM_LOSS=YES  
NO_ITEM_DUPLICATION=YES  
NO_ROW_SPLIT=YES  
ORNAMENT_GEOMETRY_CHANGED=NO  
HEADER_GEOMETRY_CHANGED=NO  
PARTIES_GEOMETRY_CHANGED=NO  
TABLE_X_GEOMETRY_CHANGED=NO  
SUMMARY_X_GEOMETRY_CHANGED=NO  
KSEF_GEOMETRY_CHANGED=NO  
STAINED_GLASS_CHANGED=NO  
DESKTOP_PREVIEWS=~/Desktop/IFG-PAGINATION-*.jpg  
COMMIT_PERFORMED=NO  
MERGE_PERFORMED=NO  
DEPLOY_PERFORMED=NO  
