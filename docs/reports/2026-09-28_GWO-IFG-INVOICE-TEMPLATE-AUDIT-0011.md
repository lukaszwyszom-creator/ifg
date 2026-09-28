# GWO-IFG-INVOICE-TEMPLATE-AUDIT-0011

**Date:** 2026-09-28  
**Type:** AUDYT + PROJEKT (bez implementacji UI)  
**Canonical:** `/Volumes/WorkspaceSSD/projects/ifg_standalone`  
**Worktree (temporary):** `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011`  
**Branch:** `gwo/ifg-invoice-template-0011`  
**BASE_SHA:** `4b03bf4e6312538846ae7b82c002c19a6a2bf030` (= `origin/production`)  
**OLD/quarantine:** NOT used

---

## STATUS

| Field | Value |
|-------|-------|
| **VERDICT** | **READY_FOR_MODERN_TEMPLATE_IMPLEMENTATION** |
| BASE_SHA | `4b03bf4e6312538846ae7b82c002c19a6a2bf030` |
| BRANCH | `gwo/ifg-invoice-template-0011` |
| WORKTREE | `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011` |
| REFACTOR_REQUIRED | **LIMITED** |
| DS723_TOUCHED | NO |
| KSEF_TOUCHED | NO |
| DB_TOUCHED | NO |
| FUNCTIONAL_COMMIT | NO |
| NEXT_GWO | GWO-IFG-INVOICE-TEMPLATE-MODERN-0012 |

---

## 🩷 STATUS KOŃCOWY

✅ **Co działa**
- Jedno źródło prawdy prezentacji: `render_invoice_html` → preview HTML + WeasyPrint PDF
- Frontend tylko konsumuje HTML/PDF (iframe / blob / download)
- Granica KSeF jest czysta: XML osobno (`KSeFMapper`), PDF nie generuje FA(3)
- Istniejące testy `test_pdf_service.py` pokrywają bank, formaty, light paper, `@media print`
- Branch + tymczasowy worktree z `origin/production` OK

⚠️ **Znane problemy (prezentacja)**
- Brak `@page` / A4 / page-break / powtarzania thead
- Brak kolumny Lp.
- Brak podsumowania VAT wg stawek
- Brak pola „uwagi” w modelu faktury (jest tylko `correction_reason` — nie w PDF)
- Adres w PDF = surowy `address` + `city` ze snapshota (nie `format_adres_l1`)
- Status IFG (badge) na dokumencie handlowym — dyskusyjne dla „modern A4”
- Brak logo / QR (oczekiwane jako future)

❌ **Co nie działa**
- Brak (w zakresie audytu — nic nie zepsuto)

---

## A. Root cause (stan obecny)

IFG nigdy nie zbudowało Reactowego szablonu druku. Cały human-readable sheet to **inline HTML+CSS string** w backendzie. Preview i PDF to ten sam HTML. Modernizacja = zmiana tego jednego renderera (plus regresje), bez ruszania KSeF/DB/modeli fiskalnych.

## B. Zmienione pliki (ten GWO)

- Tylko ten raport w worktree.
- Brak zmian funkcjonalnych / CSS / PDF / commitów feature.

## C. Deploy

Nie wykonano (zakaz).

## D. Testy

Tylko odczyt istniejących. Propozycja regresji → sekcja 8 / IMPLEMENTATION PLAN.

## E. Następny krok

**GWO-IFG-INVOICE-TEMPLATE-MODERN-0012** — implementacja Option A w `pdf_service.py` (+ rozszerzenie `test_pdf_service.py`). Po merge: usunąć worktree + prune.

---

## CURRENT_PIPELINE

