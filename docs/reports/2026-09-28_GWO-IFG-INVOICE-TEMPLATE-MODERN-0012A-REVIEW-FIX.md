# GWO-IFG-INVOICE-TEMPLATE-MODERN-0012A-REVIEW-FIX

**Date:** 2026-09-28  
**Branch:** `gwo/ifg-invoice-template-0011`  
**PR:** https://github.com/lukaszwyszom-creator/ifg/pull/4  
**Worktree:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011`

---

## STATUS

| Field | Value |
|-------|-------|
| **VERDICT** | **PR4_READY_FOR_MERGE_GATE** |
| DO_ZAPLATY_SOURCE | `remaining_amount` if not None, else `total_gross` |
| PARTIAL_PAYMENT_TEST | PASS (1000 gross / 400 remaining → DO ZAPŁATY 400.00) |
| PAID_TEST | PASS (remaining 0 → 0.00 PLN) |
| FALLBACK_TEST | PASS (remaining None → total_gross) |
| VAT_ZW_SUPPORT | **NOT_DISTINGUISHABLE** from presentation model |
| VAT_LIMITATION | `InvoiceItemResponse.vat_rate: Decimal` only; XML parser maps `zw`/`np` → `Decimal("0")`; PDF renders `0%` — no fake “zw.” |
| VISUAL_PREVIEW | PASS (1-item + partial in browser) |
| VISUAL_PRINT | PASS (`@media print` / print CSS; button hidden) |
| VISUAL_PDF | PASS (WeasyPrint; 1-item=1 page after flex fix) |
| MULTIPAGE_VISUAL | PASS (51 items → 8 A4 pages; thead CSS present) |
| TABLE_READABILITY | **ACCEPTABLE** — 9 cols, body cells ~9.5pt, headers 8pt; not squeezed further |
| TESTS | 29 passed |
| PR4_STATE | OPEN — fix pushed |
| KSEF_CHANGED | NO |
| DB_CHANGED | NO |
| NEXT_GWO | GWO-IFG-INVOICE-TEMPLATE-MODERN-0012-MERGE-GATE |

---

## 🩷 STATUS KOŃCOWY

✅ **Co działa**
- DO ZAPŁATY uses `remaining_amount` (partial/paid/fallback covered by tests)
- Visual: short invoice fits 1 PDF page (CSS grid → flex for WeasyPrint)
- 9-column table readable without further font shrink
- VAT limitation documented; Decimal rates (0/5/8/23) render correctly

⚠️ **Znane problemy / GDD**
- Presentation cannot show `zw.` / `np.` distinctly from `0%` without model change (out of scope)

❌ **Co nie działa**
- Brak (w zakresie 0012A)

---

## A. Root cause

1. DO ZAPŁATY wrongly used `total_gross` ignoring payment allocations already exposed as `remaining_amount`.
2. WeasyPrint poorly laid out CSS `display:grid` (esp. pay-details) → inflated “DO ZAPŁATY” block → empty second page on short invoices.

## B. Zmienione pliki

- `app/services/pdf_service.py` — amount-due source + flex layout
- `tests/unit/test_pdf_service.py` — payment + page-count + VAT limitation tests
- this report

## C. Deploy

Nie. PR #4 nie merge’owany.

## D. Testy

```text
29 passed  (tests/unit/test_pdf_service.py)
```

Smoke: one/partial = 1 page; multi 51 items = 8 pages; due amounts 210 / 400 / 2945.50.

## E. Następny krok

Merge gate PR #4 → verify production → remove temporary worktree.

---

## VAT_LIMITATION (GDD)

| Fakt | Szczegół |
|------|----------|
| API field | `InvoiceItemResponse.vat_rate: Decimal` |
| Purchase XML | `zw`/`np` coerced to `Decimal("0")` in `xml_parser._parse_item` |
| KSeF emit | mapper has string keys `zw`/`np`, but domain line rate remains Decimal |
| PDF 0012/0012A | formats Decimal as `N%` (e.g. `0%`); does **not** invent `zw.` |
| Future | require explicit rate label/enum on item response before rendering `zw.`/`np.` |

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

- `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011/docs/reports/2026-09-28_GWO-IFG-INVOICE-TEMPLATE-MODERN-0012A-REVIEW-FIX.md`
