# GWO-IFG-SALES-INVOICE-ELEGANT-TEMPLATE-0015

**Data:** 2026-09-30  
**FINAL_HEAD:** `40c75bc4a236e67f7737fa373344ceb80642c97b`  
**PR:** https://github.com/lukaszwyszom-creator/ifg/pull/6 (**otwarty, NIE zmergowany**)  
**FEATURE_HEAD:** `84db52be59420227b92ac0f0df5267d748459991`  
**BASE_SHA:** `45cfacf828efd125a2028f83152b9654bbfea404` (`origin/production`)  
**BRANCH:** `gwo/ifg-sales-invoice-elegant-0015`  
**WORKTREE:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**Merge:** NIE  
**Deploy DS723:** NIE  

---

## STATUS / OUTPUT

| Field | Value |
|-------|-------|
| **VERDICT** | **PR_READY_WITH_ASSET_GATES** |
| BASE_SHA | `45cfacf828efd125a2028f83152b9654bbfea404` |
| FINAL_HEAD | `40c75bc4a236e67f7737fa373344ceb80642c97b` |
| BRANCH | `gwo/ifg-sales-invoice-elegant-0015` |
| PR | https://github.com/lukaszwyszom-creator/ifg/pull/6 |
| FILES_CHANGED | `app/services/pdf_service.py`, `app/services/pdf_sale_elegant.py`, `app/assets/invoice/README.md`, `tests/unit/test_pdf_service.py`, ten raport |
| TESTS | **38 PASS** |
| VISUAL_SMOKE | **PASS** (`/tmp/ifg-0015-smoke/`) |
| PDF_PAGES | sale **1**; multipage 51 pozycji **3** |
| DATE_SEPARATOR_X | `1515.609375` px (viewport) |
| PARTIES_SEPARATOR_X | `1515.609375` px |
| **X_ALIGNMENT_DELTA** | **0** |
| DATE_SEPARATOR_HEIGHT | `39.8359375` px |
| OTHER_DATE_SEPARATOR_HEIGHT | `39.8359375` px |
| QR_STATUS | **MISSING_MECHANISM** |
| STAINED_GLASS_ASSET | **STAINED_GLASS_ASSET_REQUIRED** |
| PURCHASE_TEMPLATE_REGRESSION | **PASS** (classic modern, bez Cena brutto jednostkowej) |
| KSEF_TOUCHED | **NO** |
| DB_TOUCHED | **NO** |
| API_TOUCHED | **NO** |
| NEXT_GWO | GWO-0015A: QR mechanizm + witraż asset + visual finalize / merge-gate |

---

## Architektura

- Wspólny silnik: `render_invoice_html` / `render_invoice_pdf`
- **Sale** → `pdf_sale_elegant.render_sale_elegant_html`
- **Purchase** → `_render_classic_modern_html` (produkcyjny modern 0014 — bez regresji)
- Shared helpers: adresy, VAT summary, `remaining_amount` / DO ZAPŁATY, escape — bez duplikacji logiki fiskalnej

---

## QR — STOP (bez atrapy)

Brak w IFG kompletnego mechanizmu prawidłowego kodu weryfikacyjnego KSeF:

1. **Brak zależności** `qrcode` / `segno` (lub równoważnej) w `pyproject.toml`
2. **Brak buildera URL** `https://qr.ksef.mf.gov.pl/invoice/{NIP}/{DD-MM-YYYY}/{hash_base64url}` (Kod I)
3. **Brak w `InvoiceResponse`** przechowywanego skrótu FA(3) XML w formacie base64url wymaganym przez QR
4. Istniejące `KSeFMapper.xml_content_hash` zwraca **hex SHA-256 C14N**, nie base64url; użycie wymagałoby regeneracji XML w ścieżce PDF (ryzyko rozjazdu z XML wysłanym do KSeF) — **nie zaimplementowano**

Szablon ma zarezerwowany `.qr-slot` z `data-qr-status="MISSING_MECHANISM"` — **bez** fake QR / bez kodowania samego numeru KSeF.

---

## Witraż

- Kanoniczna ścieżka: `app/assets/invoice/stained_glass.png|svg|jpg`
- Brak pliku w repo → slot CSS `data-stained-glass="STAINED_GLASS_ASSET_REQUIRED"`
- Layout wymienialny (data-URI gdy asset pojawi się)
- **Nie** pretendujemy, że placeholder jest brandingiem Ikony

---

## Geometry gate (programowy)

CSS: `--layout-axis-x: 50%` + `meta-dates` 4-kolumnowy grid + `parties` 2-kolumnowy grid → środkowy separator dat i separator SPRZEDAWCA|NABYWCA współdzielą tę samą oś.

Pomiar browser CDP na `/tmp/ifg-0015-smoke/sale.html`:

| Metric | Value |
|--------|-------|
| X_ALIGNMENT_DELTA | **0** |
| HEIGHT_DELTA (date seps) | **0** |

---

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- Elegant sale template (ivory/navy/gold, ornament, IKONA WYDAWNICTWO, tabela z CENA BRUTTO, PL tysiące, ciche DO ZAPŁATY)  
- Purchase bez regresji  
- 38 testów PASS; smoke HTML/PDF; X_ALIGNMENT_DELTA=0  

⚠️ Znane problemy  
- QR: MISSING_MECHANISM  
- Witraż: STAINED_GLASS_ASSET_REQUIRED  
- Brak finalnego assetu graficznego operatora w repo — layout odtworzony ze specyfikacji GWO  

❌ Co nie działa  
- Prawdziwy QR KSeF (świadomie niezaimplementowany)  

### A. Root cause
Nowy wariant prezentacji sprzedażowej; zakup zostaje na classic modern.

### B. Zmienione pliki
Jak w tabeli STATUS.

### C. Deploy
Nie.

### D. Testy
`pytest tests/unit/test_pdf_service.py` → 38 passed.

### E. Następny krok
Dostarczyć asset witraża + GWO mechanizmu QR (hash + URL + lib) → potem merge/deploy gate.

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Potwierdzić, że layout ze smoke (`/tmp/ifg-0015-smoke/sale.html` / `.pdf`) jest wierny zaakceptowanemu wzorcowi (brak obrazu wzorca w repo).
2. Dostarczyć plik witraża do `app/assets/invoice/stained_glass.png` (lub SVG).
3. Zdecydować NEXT GWO dla QR: skąd brać hash FA(3) (zapis przy submit vs regeneracja) i czy dodać `segno`/`qrcode` do zależności.

## GENERATED REPORTS

- `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/docs/reports/2026-09-30_GWO-IFG-SALES-INVOICE-ELEGANT-TEMPLATE-0015.md`