```
PostgreSQL (InvoiceORM + InvoiceItemORM + snapshots JSON)
  → InvoiceRepository / InvoiceMapper
  → InvoiceService.get_invoice
  → Invoice (domain) + compute_remaining_amounts
  → InvoiceResponse.from_domain (+ remaining_amount)
  → SettingsService.get_settings()["seller_bank_account"]
  → resolve_seller_bank_account_for_render(...)
  → render_invoice_html(...)          ← JEDYNY SZABLON PREZENTACJI
       ├─ GET /api/v1/invoices/{id}/preview  → text/html
       │     → FE: SimpleView iframe | InvoiceCardList window/blob | window.print()
       └─ render_invoice_pdf → WeasyPrint.HTML(...).write_pdf()
             → GET /api/v1/invoices/{id}/pdf → application/pdf download / ZIP bulk
```

**KSeF (osobno):** `KSeFMapper.invoice_to_xml` → FA(3) XML → submit/transmission. PDF nie uczestniczy.

---

## KEY_FILES

| Rola | Plik |
|------|------|
| HTML template + print CSS + PDF | `app/services/pdf_service.py` |
| Bank display | `app/services/bank_account.py` |
| Endpoints preview/PDF | `app/api/routers/invoices.py` |
| API schema | `app/schemas/invoice.py` (`InvoiceResponse`, `InvoiceItemResponse`) |
| Domain | `app/domain/models/invoice.py` |
| ORM | `app/persistence/models/invoice.py`, `invoice_item.py` |
| FE API | `frontend-react/src/api/invoices.js` |
| FE preview iframe | `frontend-react/src/pages/simple/SimpleView.jsx` |
| FE card / bulk print/PDF | `frontend-react/src/components/invoice/InvoiceCardList.jsx` |
| FE open mode | `frontend-react/src/components/invoice/invoiceOpenMode.js` |
| FE edit form (nie print) | `frontend-react/src/components/invoice/InvoiceForm.jsx` |
| KSeF XML | `app/integrations/ksef/mapper.py` |
| Adres L1 (KSeF) | `app/domain/party_address.py` |
| Unit tests PDF | `tests/unit/test_pdf_service.py` |
| API PDF smoke | `tests/unit/test_invoice_api.py` (`TestInvoicePdf`) |

**ABSENT:** `templates/` Jinja, React print component, `InvoiceViewModel` / `InvoicePrintModel`, jsPDF/html2canvas/puppeteer dla faktur.

---

## DATA_FLOW (pola prezentacji dziś)

| Element | Źródło | Render w PDF? |
|---------|--------|---------------|
| Numer | `number_local` | TAK (`<h1>Faktura …`) |
| Status IFG | `status` | TAK (badge) |
| Data wystawienia / sprzedaży | `issue_date`, `sale_date` | TAK |
| Waluta | `currency` | TAK |
| Termin płatności | `due_date` | TAK (sekcja płatności) |
| Sposób płatności | `payment_method` | TAK |
| Sprzedawca | `seller_snapshot` name/nip/address/city | TAK |
| Nabywca | `buyer_snapshot` j.w. | TAK |
| Rachunek | settings lub snapshot (purchase) | TAK (warunkowo) |
| Pozycje | `items[]` | TAK (bez Lp.) |
| ISBN | `item.isbn` | TAK (pod nazwą) |
| Sumy | `total_net/vat/gross` | TAK |
| Pozostało / zapłacono | `remaining_amount` | TAK |
| Numer KSeF | `ksef_reference_number` | TAK (banner, jeśli jest) |
| VAT wg stawek | — | **NIE** |
| Uwagi / notes | brak pola notes; `correction_reason` istnieje w domain | **NIE w PDF** |
| Logo | — | **NIE** |
| Adnotacje FA (P_16…) | domain flags | **NIE w PDF** |

---

## PRINT_PDF_MECHANISM

