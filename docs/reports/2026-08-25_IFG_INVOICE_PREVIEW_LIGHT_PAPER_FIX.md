# 2026-08-25 — Naprawa czytelności podglądu faktury (ciemny motyw)

**Projekt:** IFG
**Zakres:** podgląd HTML / druk / PDF faktury
**Deploy:** nie wykonano

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

**Lokalny podgląd:** po restarcie API otwórz dowolną fakturę (podgląd w nowej karcie / SimpleView iframe) przy ciemnym motywie systemu — kartka ma być biała, tekst ciemny.

### Checklista review

- [ ] Numer i metadane faktury czytelne
- [ ] Sprzedawca i nabywca czytelni
- [ ] Komórki tabeli pozycji czytelne
- [ ] Podsumowanie netto/VAT/brutto czytelne
- [ ] Sekcja Płatność nadal czytelna
- [ ] Drukuj / Zapisz jako PDF — biała kartka
- [ ] Reszta UI IFG bez zmian wyglądu

---

## A. Root cause

Szablon HTML faktury (`app/services/pdf_service.py` → `render_invoice_html`) ustawiał `body { color: #111 }` **bez** `background` i bez `color-scheme: light`.

Przy aktywnym ciemnym `color-scheme` przeglądarki / OS (oraz w iframe pod ciemnym UI IFG) canvas stawał się czarny, a tekst pozostawał czarny → niewidoczny.

Sekcja „Płatność” miała już jawne `background: #fafafa`, stąd była czytelna.

PDF (WeasyPrint) zwykle nie stosuje OS dark mode, więc usterka dotyczyła głównie **podglądu ekranowego** i druku z przeglądarki — ten sam szablon jest źródłem dla PDF.

---

## B. Zmienione pliki

1. `app/services/pdf_service.py` — wymuszenie jasnej kartki:
   - `html { color-scheme: light; background: #ffffff }`
   - `body { color: #111111; background: #ffffff }`
   - jawne kolory tekstu dla `h1`, `.party p`, `th/td`, `.totals`
   - `@media print` z `background/color !important` + `print-color-adjust: exact`
2. `tests/unit/test_pdf_service.py` — test regresyjny `test_html_forces_light_paper_against_dark_color_scheme`

**Nie zmieniono:** `theme.css`, globalnego motywu, list/formularzy faktur.

---

## C. Deploy

Nie wykonano. Wymagana osobna zgoda.

---

## D. Testy

```text
python3 -m pytest tests/unit/test_pdf_service.py -q
10 passed in 0.03s
```

Testy frontendu invoice (`invoiceOpenMode`, `invoiceCardListBuyerPopup`, `invoiceCardListNumbering`) nie obejmują szablonu podglądu HTML — źródłem prawdy jest backend `pdf_service.py` (wspólny dla preview i PDF).

---

## E. Następny krok

1. Lokalny review podglądu faktury (checklista powyżej).
2. Po PASS → Deploy GWO na DS723 (osobna zgoda).
3. Po deploy: PRODUCTION_VERIFIED na prawdziwym podglądzie.

---

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-25_IFG_INVOICE_PREVIEW_LIGHT_PAPER_FIX.md
