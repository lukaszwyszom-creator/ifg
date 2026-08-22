---
kind: gwo
project: IFG
workflow: GWO-IFG-0023
handoff: true
created_at: 2026-07-20T14:45:00Z
---

# GWO-IFG-0023 — Zestawienia UX Improvements

**Data:** 2026-07-20  
**Repo:** `/Users/lukasz/projekty/ifg_standalone`  
**STATUS:** SUCCESS  
**VERDICT:** READY  

---

## STATUS

| Gate | Wynik |
|------|-------|
| Rename UI → „Zestawienia” | PASS |
| Panel YTD (paski Sprzedaż/Zakup, netto, rok dynamiczny) | PASS |
| Popup nabywcy (nazwa + kontakt bez NIP/adresu) | PASS (kontakt: brak pól w modelu — tylko nazwa) |
| Brak zmian API / modeli / logiki biznesowej | PASS |
| Testy objęte GWO | PASS (nowe + zaktualizowane) |
| `npm run build` (frontend-react) | PASS |
| Pre-existing testy `InvoiceList` (string assertions) | FAIL (poza zakresem — 2) |

**VERDICT:** Zmiany UX wdrożone w warstwie prezentacji; frontend buduje się poprawnie.

---

## VERDICT

**READY** — trzy zmiany UX działają bez naruszenia API/modeli.

---

## Wykonane zmiany

### 1. Nazwa widoku „Zestawienia”

- Sidebar: `Sprzedaż / Zakup` → `Zestawienia`
- Topbar: `Zestawienia: sprzedaż / zakup` → `Zestawienia`
- Bez zmiany tras, endpointów ani nazw komponentów

### 2. Wykres syntetyczny YTD (prawy panel)

- Istniejący wykres liniowy/area **bez zmian**
- Po prawej: panel z dwoma pionowymi paskami (Sprzedaż = `#d4a017`, Zakup = `#3b82f6`)
- Źródło: suma `total_net` PLN (bez rejected), zakres `currentYearToDateRange()` = **1 stycznia aktualnego roku systemowego → dziś**
- Wspólna skala (`buildYtdBarHeights`), etykiety + kwoty netto pod paskami
- Osobne ładowanie puli faktur YTD (istniejący `loadInvoicePool` / list API) — bez nowego endpointu
- Responsywność: poniżej 900px panel pod wykresem

### 3. Popup nabywcy (Faktury sprzedaży)

- Hover na nazwę nabywcy → popup z pełną nazwą
- Kontakt: `extractBuyerContactLines` czyta wyłącznie pola typu phone/email z `buyer_snapshot`
- **Nie** pokazuje NIP, adresu ani innych pól firmowych
- Brak kontaktu → tylko nazwa

**Ograniczenie (świadome, bez zmiany API):** model kontrahenta / snapshot faktury **nie zawiera** telefonu ani e-maila (`Contractor` ma nip/name/source; `_SNAPSHOT_FIELDS` bez kontaktu). Popup jest gotowy na pola kontaktowe, gdy pojawią się w snapshotcie; dziś w praktyce widać wyłącznie nazwę.

---

## Zmienione pliki

| Plik | Rola |
|------|------|
| `frontend-react/src/components/layout/Sidebar.jsx` | etykieta menu |
| `frontend-react/src/components/layout/Topbar.jsx` | tytuł strony |
| `frontend-react/src/components/dashboard/DashboardSummary.jsx` | panel YTD |
| `frontend-react/src/components/dashboard/DashboardSummary.module.css` | layout + style pasków |
| `frontend-react/src/components/dashboard/dashboardQuery.js` | `currentYearToDateRange` |
| `frontend-react/src/components/dashboard/dashboardAggregation.js` | `buildYtdBarHeights` |
| `frontend-react/src/components/dashboard/dashboardAggregation.test.js` | testy GWO-0023 + aktualizacja rename |
| `frontend-react/src/components/invoice/InvoiceCardList.jsx` | popup nabywcy |
| `frontend-react/src/components/invoice/InvoiceCardList.module.css` | style popup |
| `frontend-react/src/components/invoice/buyerContact.js` | ekstrakcja kontaktu |
| `docs/reports/2026-07-20_GWO-IFG-0023_ZESTAWIENIA_UX_IMPROVEMENTS.md` | ten raport |

---

## Wynik testów

```text
node --test frontend-react/src/components/dashboard/dashboardAggregation.test.js
ℹ tests 38
ℹ pass 36
ℹ fail 2
```

**Fail (pre-existing, poza GWO-0023):**

- `InvoiceList: ignoruje stare odpowiedzi requestów` — asercje na `requestSeqRef` nieobecne w obecnym `InvoiceList.jsx`
- `InvoiceList: przy filters.month odfiltrowuje…` — asercje na stare wzorce filtracji

**Nowe / objęte GWO — PASS:** rename Sidebar/Topbar, `currentYearToDateRange`, `buildYtdBarHeights`, panel YTD, CSS kolorów, `extractBuyerContactLines`, popup nabywcy.

---

## Wynik buildu

```text
cd frontend-react && npm run build
✓ 967 modules transformed
✓ built in 1.34s
dist/assets/index-*.js ~904 kB (gzip ~267 kB)
```

Ostrzezenie Vite o rozmiarze chunka (>500 kB) — znane, poza zakresem.

---

## Ewentualne problemy

1. Brak danych kontaktowych w bazie/API → popup nabywcy pokazuje wyłącznie nazwę (zgodne ze specyfikacją fallback).
2. Panel YTD ładuje osobną pulę faktur od 1 stycznia (dodatkowe requesty list) — cache `invoicePool` ogranicza powtórzenia; filtr okresu wykresu liniowego pozostaje niezależny.
3. Dwa pre-existing failujące testy stringowe `InvoiceList` — nie naprawiane w tym GWO.

---

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG-0023_ZESTAWIENIA_UX_IMPROVEMENTS.md`

## Wygenerowane artefakty

- `docs/handoff/HANDOFF-0006.md`
- `docs/handoff/latest.md` → HANDOFF-0006
- `docs/handoff/index.json` (`latest_handoff_id: 6`)
- `frontend-react/dist/` (build produkcyjny)

### Handoff

| Pole | Wartość |
|------|---------|
| Przygotowany? | **TAK** |
| HANDOFF ID | HANDOFF-0006 |
| source_reports | `docs/reports/2026-07-20_GWO-IFG-0023_ZESTAWIENIA_UX_IMPROVEMENTS.md` |
| workflow | GWO-IFG-0023 |
| status | SUCCESS |