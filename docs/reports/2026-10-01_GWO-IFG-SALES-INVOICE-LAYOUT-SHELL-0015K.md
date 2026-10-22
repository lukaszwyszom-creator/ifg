# GWO-IFG-SALES-INVOICE-LAYOUT-SHELL-0015K

**Data:** 2026-10-01  
**Branch / worktree:** `gwo/ifg-sales-invoice-elegant-0015` @ `b6e82da`  
**Zakres:** edytowalny szkielet A4 (mm/pt) — bez IFG bind, bez freeze, bez finalizacji witraża

## ARCHITEKTURA

Warstwy w `app/assets/invoice/layout_shell/`:

1. `layer-background` — cream paper  
2. `layer-ornament` — oś `--ornament-x-mm`, romby, reguły wektorowe  
3. `stained-glass-module` — osobny moduł edytowalny (`stained_glass_module.json`)  
4. `layer-branding` — Ikona / WYDAWNICTWO  
5. `layer-content` — treść dokumentu + sloty  
6. `layer-ksef-qr` — placeholder QR  

Geometria: **mm / pt** (nie px jako źródło).  
Raster MASTER **nie** jest tłem dokumentu.

## PARAMETRY

| Token | Wartość |
|-------|---------|
| PAGE_SIZE | A4 210mm × 297mm |
| ORNAMENT_X_MM | 17.2 |
| CONTENT_LEFT_MM | 42 |
| CONTENT_WIDTH_MM | 147 |
| TABLE_WIDTH_MM | 147 (= content) |
| STAINED_GLASS | x=-10mm, y=-8mm, size=58mm, editable |

## SLOTY (test data only)

`invoice_number` … `ksef_qr` — obecne; **IFG_DATA_BOUND=NO**

## RENDER

| Artefakt | Ścieżka |
|----------|---------|
| HTML | `/tmp/ifg-0015k/layout.html` |
| PDF | `/tmp/ifg-0015k/layout.pdf` |
| PNG | `/tmp/ifg-0015k/layout-page-1.png` |
| Desktop | `~/Desktop/IFG-LAYOUT-SHELL-0015K.jpg` |

PDF_PAGES=1

## STOP

- commit / merge / deploy — NIE  
- InvoiceResponse bind — NIE  
- freeze wyglądu — NIE (tylko struktura do review)

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- Szkielet A4 w mm/pt, 6 warstw  
- Edytowalny `stained_glass_module` (JSON + data-* + CSS vars)  
- Ornament na wspólnej `--ornament-x-mm`  
- Native HTML tabela 10 kolumn (CENA NETTO+CENA BRUTTO), DO ZAPŁATY  
- Render 1×A4 + Desktop preview  

⚠️ Znane problemy  
- Witraż = placeholder (crop/scale do dalszej kalibracji operatora)  
- QR = pusty placeholder (bez Kod I na tym etapie)  
- Proporcje do akceptacji vs `projektfv_master.jpg`  

❌ Co nie działa  
- Brak w zakresie STOP  

### A. Root cause
Etap K buduje prawdziwy layout dokumentu zamiast raster-as-background.

### B. Zmienione pliki
- `app/assets/invoice/layout_shell/*`  
- raport niniejszy  

### C. Deploy — nie  
### D. Testy — WeasyPrint 1 page; slot inventory PASS; brak raster MASTER jako bg  
### E. Następny krok — review Desktop; ewentualna kalibracja witraża / rytmu; potem osobne GWO bind/freeze

## Decyzje dla ChatGPT

1. Czy geometria shell (ornament 17.2mm, content 147mm, glass 58mm) akceptujemy względem MASTER?  
2. Czy DO ZAPŁATY (zamiast stack Netto/VAT/Brutto) zostaje w shellu?  
3. Czy po akceptacji idziemy: kalibracja witraża → bind IFG → freeze?

---

STATUS=DONE  
VERDICT=LAYOUT_SHELL_VISUAL_REVIEW_REQUIRED  
PAGE_SIZE=A4_210mm_x_297mm  
ORNAMENT_X_MM=17.2  
STAINED_GLASS_MODULE=app/assets/invoice/layout_shell/stained_glass_module.json  
EDITABLE=YES  
TABLE_WIDTH_MM=147  
CONTENT_WIDTH_MM=147  
SLOTS=invoice_number,issue_date,sale_date,due_date,payment_method,bank_account,seller_name,seller_address,seller_nip,buyer_name,buyer_address,buyer_nip,items,vat_summary,amount_due,ksef_number,ksef_qr  
PDF_PAGES=1  
DESKTOP_PREVIEW=/Users/lukasz/Desktop/IFG-LAYOUT-SHELL-0015K.jpg  
IFG_DATA_BOUND=NO  
COMMIT_PERFORMED=NO  
MERGE_PERFORMED=NO  
DEPLOY_PERFORMED=NO  
