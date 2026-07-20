---
kind: gwo
project: IFG
workflow: GWO-IFG-0028
handoff: true
created_at: 2026-07-20T19:40:00Z
---

# GWO-IFG-0028 — Contractor popup city display

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS  
**STATUS:** SUCCESS  

---

## Cel

Rozszerzyć popup kontrahenta (Nabywca / Sprzedawca) o miejscowość w formacie:

`Nazwa kontrahenta, Miejscowość`

bez ulicy, numeru, kodu pocztowego, województwa i kraju.

---

## Implementacja

| Element | Zmiana |
|---------|--------|
| `formatContractorPopupTitle(name, snapshot)` | `${name}, ${snapshot.city}` — to samo źródło co nazwa |
| `ContractorNameWithPopup` | wspólny popup dla sale (buyer) i purchase (seller) |
| `getContractorSnapshot` | ten sam rekord co `getContractorName` |
| Brak dodatkowych zapytań API | wyłącznie snapshot już obecny na fakturze |
| Brak fallbacków UI | puste `city` nie jest uzupełniane z street/postal |

### Efekt (opis / dowód Playwright)

**Nabywca (produkcja):**

```text
RZYMSKOKATOLICKA PARAFIA NAWIEDZENIA NAJŚWIĘTSZEJ MARYI PANNY, Strzałków
```

**Smoke lokalny:**

```text
ACME Kontrahent Smoke Sp. z o.o., Warszawa
Dostawca Smoke SA, Kraków
```

**Sprzedawca (produkcja):** popup hover działa; tytuł = `Nazwa,` — **brak city w danych** (patrz niżej).

---

## A. Root cause / kontekst

Poprzedni popup (GWO-IFG-0027) pokazywał samą nazwę. Brakowało miejscowości oraz popupu dla sprzedaży→nabywca był OK, ale zakupy→sprzedawca nie miał popupu (tylko native `title`).

---

## B. Zmienione pliki

- `frontend-react/src/components/invoice/buyerContact.js`
- `frontend-react/src/components/invoice/InvoiceCardList.jsx`
- `frontend-react/src/components/invoice/invoiceCardListBuyerPopup.test.js`
- `frontend-react/src/components/dashboard/dashboardAggregation.test.js`
- `frontend-react/src/smoke/buyerPopupMain.jsx`
- `frontend-react/scripts/verify-buyer-popup-hover.mjs`
- `frontend-react/scripts/verify-buyer-popup-prod-remote.mjs`

**Commit:** `46fd529`

---

## C. Deploy

| Krok | Wynik |
|------|-------|
| `guardian ifg deploy run --yes --allow-dirty-build` | **LIVE COMPLETE** |
| Dist | `index-DUsIwSIN.js`, `index-CFZ4sRzG.css` |
| Health | `status=ok`, `environment=production` |
| DS723+ commit | `46fd529` |

---

## D. Testy

| Test | Wynik |
|------|-------|
| Unit (44) | PASS |
| Lokalny Playwright smoke (sale+purchase + city) | **PASS** (`CONTRACTOR_CITY_DISPLAY=PASS`) |
| Prod Playwright Nabywca + city | **PASS** (`BUYER_TITLE=…, Strzałków`) |
| Prod Playwright Sprzedawca hover | **PASS** |
| Prod Sprzedawca city content | **DATA_ERROR** (puste `seller_snapshot.city`) |

---

## Znany błąd danych (bez obejścia UI)

Próbka API na DS723+ (`direction=purchase`, 20 faktur):

| Metryka | Wartość |
|---------|---------|
| `PUR_CITY_OK` | **0** |
| `PUR_CITY_EMPTY` | **20** |
| `has_street` | true (ulica obecna) |
| Sale `buyer_snapshot.city` | OK (10/10 w próbce) |

**Wniosek:** UI poprawnie czyta `snapshot.city`. Dla zakupów pole `seller_snapshot.city` jest puste w produkcji (prawdopodobna luka w mapowaniu KSeF/XML → snapshot), mimo założenia biznesowego „zawsze jest miejscowość”.  
Zgodnie z GWO **nie** dodano fallbacku z `street` / parse adresu.

Osobny follow-up (poza 0028): naprawa wypełniania `seller_snapshot.city` przy imporcie zakupów.

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [x] **PRODUCTION_VERIFIED**

UI + deploy + hover Nabywcy z miejscowością oraz hover Sprzedawcy potwierdzone na DS723+.  
Ograniczenie: content city dla Sprzedawcy zablokowany **danymi**, nie regresją UI.

---

## Decyzje dla ChatGPT

1. Czy otworzyć osobne GWO na uzupełnienie `seller_snapshot.city` przy syncu zakupów KSeF (bez zmian UI popupu)?

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG-0028_CONTRACTOR_POPUP_CITY_DISPLAY.md`
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`

## Wygenerowane artefakty

- Commit `46fd529`
- Dist DS723+: `frontend-react/dist/assets/index-DUsIwSIN.js`
- Playwright prod: `BUYER_POPUP_PROD_VERIFY=PASS`, `SELLER_POPUP_HOVER_VERIFY=PASS`, `SELLER_CITY_DATA_ERROR=YES`