| Mechanizm | Status |
|-----------|--------|
| Backend HTML (inline CSS) | **TAK** — kanoniczny |
| WeasyPrint PDF | **TAK** — `render_invoice_pdf` |
| `window.print()` | **TAK** — przycisk w HTML + bulk w `InvoiceCardList` |
| `@media print` | **TAK** — ukrywa `.print-btn`, light paper, `print-color-adjust: exact` |
| `@page` / `size: A4` | **NIE** (dla faktur; A4 jest tylko w warehouse `BalanceTab`) |
| `page-break` / `break-inside` | **NIE** |
| Powtarzanie thead | markup `<thead>` jest; **brak** CSS `display: table-header-group` / reguł multipage |
| Marginesy print | `body padding: 24px` screen; print `padding: 0` — **brak** mm |
| jsPDF / html2canvas / Puppeteer / Playwright (invoice) | **NIE** |
| React print layout | **NIE** |

**Wniosek:** Preview i PDF to **ten sam** HTML. Zmiana wyglądu w `render_invoice_html` automatycznie trafia do obu ścieżek.

---

## KSEF_BOUNDARY

### A — fiskalne / model / KSeF (NIE ruszać w 0012)

- `app/integrations/ksef/mapper.py` (`invoice_to_xml`)
- `app/integrations/ksef/fa3.xsd`, `xml_parser.py`, `fa3_address.py`
- `app/domain/party_address.py` (`format_adres_l1`, `can_build_adres_l1`)
- `app/worker/job_handlers/submit_invoice.py`, `transmission_service.py`
- Numeracja: `invoice_number_policy.py`
- VAT/totals kalkulacja: `invoice_totals.py`, domain `Invoice` / items
- Modele ORM / migracje DB

### B — human-readable presentation (scope modern template)

- `app/services/pdf_service.py` (+ ewentualnie drobny helper prezentacji adresu **tylko do HTML**)
- Endpointy preview/PDF **bez zmiany kontraktu** (nadal HTML / PDF bytes)
- Testy `tests/unit/test_pdf_service.py`
- FE **tylko** jeśli trzeba dopasować iframe chrome (nie layout faktury)

**Granica kodowa:** PDF może **pokazywać** `ksef_reference_number` jako informację; nie może generować XML, zmieniać snapshotów przy renderze, ani przeliczać VAT inaczej niż wartości już w `InvoiceResponse`.

---

## CURRENT_PRESENTATION_ARCHITECTURE

- **Brak** osobnego ViewModel / PrintModel / PresentationModel.
- Wejście renderera: `InvoiceResponse` (+ opcjonalny `seller_bank_account: str`).
- Formatowanie lokalne w `pdf_service`: `_money`, `_amount`, `_format_quantity`, `_format_vat_rate`, `_unit_price_gross`, `_esc`.
- Mobile ma lokalny `viewModel` w `InvoiceDetailScreen` — **nie współdzielony** z PDF.

**Ocena potrzeby nowego ViewModel:**  
**NIE wymagany** na start. `InvoiceResponse` wystarcza. Ewentualny mały helper `_party_address_lines(snapshot) -> list[str]` wewnątrz `pdf_service` (presentation-only) — bez nowej warstwy architektury.

---

## EXISTING_TESTS

| Test | Co pokrywa |
|------|------------|
| `tests/unit/test_pdf_service.py` | bank sale/purchase, qty, VAT %, unit gross, light paper, `@media print` |
| `tests/unit/test_invoice_api.py` (`TestInvoicePdf`) | endpoint PDF zwraca PDF |
| `tests/e2e_mvp.py` `test_07_pdf_preview` | smoke PDF |
| `tests/unit/test_bank_account.py` | format rachunku |
| `frontend-react/.../invoiceOpenMode.test.js` | edit vs preview |
| `frontend-react/.../partyAddress.test.js` | AdresL1 (KSeF UI) |
| `tests/unit/test_ksef_partial_regon_address.py` | partial address → XML |
| `amountFormatting.test.js` / buyer popup tests | lista kart — nie sheet |

**Luki:** brak unit testu treści `GET /preview`; brak asercji Lp/VAT-by-rate/@page (bo ich nie ma); brak testów multipage.

---

## PROBLEMS_FOUND

