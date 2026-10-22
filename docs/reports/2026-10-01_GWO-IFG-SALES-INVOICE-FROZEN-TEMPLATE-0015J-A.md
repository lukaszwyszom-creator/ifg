# GWO-IFG-SALES-INVOICE-FROZEN-TEMPLATE-0015J-A

**Data:** 2026-10-01  
**Branch / worktree:** `gwo/ifg-sales-invoice-elegant-0015` @ `b6e82da`  
**Zakres:** STATIC TEMPLATE + NAMED DATA SLOTS (bez IFG binder)

## CEL

Zamrożony wizualnie formularz faktury sprzedażowej na podstawie `docs/design_refs/projektfv_master.jpg`.  
Etap A — wyłącznie dokument/szablon wizualny + sloty. Brak bindingu `InvoiceResponse`.

## ARCHITEKTURA (zrealizowana)

```
STATIC TEMPLATE  +  NAMED DATA SLOTS
( IFG DATA BINDER — poza zakresem 0015J-A )
```

### Pliki szablonu

| Plik | Rola |
|------|------|
| `app/assets/invoice/sale_template/sale_template.html` | HTML + `data-slot=*` + dane wizualizacyjne MASTER |
| `app/assets/invoice/sale_template/sale_template.css` | **FROZEN** geometria / typografia / spacing |
| `app/assets/invoice/sale_template/invoice_frame.svg` | Statyczna rama (ornament/osie) — asset freeze package |
| `app/assets/invoice/sale_template/stained_glass.png` | Witraż (kopia z `app/assets/invoice/`) |
| `app/assets/invoice/sale_template/qr_fixture.png` | QR fixture z renderu PR #6 (Kod I bez zmiany mechanizmu) |
| `app/assets/invoice/sale_template/README.md` | Kontrakt freeze |

## SLOTY

Wymagane sloty obecne (`data-slot`):

`invoice_number`, `issue_date`, `sale_date`, `due_date`, `payment_method`, `bank_account`,  
`seller_name`, `seller_address`, `seller_nip`, `buyer_name`, `buyer_address`, `buyer_nip`,  
`items`, `vat_summary`, `amount_due`, `ksef_number`, `ksef_qr`

Dodatkowe kontenery pomocnicze: `brand`, `seller`, `buyer`, `item`, `stained_glass`.

## DANE WIZUALIZACYJNE (nie runtime)

- FV/15/09/2026 · 2026-09-18 / 2026-09-18 / 2026-10-31 · Przelew  
- Rachunek: 48 1090 1896 0000 0001 0647 4926  
- Parties jak MASTER  
- Pozycja: 150 szt. · 114,29 / 120,00 · 5% · 17 142,86 / 857,14 / 18 000,00  
- Do zapłaty: **18 000,00 PLN** (bez dodatkowego Netto/VAT po prawej)  
- KSEF testowy + QR fixture PR #6

## RENDER (STOP)

| Artefakt | Ścieżka |
|----------|---------|
| HTML | `/tmp/ifg-0015j-a/template.html` |
| PDF | `/tmp/ifg-0015j-a/template.pdf` |
| PNG | `/tmp/ifg-0015j-a/template.png` |
| Desktop | `~/Desktop/IFG-INVOICE-TEMPLATE-FROZEN.jpg` |

- **PDF_PAGES:** 1 (A4)  
- Renderer: WeasyPrint 70  
- Raster preview: qlmanage 2480px → PNG/JPEG

## NIE ZMIENIONO (świadomie)

- `InvoiceResponse` binding — brak  
- `pdf_service` / `pdf_sale_elegant` business logic — brak  
- mapper / DB / purchase — brak  
- mechanizm Kod I (`ksef_qr.py`) — brak  
- commit / merge / deploy — brak

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- Statyczny szablon HTML/CSS + SVG + witraż + QR fixture w `sale_template/`  
- Wszystkie wymagane `data-slot` obecne  
- Render 1×A4: HTML/PDF/PNG + Desktop JPEG  
- Tabela z CENA NETTO + CENA BRUTTO; po prawej wyłącznie DO ZAPŁATY  
- Brak bindingu IFG / brak commit/merge/deploy  

⚠️ Znane problemy  
- Wierność pikselowa vs MASTER wymaga **akceptacji operatora** (FROZEN dopiero po review)  
- MASTER historycznie pokazywał stack Netto/VAT/Brutto — zgodnie z GWO §7 użyto DO ZAPŁATY  
- Preview Desktop to JPEG z qlmanage (nie natywny WeasyPrint PNG API w v70)  

❌ Co nie działa  
- Brak — zakres etapu A domknięty do review wizualnego  

### A. Root cause
Etap A celowo oddziela zamrożony wzorzec wizualny od binderów IFG.

### B. Zmienione pliki
- `app/assets/invoice/sale_template/*` (nowy katalog szablonu)  
- raport niniejszy  

### C. Deploy
Nie — STOP po renderze.

### D. Testy
- WeasyPrint render → `PDF_PAGES=1`  
- Inwentaryzacja slotów → wszystkie wymagane obecne  
- Brak zmian w `pdf_sale_elegant.py` / Kod I  

### E. Następny krok
Operator: wizualny review `~/Desktop/IFG-INVOICE-TEMPLATE-FROZEN.jpg` vs `projektfv_master.jpg`.  
Po akceptacji → **FROZEN** CSS/frame; etap B = IFG DATA BINDER (bez swobodnej edycji geometrii).

## Decyzje dla ChatGPT

1. Czy geometria `sale_template.css` / frame zostaje **FROZEN** (akceptacja MASTER fidelity)?  
2. Czy DO ZAPŁATY (bez Netto/VAT po prawej) jest ostatecznym kontraktem względem MASTER?  
3. Czy przechodzimy do etapu B (binder `InvoiceResponse` → sloty) bez dalszych korekt CSS?

---

STATUS=DONE  
VERDICT=FROZEN_TEMPLATE_VISUAL_REVIEW_REQUIRED  
TEMPLATE_HTML=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/app/assets/invoice/sale_template/sale_template.html  
TEMPLATE_CSS=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/app/assets/invoice/sale_template/sale_template.css  
STATIC_FRAME=/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/app/assets/invoice/sale_template/invoice_frame.svg  
SLOTS=invoice_number,issue_date,sale_date,due_date,payment_method,bank_account,seller_name,seller_address,seller_nip,buyer_name,buyer_address,buyer_nip,items,vat_summary,amount_due,ksef_number,ksef_qr  
PDF_PAGES=1  
TEST_RENDER=/tmp/ifg-0015j-a/  
DESKTOP_PREVIEW=/Users/lukasz/Desktop/IFG-INVOICE-TEMPLATE-FROZEN.jpg  
IFG_DATA_BOUND=NO  
COMMIT_PERFORMED=NO  
MERGE_PERFORMED=NO  
DEPLOY_PERFORMED=NO  
