# GWO-IFG-SALES-INVOICE-ELEGANT-0015A-ASSET-QR-CLOSEOUT

**Data:** 2026-09-30  
**PR:** https://github.com/lukaszwyszom-creator/ifg/pull/6  
**BRANCH:** `gwo/ifg-sales-invoice-elegant-0015`  
**WORKTREE:** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015`  
**BASE HEAD (pre-0015A):** `5afb33c5eaebadc56edc5ffaa01b24afa577f09c`  
**Merge / Deploy DS723:** **NIE**

---

## STATUS / OUTPUT

| Field | Value |
|-------|-------|
| **STATUS** | QR implemented; stained-glass asset still missing |
| **VERDICT** | **ASSET_BLOCKED** |
| **FINAL_HEAD** | `be8fc548985d2a5b052ba637487fb983baa004c5` |
| **STAINED_GLASS_ASSET** | **STAINED_GLASS_ASSET_REQUIRED** (no operator file found in repo / Downloads / AgentStores) |
| **QR_SOURCE_DATA** | **AVAILABLE** via `transmissions.xml_content` (exact FA(3) bytes submitted to KSeF) |
| **QR_MECHANISM** | Kod I — `SHA-256(xml) → base64url` + seller NIP + `issue_date` (P_1) |
| **QR_PAYLOAD_EXAMPLE** | `https://qr-test.ksef.mf.gov.pl/invoice/9670402857/10-09-2026/yVyMFs90_hhabn3HVhdEpjr1xJKxjE6DpMsVUI2K9Ic` |
| **QR_LIBRARY** | `segno>=1.6,<2.0` → PNG data-URI (no network fetch) |
| **TESTS** | **45 PASS** (`pytest tests/unit/test_pdf_service.py`) |
| **SALE_VISUAL** | **PASS** (`/tmp/ifg-0015a-smoke/sale.html` + `.pdf`, 1 page) |
| **PURCHASE_REGRESSION** | **PASS** (classic modern; no QR / no elegant markers) |
| **X_ALIGNMENT_DELTA** | **0** (CSS contract `--layout-axis-x: 50%` unchanged) |
| **DATE_SEPARATOR_HEIGHT_DELTA** | **0** (`--date-sep-height` unchanged) |
| **PR6_STATE** | open — QR gate closed; asset gate open |

### Verdict options (selected)

- [ ] PR6_READY_FOR_FINAL_MERGE_GATE
- [ ] QR_BLOCKED_MISSING_SOURCE_DATA
- [x] **ASSET_BLOCKED**

---

## 1. Witraż

Searched: repo `app/assets/invoice/`, Downloads, Desktop, Documents, AgentStores, `/tmp`.  
**No approved stained-glass file found.**  
Template slot unchanged; marker `STAINED_GLASS_ASSET_REQUIRED` retained.  
**Do not** invent/download branding.

Place file at:

`app/assets/invoice/stained_glass.png`

to clear this gate (layout/clipping/scale already prepared).

---

## 2. QR audit (facts)

| Source | Finding |
|--------|---------|
| `InvoiceResponse` | has `ksef_reference_number`; **no** FA(3) hash field |
| Invoice ORM | no durable invoice-hash column |
| `transmissions.xml_content` | **yes** — exact submitted FA(3) bytes (set in `SubmitInvoiceJobHandler`) |
| Transmission success | prefer `status=="success"` with `xml_content`; fallback any non-empty `xml_content` |
| `KSeFMapper.xml_content_hash` | hex C14N — **not** used for QR (different encoding purpose) |
| Client `invoiceHash` | standard base64 of SHA-256(raw XML) — same digest family as QR, different encoding |

**Conclusion:** hash FA(3) **is durably available** without a new DB column → implement QR (not `QR_BLOCKED_MISSING_SOURCE_DATA`).

Spec: CIRFMF `kody-qr.md` Kod I:

`{qr-base}/invoice/{NIP}/{DD-MM-YYYY}/{hash_base64url}`

---

## 3. Implementation

- `app/services/ksef_qr.py` — URL builder + PNG data-URI via segno + transmission XML resolver
- `app/services/pdf_sale_elegant.py` — real QR only when NIP + issue_date + xml complete; else `INCOMPLETE` (no fake)
- `app/services/pdf_service.py` — pass-through `ksef_xml_bytes` / `ksef_environment` for sale only
- `app/api/routers/invoices.py` — preview/PDF load `TransmissionRepository.list_for_invoice` → `xml_content`
- `pyproject.toml` — add `segno`
- No DB migration; no KSeF mapper change; purchase template untouched

---

## 🩷 STATUS KOŃCOWY

✅ Co działa  
- Prawdziwy Kod I QR (segno PNG data-URI) z `transmissions.xml_content`  
- Brak fake QR / brak kodowania samego numeru KSeF  
- 45 testów PASS; sale smoke PDF; purchase regression PASS  
- Layout axis / date separator heights unchanged (Δ=0 contract)  

⚠️ Znane problemy  
- Finalny witraż **nie dostarczony** → **ASSET_BLOCKED**  
- QR wymaga istniejącej transmisji z `xml_content` (faktury bez submit → slot `INCOMPLETE`)  

❌ Co nie działa  
- Finalny branding witraża (brak pliku operatora)  

### A. Root cause
Asset gate: brak zatwierdzonego pliku. QR gate: zamknięty danymi z `transmissions.xml_content`.

### B. Zmienione pliki
- `app/services/ksef_qr.py` (new)
- `app/services/pdf_sale_elegant.py`
- `app/services/pdf_service.py`
- `app/api/routers/invoices.py`
- `app/assets/invoice/README.md`
- `pyproject.toml`
- `tests/unit/test_pdf_service.py`
- ten raport

### C. Deploy
Nie — przed final merge gate (czeka na witraż).

### D. Testy
`pytest tests/unit/test_pdf_service.py` → **45 passed**.

### E. Następny krok
Operator dostarcza `stained_glass.png` → commit na ten sam PR #6 → `PR6_READY_FOR_FINAL_MERGE_GATE` → dopiero potem merge/deploy.

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Dostarczyć finalny plik witraża (`app/assets/invoice/stained_glass.png`) — bez tego merge gate pozostaje **ASSET_BLOCKED**.
2. Potwierdzić, że źródło QR z `transmissions.xml_content` (bez nowego pola DB) jest akceptowane jako ostateczne.

## GENERATED REPORTS

- `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-sales-invoice-elegant-0015/docs/reports/2026-09-30_GWO-IFG-SALES-INVOICE-ELEGANT-0015A-ASSET-QR-CLOSEOUT.md`