1. Brak kontroli A4 (`@page`) — WeasyPrint/browser dziedziczą default.
2. Brak strategii wielostronicowej (break-inside, thead repeat).
3. Brak Lp. w tabeli pozycji.
4. Brak VAT summary per rate (wymagane w modern design).
5. „Do zapłaty” istnieje, ale nie jest wizualnie dominant payment block z rachunkiem w jednym miejscu (rachunek dziś przy sprzedawcy).
6. Status workflow IFG na dokumencie handlowym.
7. Adres częściowy: PDF nie używa logiki AdresL1 → puste `<p>` przy brakach.
8. Brak uwag (notes) w modelu — footer „uwagi” będzie pusty lub tylko `correction_reason` (świadoma decyzja 0012).
9. Kolumny dziś: Nazwa, Ilość, J.m., Cena netto, **Cena brutto**, VAT%, Netto, VAT, Brutto — modern chce Lp. + bez obowiązkowej „Cena brutto” (do decyzji UI; preferencja: zachować dane netto/VAT/brutto, Lp. dodać).

---

## REUSABLE_COMPONENTS

- `render_invoice_html` / `render_invoice_pdf` API publiczne — **zachować sygnatury**
- `resolve_seller_bank_account_for_render`
- `format_bank_account_display`
- `InvoiceResponse` jako DTO
- Istniejące testy `_sample_invoice()` w `test_pdf_service.py`
- FE konsumenci (`getPreview`/`getPdf`) — **bez zmian kontraktu**

---

## REFACTOR_REQUIRED

**LIMITED**

Wystarczy przebudowa markup/CSS w `pdf_service.py` (+ helpery lokalne + testy).  
Nie trzeba: nowego template engine, osobnego FE print stacku, ViewModel layer, zmian backend kontraktu API.

---

## MODERN_TEMPLATE_STRUCTURE (projekt)

```
┌─────────────────────────────────────────────┐
│ HEADER                                      │
│  [logo slot]     FAKTURA VAT                │
│  sprzedawca      nr: FV/…                   │
│  (kompakt)                                  │
├─────────────────────────────────────────────┤
│ META                                        │
│  wystawienia | sprzedaży | termin | metoda  │
├──────────────────────┬──────────────────────┤
│ PARTIES              │                      │
│  Sprzedawca          │  Nabywca             │
│  nazwa, NIP, adres   │  nazwa, NIP, adres   │
├──────────────────────┴──────────────────────┤
│ ITEMS                                       │
│  Lp | Nazwa | Ilość | Jm | Cena netto |     │
│  VAT% | Netto | VAT | Brutto                │
├─────────────────────────────────────────────┤
│ SUMMARY                                     │
│  Netto | VAT wg stawek | Brutto             │
├─────────────────────────────────────────────┤
│ PAYMENT (dominant)                          │
│  DO ZAPŁATY: X XXX,XX zł                    │
│  termin | rachunek | metoda                 │
├─────────────────────────────────────────────┤
│ FOOTER                                      │
│  uwagi / info dodatkowe / KSeF ref (opc.)  │
└─────────────────────────────────────────────┘
```

**CSS docelowe (0012):**
- `@page { size: A4; margin: 12–16mm; }`
- `@media print` — bez przycisku, light paper (zachować regresję)
- `thead { display: table-header-group; }`
- `tr, .party, .payment-box { break-inside: avoid; }` gdzie sensownie
- max-width ~210mm dla preview (responsive iframe)

**Logo/QR:** puste sloty CSS (`min-height`) bez logiki — future-ready, zero zależności.

---

## MULTIPAGE_STRATEGY

1. WeasyPrint + browser print na tym samym HTML z `@page A4`.
2. Tabela pozycji: natural flow; `thead` repeat.
3. Bloki parties / payment / summary: `break-inside: avoid` gdy mieszczą się na stronie.
4. Długie nazwy: wrap w komórce; bez `white-space: nowrap` na nazwie.
5. Nie budować ręcznego paginatora w JS.
6. Test regresji: HTML zawiera `@page` + `table-header-group`; opcjonalnie WeasyPrint smoke dla 50 pozycji (jeśli CI ma WeasyPrint).

