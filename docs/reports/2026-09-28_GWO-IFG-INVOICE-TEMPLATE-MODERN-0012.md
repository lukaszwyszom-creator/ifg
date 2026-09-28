# GWO-IFG-INVOICE-TEMPLATE-MODERN-0012

**Date:** 2026-09-28  
**Branch:** `gwo/ifg-invoice-template-0011`  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011`  
**BASE_SHA:** `4b03bf4e6312538846ae7b82c002c19a6a2bf030`  
**origin/production at start:** same SHA (rebase: not needed)

---

## STATUS

| Field | Value |
|-------|-------|
| **VERDICT** | **MODERN_TEMPLATE_PR_READY** |
| STATUS_BADGE | **HIDDEN** |
| UNIT_GROSS_PRICE_COLUMN | **NOT_PRESENT** |
| VAT_SUMMARY | by `vat_rate` from existing item totals |
| ADDRESS_FORMATTING | presentation helper; no None/null; partial REGON OK |
| A4_PRINT_CSS | `@page size A4`, thead repeat, break-inside avoid |
| MULTIPAGE | CSS + 54-item unit test + 51-item smoke |
| HTML_ESCAPE | **PASS** |
| TESTS | 23 passed (`test_pdf_service.py`) |
| PREVIEW_SMOKE | **PASS** |
| PDF_SMOKE | **PASS** (same HTML → WeasyPrint) |
| KSEF_CHANGED | **NO** |
| DB_CHANGED | **NO** |
| API_CONTRACT_CHANGED | **NO** |
| WORKTREE | **PRESERVED_PENDING_REVIEW** |
| PR | https://github.com/lukaszwyszom-creator/ifg/pull/4 |
| FINAL_HEAD | `5ebd8e68ae1be02dd114c20f8861ab3c38e85eb0` |
| NEXT_GWO | GWO-IFG-INVOICE-TEMPLATE-MODERN-0012-MERGE-GATE |

---

## 🩷 STATUS KOŃCOWY

✅ **Co działa**
- Modern A4 template in `render_invoice_html`
- Preview HTML + WeasyPrint PDF share one template
- Badge statusu IFG ukryty
- Brak kolumny jednostkowej „Cena brutto”
- Lp., VAT summary, DO ZAPŁATY, partial address, escape
- 23 unit tests PASS; smoke HTML+PDF PASS

⚠️ **Znane problemy**
- Worktree zachowany do merge gate (nie usuwać przed review)
- Widoczne smoke artifacts lokalne `/tmp/ifg_invoice_modern_smoke.{html,pdf}` (nie w repo)

❌ **Co nie działa**
- Brak (w zakresie 0012)

---

## A. Root cause

Audyt 0011: prezentacja = jeden backend HTML. 0012 przebudowuje wyłącznie ten renderer.

## B. Zmienione pliki

- `app/services/pdf_service.py`
- `tests/unit/test_pdf_service.py`
- `docs/reports/2026-09-28_GWO-IFG-INVOICE-TEMPLATE-AUDIT-0011.md` (docs commit)
- ten raport

## C. Deploy

Nie (zakaz). PR bez merge.

## D. Testy

```bash
python -m pytest tests/unit/test_pdf_service.py -q
# 23 passed
```

Smoke: 51 pozycji → HTML + PDF `%PDF` / `%%EOF`.

## E. Następny krok

**GWO-IFG-INVOICE-TEMPLATE-MODERN-0012-MERGE-GATE** — review PR, merge do production, verify, worktree remove + prune.

---

## DESIGN_IMPLEMENTED

- HEADER: sprzedawca (lewa) + tytuł dokumentu + numer (prawa)
- META: wystawienie / sprzedaż / termin / metoda (tylko dostępne)
- PARTIES: Sprzedawca | Nabywca
- ITEMS: Lp., Nazwa, Ilość, Jm., Cena netto, VAT, Netto, VAT kwota, Brutto
- VAT summary wg stawek z sum pozycji
- Totals Netto/VAT/Brutto z `InvoiceResponse`
- DO ZAPŁATY dominant + termin/metoda/rachunek
- Korekta: tytuł + `Przyczyna korekty` tylko dla KOR*
- Numer KSeF tylko gdy obecny
- `@page A4`, print CSS, thead repeat, break-inside

## CORRECTION_REASON

Renderowane **tylko** gdy `invoice_type ∈ {KOR, KOR_ZAL, KOR_ROZ}` i reason niepusty.  
Nie używane jako ogólne uwagi. Brak pola notes → brak sekcji UWAGI.

## RISKS

- WeasyPrint vs browser print drobne różnice layoutu (ten sam HTML mitigates)
- Sumy VAT-by-rate z pozycji mogą różnić się groszowo od header totals przy historycznych danych — totals główne nadal z `InvoiceResponse`
- Podwójne pokazanie sprzedawcy (header + parties) — świadome wg briefu

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

- `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011/docs/reports/2026-09-28_GWO-IFG-INVOICE-TEMPLATE-MODERN-0012.md`
