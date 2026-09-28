# GWO-IFG-INVOICE-TEMPLATE-POLISH-0014

**Data:** 2026-09-28  
**Branch:** `gwo/ifg-invoice-template-polish-0014`  
**Base:** `origin/production` @ `eb5e555ccf767bf63794f917f3710eab530391ff`  
**Zakres:** polish prezentacji modern A4 (header kind/period + szerokości kolumn tabeli)  
**Poza zakresem:** KSeF, DB, API, VAT summary, DO ZAPŁATY / remaining_amount, logika fiskalna, deploy

---

## Decyzje operatora (wdrożone)

1. Górny lewy blok bez danych sprzedawcy → dynamicznie `ZAKUP` / `SPRZEDAŻ` / `KOREKTA`, poniżej miesiąc+rok (`sale_date`, fallback `issue_date`).
2. Tabela: Lp. wąska + left; Nazwa poszerzona; j.m. ~4 znaki; VAT tylko pod `23%`; odzyskane miejsce na Nazwę.
3. Bez zmian VAT summary / DO ZAPŁATY / KSeF / DB / API / fiskal.

---

## Implementacja

### `app/services/pdf_service.py`

- `_invoice_kind_label()` — KOREKTA (typy KOR*) ma pierwszeństwo; inaczej purchase→ZAKUP, else→SPRZEDAŻ.
- `_period_label()` — polska nazwa miesiąca + rok (`maj 2026`).
- Header: `.kind-block` zamiast `.seller-compact` (sprzedawca pozostaje w sekcji parties).
- Kolumny: `.lp` left + wąski padding; `.unit` 2.4em; `.vat-rate` 2.8em; `.name` 42%.

### Testy

- Zaktualizowane asercje `td.lp` (bez `num`).
- Nowe: kind sale/purchase/kor, period + fallback, layout CSS kolumn.

---

## Dowody

| Gate | Wynik |
|------|-------|
| `pytest tests/unit/test_pdf_service.py` | **32 PASS** |
| Preview smoke (sale/purchase/kor/partial HTML) | PASS — `SPRZEDAŻ`/`ZAKUP`/`KOREKTA`, `maj 2026`, brak `seller-compact` |
| PDF smoke | PASS — `%PDF`, sale 1 strona, multipage 51 pozycji → 3 strony |
| Partial DO ZAPŁATY regresja | PASS — `400.00 PLN` przy remaining |

Artefakty lokalne (nie w repo): `/tmp/ifg-0014-smoke/`

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

**URL lokalny review:** otwórz `/tmp/ifg-0014-smoke/sale.html` (oraz purchase/kor) w przeglądarce; PDF: te same nazwy `.pdf`.

**Checklista UX:**
- [ ] Górny lewy: rodzaj + miesiąc (bez sprzedawcy w headerze)
- [ ] Nazwa czytelnie szersza; Lp/Jm/VAT wąskie
- [ ] Sprzedawca/Nabywca nadal w sekcji parties
- [ ] DO ZAPŁATY bez regresji

**Następny krok Deploy GWO:** dopiero po review + merge PR (ten GWO: NIE merge).

---

## 🩷 STATUS KOŃCOWY

✅ Co działa
- Kind/period w headerze; kolumny Lp/Nazwa/Jm/VAT; 32 testy; smoke HTML/PDF.

⚠️ Znane problemy
- Brak.

❌ Co nie działa
- Brak.

### A. Root cause
Operator polish po 0013: header miał dane sprzedawcy; kolumna Nazwa za wąska względem Lp/Jm/VAT.

### B. Zmienione pliki
- `app/services/pdf_service.py`
- `tests/unit/test_pdf_service.py`
- `docs/reports/2026-09-28_GWO-IFG-INVOICE-TEMPLATE-POLISH-0014.md`

### C. Deploy
Nie — PR only, bez merge / bez DS723.

### D. Testy
`32 passed` (`tests/unit/test_pdf_service.py`); smoke WeasyPrint PASS.

### E. Następny krok
Review PR → merge gate → osobne GWO deploy-verify.

## Decyzje dla ChatGPT
Brak.