---

## EDGE_CASES

| Case | Dziś | 0012 |
|------|------|------|
| 1 pozycja | OK | OK |
| 10 pozycji | OK | OK + A4 |
| 50+ | brak kontroli page-break | `@page` + thead repeat |
| długie nazwy | wrap naturalny | jawny wrap |
| wieloliniowy adres | 2 pola address/city | helper linii; puste pomijać |
| częściowy adres | puste `<p>` | nie renderować pustych linii; **nie** zmieniać KSeF AdresL1 |
| różne stawki VAT | tylko suma | dodać grupowanie po `vat_rate` (presentation) |
| zwolnione / 0% | Decimal 0 → `0%` | zachować; klucz grupy `"0"` / zw jeśli kiedyś string |
| grosze | ROUND_HALF_UP 0.01 | bez zmian kalkulacji — tylko display |
| duże kwoty | string Decimal | formatowanie z separatorem tysięcy (opcjonalnie PL) |
| multipage | słabe | strategy powyżej |

---

## OPTION_A — modernizacja istniejącego `render_invoice_html`

- **Zakres:** głównie `pdf_service.py` + `test_pdf_service.py`
- **Ryzyko:** niskie (jeden punkt renderu; FE bez zmian kontraktu)
- **Duplikacja:** brak
- **Testowalność:** wysoka (string HTML assertions)
- **Wpływ KSeF:** zero

## OPTION_B — osobny `InvoicePrintView` (React)

- **Zakres:** nowy FE layout + nadal backend PDF LUB FE-only print
- **Ryzyko:** wysokie rozjechanie preview vs PDF
- **Duplikacja:** dwa szablony
- **Testowalność:** FE + backend
- **Wpływ KSeF:** zero, ale koszt duży

## OPTION_C — multi-template engine

- **Zakres:** registry templates, wybór wariantu
- **Ryzyko:** overengineering
- **Duplikacja:** framework + 1 template
- **Testowalność:** średnia
- **Wpływ KSeF:** zero
- **Potrzeba teraz:** **NIE**

---

## RECOMMENDED_ARCHITECTURE

**OPTION_A** — modernizacja `app/services/pdf_service.py` (`render_invoice_html` + CSS), zachowanie `render_invoice_pdf` i endpointów.

## RATIONALE

1. Preview i PDF już dzielą jeden HTML — to właściwy punkt zmiany.
2. FE nie renderuje sheetu — Option B dodaje zbędną drugą prawdę.
3. Brak wariantów biznesowych dziś → Option C zbędna.
4. Minimalny diff, zero KSeF/DB, istniejące testy łatwo rozszerzyć.
5. ViewModel warstwa nie wnosi wartości przy jednym DTO wejściowym.

---

## EXPECTED_FILES_TO_CHANGE (GWO-0012)

| Plik | Zmiana |
|------|--------|
| `app/services/pdf_service.py` | markup modern A4, VAT-by-rate, Lp., payment dominant, `@page`, multipage CSS, opcjonalny helper adresu |
| `tests/unit/test_pdf_service.py` | regresje: light paper, bank, qty, VAT%, unit gross + nowe: Lp., `@page`, VAT summary, puste linie adresu, wiele stawek |

**Możliwe (niewymagane):**
- `tests/unit/test_invoice_api.py` — smoke preview HTML contains `FAKTURA` / `@page`
- drobny komentarz w docs runbook (opcjonalnie)

## FILES_THAT_MUST_NOT_CHANGE (0012)

- `app/integrations/ksef/**`
- `app/domain/party_address.py` (chyba że **tylko** reuse read-only w pdf — preferuj lokalny helper bez zmiany party_address)
- `app/domain/models/invoice.py` / ORM / alembic
- `invoice_totals.py`, `invoice_number_policy.py`
- `submit_invoice.py`, transmission
- prod-monitor / Guardian runtime
- mobile-expo invoice screens (poza scope)
- CSS React invoice list/form (nie sheet)

