---
kind: gwo
project: IFG
workflow: GWO-IFG-0027
handoff: true
created_at: 2026-07-20T19:15:00Z
---

# GWO-IFG-0027 — Buyer popup hover binding regression fix

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS  
**STATUS:** SUCCESS  

---

## Problem (produkcja po GWO-IFG-0026)

1. Hover na **nazwie nabywcy** — popup kontrahenta **nie** pojawiał się.
2. Hover na **numerze faktury** — natywny tooltip: `Źródło numeru: backend:number_local`.
3. Zachowanie sprzeczne z wymaganiem i raportem GWO-IFG-0026 (weryfikacja 0026 opierała się głównie na markerach w bundlu, nie na realnym hoverze).

---

## A. Root cause

Dwie niezależne przyczyny w `InvoiceCardList.jsx` / CSS:

1. **Techniczny tooltip na numerze (sale):** komórka numeru ustawiała  
   `title={\`Źródło numeru: ${item.numberSource}\`}`  
   (`numberSource` = m.in. `backend:number_local`). Stąd natywny tooltip przeglądarki na numerze.

2. **Popup nabywcy niewidoczny / nieskuteczny:** popup był pozycjonowany `absolute` **wewnątrz** komórki z `overflow: hidden` oraz obszaru scroll — CSS `:hover` + `opacity` nie dawały wiarygodnej widoczności; trigger był poprawnie w komórce nabywcy, ale warstwa wizualna była obcinana / nieskuteczna.

**Nie** było błędnego przypięcia triggera do numeru faktury — numer miał osobny `title`; popup był przy nabywcy, ale nieskuteczny w DOM/CSS.

### Fix

- Usunięto techniczny `title` z numeru sprzedaży (`title` tylko dla długiego numeru zakupu).
- `BuyerNameWithPopup`: `createPortal` → `document.body`, `position: fixed`, delay hide (anti-flicker), atrybuty `data-buyer-hover-trigger` / `data-buyer-popup`.
- CSS: `.buyerPopupFixed { position: fixed }`, usunięto zależność od `:hover` opacity wewnątrz komórki.

---

## B. Zmienione pliki

| Plik | Rola |
|------|------|
| `frontend-react/src/components/invoice/InvoiceCardList.jsx` | Portal popup + usunięcie title numberSource |
| `frontend-react/src/components/invoice/InvoiceCardList.module.css` | Fixed portal styles |
| `frontend-react/src/components/invoice/invoiceCardListBuyerPopup.test.js` | Regresja (numer / trigger / dane) |
| `frontend-react/src/components/dashboard/dashboardAggregation.test.js` | Asercje CSS/JSX pod portal |
| `frontend-react/buyer-popup-smoke.html` | Smoke entry |
| `frontend-react/src/smoke/buyerPopupMain.jsx` | Smoke mount |
| `frontend-react/scripts/verify-buyer-popup-hover.mjs` | Lokalny Playwright hover |
| `frontend-react/scripts/verify-buyer-popup-prod-remote.mjs` | Prod Playwright na DS723 (Docker host network) |
| `frontend-react/scripts/verify-buyer-popup-prod.mjs` | Próba SOCKS (SSH forward zablokowany na NAS) |

**Commity:** `a0f4f59` (fix), `c3bbfce` (skrypty verify).

---

## C. Deploy

| Krok | Wynik |
|------|-------|
| Push `origin/production` | PASS (`a0f4f59`) |
| `guardian ifg deploy run --yes --allow-dirty-build` | **LIVE COMPLETE** |
| Dist sync | `index-UQImflzm.js`, `index-CFZ4sRzG.css` |
| Compose up / usługi | PASS |
| Health `http://127.0.0.1:8000/health` | `status=ok`, `environment=production` |
| DS723+ `git rev-parse` | `a0f4f59` (kod fix); skrypty verify później `c3bbfce` |

Raport deploy: `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`

---

## D. Testy

| Test | Wynik |
|------|-------|
| `node --test` `invoiceCardListBuyerPopup.test.js` | PASS |
| `dashboardAggregation.test.js` (m.in. portal CSS) | PASS |
| `npm run build` | PASS |
| Dist: brak `Źródło numeru`; obecne `buyer-hover-trigger`, `createPortal`, `_buyerPopupFixed_*` | PASS |
| Lokalny Playwright smoke (`verify-buyer-popup-hover.mjs`) | **PASS** |
| Produkcja Playwright na DS723 Docker `--network host` (`verify-buyer-popup-prod-remote.mjs`) | **PASS** |

### Metoda rzeczywistej weryfikacji zachowania (produkcja)

**Nie** ograniczono się do grep klas w JS.

1. Na DS723 uruchomiono kontener `mcr.microsoft.com/playwright:v1.61.1-jammy` z `--network host`.
2. Logowanie API → `localStorage` auth → `http://127.0.0.1:8000/ui/invoices` (bundle `index-UQImflzm.js`).
3. Wybór miesiąca z danymi (gdy bieżący pusty).
4. **Hover numeru** — brak `title` z `Źródło numeru` / `number_local` / `backend:`; popup się nie otwiera.
5. **Hover nabywcy** (`[data-buyer-hover-trigger]`) — widoczny `[data-buyer-popup]` z tą samą nazwą (długość sprawdzona: 61).
6. Przejście kursora na popup — bez migotania; wyjście — zamknięcie.

Wynik: `BUYER_POPUP_PROD_VERIFY=PASS`.

Uwaga: SSH `LocalForward` / `DynamicForward` na DS723 są administracyjnie zablokowane — stąd weryfikacja **na hoście** przez Docker, nie przez tunel z Mac mini.

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [x] **PRODUCTION_VERIFIED**

Dowód: Playwright hover na uruchomionej aplikacji IFG (`127.0.0.1:8000/ui`) na DS723+, aktywny bundle `index-UQImflzm.js`.

---

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG-0027_BUYER_POPUP_HOVER_BINDING_REGRESSION_FIX.md`

## Wygenerowane artefakty

- Commit `a0f4f59` — fix UI
- Commit `c3bbfce` — skrypty weryfikacji
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md` (deploy LIVE COMPLETE)
- DS723+ dist: `frontend-react/dist/assets/index-UQImflzm.js`, `index-CFZ4sRzG.css`
- Playwright image na DS723: `mcr.microsoft.com/playwright:v1.61.1-jammy` (użyty do prod verify)
