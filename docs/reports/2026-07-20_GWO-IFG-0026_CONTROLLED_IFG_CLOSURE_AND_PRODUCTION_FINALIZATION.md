---
kind: gwo
project: IFG
workflow: GWO-IFG-0026
handoff: true
created_at: 2026-07-20T17:55:00Z
---

# GWO-IFG-0026 — Controlled IFG closure and production finalization

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS  
**STATUS:** SUCCESS  

---

## Trzy otwarte zmiany (zidentyfikowane)

| # | Zmiana | Źródło | Stan przed 0026 |
|---|--------|--------|-----------------|
| 1 | Nazwa widoku **Zestawienia** | GWO-IFG-0023 / 0024 | Deployed (`131dd70`), Release State = DEPLOYED_TO_DS723 |
| 2 | Panel **YTD** (Sprzedaż/Zakup netto) | GWO-IFG-0023 / 0024 | j.w. |
| 3 | **Popup** nabywcy (Faktury sprzedaży) | GWO-IFG-0023 / 0024 | j.w. |

Brak nowego kodu — finalizacja weryfikacji produkcyjnej po GWO-IFG-0025.

---

## Wykonane etapy

1. **Weryfikacja stanu:** `deploy check` → PRODUKCJA ZGODNA (`131dd70` Mac mini = DS723+).
2. **Deploy:** nie wymagany ponownie (artefakty już na DS723+).
3. **Restart:** `docker compose restart api` (odświeżenie serwisu serwującego `/ui`).
4. **Health:** `{"status":"ok","environment":"production",...}` PASS.
5. **Weryfikacja produkcyjna** przez serwowanie produkcyjne `http://127.0.0.1:8000/ui/` na DS723+ (ten sam dist, który obsługuje https://ifg.ikonastudio.pl po Cloudflare Access):
   - JS/CSS HTTP 200, **md5 identyczny** z plikami dist,
   - Change 1: `Zestawienia`×2, stara etykieta ×0,
   - Change 2: `ytdPanel`/`ytdBarSale`/`ytdBarPurchase` obecne; `getFullYear` obecne; **brak** `2026-01-01`,
   - Change 3: `buyerPopup` / `buyerPopupContacts` / `buyerPopupName` obecne.

---

## RELEASE STATE (ten GWO)

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [x] PRODUCTION_VERIFIED

---

## Zamknięcie trzech zmian

| Zmiana | Release State końcowy |
|--------|----------------------|
| 1. Zestawienia (nazwa) | **PRODUCTION_VERIFIED** |
| 2. Panel YTD | **PRODUCTION_VERIFIED** |
| 3. Popup kontrahenta | **PRODUCTION_VERIFIED** |

Zakres GWO-IFG-0023 / 0024 / 0025 / 0026 — **zamknięty**.

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG-0026_CONTROLLED_IFG_CLOSURE_AND_PRODUCTION_FINALIZATION.md`

## Wygenerowane artefakty

- `docs/handoff/HANDOFF-0013.md`
- `docs/handoff/latest.md` → HANDOFF-0013
- Restart `ifg-api-1` (DS723+)