---

## RISKS

| Ryzyko | Mitigacja |
|--------|-----------|
| Regresja light-paper / dark mode | istniejący test `test_html_forces_light_paper…` musi PASS |
| Regresja bank sale vs purchase | istniejące 4 testy bank |
| WeasyPrint inaczej niż browser print | ten sam HTML; ręczny smoke 1-page + 50 items |
| Zmiana kolumn psuje asercje `>120.00<` | aktualizacja testów świadomie |
| Pokazanie statusu IFG na „oficjalnym” wydruku | w 0012: przenieść status do meta mniej prominentnej lub ukryć na print (decyzja UX) |
| VAT-by-rate vs zwolnienia | grupuj po Decimal rate z response; nie wprowadzaj nowych stawek |

---

## FUTURE OPTIONS (nie implementować w 0012)

| Feature | Jak później | Teraz |
|---------|-------------|-------|
| Logo firmy | slot w HEADER + settings blob/URL | pusty slot CSS |
| QR przelewu | generator w pdf_service (dane z kwoty+rachunek) | slot |
| Status ZAPŁACONO | już jest payment_status — styl dominant | opcjonalnie w PAYMENT |
| Numer / QR KSeF | już jest banner numeru | slot QR |
| Podpis/stopka | footer HTML | uwagi |
| Wiele wariantów template | Option C dopiero gdy biznes wymaga | NIE |

---

## IMPLEMENTATION PLAN — GWO-IFG-INVOICE-TEMPLATE-MODERN-0012

1. Worktree/branch od aktualnego `origin/production` (lub kontynuacja `gwo/ifg-invoice-template-0011` → rename/new branch `…-modern-0012`).
2. Przebudowa HTML/CSS w `render_invoice_html` wg MODERN_TEMPLATE_STRUCTURE.
3. Dodać `_vat_summary_rows(items|totals)` presentation-only.
4. Dodać Lp. (`enumerate(items, start=1)` lub `sort_order`).
5. `@page A4` + multipage CSS.
6. Payment block dominant (DO ZAPŁATY + termin + rachunek + metoda).
7. Pomiń puste linie adresu.
8. Rozszerz `test_pdf_service.py` (minimal regression set poniżej).
9. Ręczny smoke: preview iframe + PDF download + Ctrl+P.
10. PR → merge → verify → **worktree remove + prune** (nie zostawiać trwałej kopii).

### Minimal regression set przed/po

1. Light paper / `@media print` / `print-color-adjust`
2. Bank sale present / purchase company omitted / purchase snapshot bank
3. Quantity bez `.00`; VAT `5%` nie `5.00%`
4. Unit gross column value
5. **NOWE:** `@page` + `size: A4`
6. **NOWE:** Lp. `1` dla pierwszej pozycji
7. **NOWE:** VAT summary zawiera stawkę przy 2 różnych rate
8. **NOWE:** puste address nie tworzy pustego `<p></p>` (lub równoważne)
9. Endpoint PDF nadal `%PDF` (istniejący test)

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

*(Audyt/docs only — standard przyjęty; brak zmian aplikacji.)*

## Decyzje dla ChatGPT

1. Czy w modern A4 **ukrywać badge statusu IFG** (`ready_for_submission` itd.) na print/PDF (zostawić tylko w preview UI), czy pokazywać dyskretnie w META?
2. Czy kolumna **„Cena brutto”** jednostkowa zostaje (dziś jest), czy modern ma tylko cenę netto + sumy (zgodnie ze szkicem ITEMS w briefie)?
3. Czy footer „uwagi” w 0012 ma pokazywać `correction_reason` (gdy korekta), czy zostawić pusty slot do czasu osobnego pola notes?

## GENERATED REPORTS

- `/Volumes/WorkspaceSSD/projects/_worktrees/ifg-invoice-template-0011/docs/reports/2026-09-28_GWO-IFG-INVOICE-TEMPLATE-AUDIT-0011.md`
