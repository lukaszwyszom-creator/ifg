# GWO-IFG-SALES-INVOICE-FROZEN-BINDER-0015J-B

**Data:** 2026-10-01  
**Branch / worktree:** `gwo/ifg-sales-invoice-elegant-0015` @ `b6e82da`  
**Zakres:** POC binder DATA→SLOT na zamrożonym MASTER (bez podmiany production renderer)

## IMPORT

Rozpakowano `/Users/lukasz/Downloads/IFG_invoice_frozen_base.zip` →  
`docs/design_refs/frozen_sales_invoice/`

- `sale_invoice_master_locked.png`
- `sale_invoice_master_locked.svg`
- `sale_invoice_slots.json` (`layout_locked=true`)
- `README_FROZEN_BASE.md`

## ARCHITEKTURA POC

```
MASTER (immutable pixels / SVG frame)
  +
DATA → SLOT masks (cream) + IFG values
```

- Nowy serwis: `app/services/frozen_sales_invoice.py`
- Skrypt: `scripts/render_frozen_sales_invoice_poc.py`
- **Nie** podłączono do `pdf_service` / production path (`render_sale_elegant_html` bez zmian ścieżki)

### Binding

Fixture IFG (`_sample_invoice` family): `FV/1/2026`, remaining_amount → DO ZAPŁATY, PL formatters, CENA NETTO+CENA BRUTTO, partial address, escaping, prawdziwy Kod I QR (`ksef_qr.py` bez zmian mechanizmu).

## RENDER

| Artefakt | Ścieżka |
|----------|---------|
| HTML | `/tmp/ifg-frozen-binder/sale.html` |
| PDF | `/tmp/ifg-frozen-binder/sale.pdf` |
| PNG (MASTER grid gate) | `/tmp/ifg-frozen-binder/sale-page-1.png` |
| Desktop | `~/Desktop/IFG-FROZEN-BINDER-REVIEW.jpg` |

- PDF_PAGES=1 (WeasyPrint A4, `preserveAspectRatio=xMidYMid meet`)
- Gate PNG = kopia MASTER + tylko maski/wartości slotów (statyczne piksele bez zmian)

## GEOMETRY GATE vs MASTER

| Metric | Value |
|--------|-------|
| ORNAMENT_DELTA | 0.000 |
| STAINED_GLASS_DELTA | 0.000 |
| BRAND_DELTA | 0.000 |
| SECTION_GEOMETRY_DELTA | 0.000 |
| STATIC_GEOMETRY_CHANGED | NO |

## SLOTS

Bound: `invoice_number`, `issue_date`, `sale_date`, `due_date`, `payment_method`, `bank_account`, `seller_name`, `seller_address`, `seller_nip`, `buyer_name`, `buyer_address`, `buyer_nip`, `items`, `vat_summary`, `amount_due`, `ksef_number`, `ksef_qr`

SLOT_OVERFLOWS: **brak**

## STOP

- commit / merge / deploy — **NIE**
- purchase — nietknięte
- production renderer — **nie zastąpiony**

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- Import frozen base + `layout_locked=true`  
- POC binder DATA→SLOT + Kod I QR  
- Geometry deltas = 0 dla ornament / witraż / brand / section  
- Artefakty `/tmp/ifg-frozen-binder/*` + Desktop JPEG  

⚠️ Znane problemy  
- Composite PNG table to kompaktowy tekst w slocie `items_table` (nie przebudowa geometrii MASTER) — HTML PDF ma pełniejszą tabelę w tym samym rect  
- Wymaga wizualnego review operatora przed ewentualnym etapem podmiany production path  

❌ Co nie działa  
- Brak w zakresie POC STOP  

### A. Root cause
Binder nie mutuje MASTER — tylko maskuje sloty i wpisuje dane IFG.

### B. Zmienione pliki
- `docs/design_refs/frozen_sales_invoice/*` (import)
- `app/services/frozen_sales_invoice.py` (nowy POC)
- `scripts/render_frozen_sales_invoice_poc.py` (nowy)
- raport niniejszy

### C. Deploy
Nie.

### D. Testy
- Slot inventory: 17/17 bound  
- Overflow gate: 0  
- Geometry MAE: 0.000 na regionach statycznych  
- PDF 1 page; QR `data-qr-status=ok`

### E. Następny krok
Operator: review Desktop vs MASTER. Po akceptacji — osobne GWO na podpięcie production path (bez luzowania freeze).

## Decyzje dla ChatGPT

1. Czy geometry gate (delta=0) + fixture bind akceptujemy jako PASS etapu B?  
2. Czy table density (CENA NETTO+CENA BRUTTO w `items_table`) jest OK bez SLOT_OVERFLOW?  
3. Czy kolejny GWO ma podmienić production renderer na frozen binder?

---

STATUS=DONE  
VERDICT=FROZEN_BINDER_VISUAL_REVIEW_REQUIRED  
FROZEN_MASTER=docs/design_refs/frozen_sales_invoice/sale_invoice_master_locked.png  
SLOT_CONTRACT=docs/design_refs/frozen_sales_invoice/sale_invoice_slots.json  
SLOTS_BOUND=invoice_number,issue_date,sale_date,due_date,payment_method,bank_account,seller_name,seller_address,seller_nip,buyer_name,buyer_address,buyer_nip,items,vat_summary,amount_due,ksef_number,ksef_qr  
SLOT_OVERFLOWS=NONE  
STATIC_GEOMETRY_CHANGED=NO  
ORNAMENT_DELTA=0.000  
STAINED_GLASS_DELTA=0.000  
BRAND_DELTA=0.000  
SECTION_GEOMETRY_DELTA=0.000  
TESTS=geometry_mae_zero;slots_bound_17;overflow_0;pdf_pages_1;kod_i_qr_ok  
PDF_PAGES=1  
DESKTOP_PREVIEW=/Users/lukasz/Desktop/IFG-FROZEN-BINDER-REVIEW.jpg  
COMMIT_PERFORMED=NO  
MERGE_PERFORMED=NO  
DEPLOY_PERFORMED=NO  
