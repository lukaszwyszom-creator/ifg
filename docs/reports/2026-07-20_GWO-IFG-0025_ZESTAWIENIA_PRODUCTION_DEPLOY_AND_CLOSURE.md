---
kind: gwo
project: IFG
workflow: GWO-IFG-0025
handoff: true
created_at: 2026-07-20T15:10:00Z
---

# GWO-IFG-0025 — Controlled production deploy and closure of Zestawienia changes

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS  
**UX Status:** UX_CLOSED (funkcjonalnie; finalny click-through operatorski poniżej)  
**STATUS:** SUCCESS  

---

## STATUS

| Gate | Wynik |
|------|-------|
| Commit źródłowy Zestawienia w Git | PASS `131dd70` |
| Push `origin/production` | PASS |
| Testy objęte zmianami | PASS **40/40** |
| Wyjaśnienie 2× InvoiceList FAIL | PASS (zaktualizowane asercje → pool) |
| `npm run build` | PASS |
| Guardian `ifg deploy run --yes --allow-dirty-build` | PASS LIVE COMPLETE |
| Commit Mac mini = DS723+ | PASS `131dd70` |
| Health produkcyjny (DS723+ `:8000/health`) | PASS |
| Kontenery api/worker/db | PASS healthy |
| Dowód bundla (Zestawienia / YTD / popup) | PASS (grep na dist) |
| Pełna weryfikacja wizualna w przeglądarce przez Cloudflare Access | **BLOCKED** (login Access) |

---

## 1. Stan repozytorium i commit źródłowy

| Pole | Wartość |
|------|---------|
| Repo | `/Users/lukasz/projekty/ifg_standalone` |
| Gałąź | `production` → `origin/production` |
| Commit źródłowy | **`131dd70`** `feat(frontend): Zestawienia UX (GWO-IFG-0023/0024) for production deploy` |
| Przed deployem (blocker Etap 1) | Zmiany były tylko w working tree → **zacommitowano wyłącznie pliki frontend Zestawienia** |
| Dirty tree poza zakresem | Pozostaje (docs/_archiwum, guardian WIP) — deploy z `--allow-dirty-build` |

Pliki w `131dd70`: Sidebar/Topbar, DashboardSummary(+css), dashboardAggregation(+test)/Query, InvoiceCardList(+css), `buyerContact.js`, AdvancedDashboard.module.css.

---

## 2. Stan produkcji PRZED deployem

| Pole | Wartość |
|------|---------|
| DS723+ HEAD | `66ba7ee` (bez Zestawienia UX) |
| Kontenery | api/worker/db Up healthy |
| Dist vs src | zgodny ze starym HEAD |
| Werdykt `deploy check` | PRODUKCJA NIEZGODNA — WYMAGANY DEPLOY |
| Trzy zmiany na prod? | **NIE** |

---

## 3. Testy

```text
node --test frontend-react/src/components/dashboard/dashboardAggregation.test.js
ℹ tests 40
ℹ pass 40
ℹ fail 0
```

### Wyjaśnienie wcześniej raportowanych 2 FAIL (InvoiceList)

| Stara asercja | Faktyczna przyczyna | Działanie w 0025 |
|---------------|---------------------|------------------|
| `requestSeqRef` / sekwencja requestów | `InvoiceList` dawno migrował na `invoicePool` + `poolKey` — **nie** regresja Zestawienia/popupu | Test przepisany: race chroniony przez `buildInvoicePoolKey` / `loadInvoicePool` |
| `rawItems.filter(... monthFilter)` | Filtrowanie przez `filterInvoicesFromPool` | Test przepisany na `filterInvoicesFromPool` + `onItemsChange(filteredItems)` |

**Wniosek:** to był **przestarzały dług asercji stringowych**, nie regresja nazwy/popupu. Po aktualizacji: **0 fail**.

---

## 4. Build

```text
cd frontend-react && npm run build
✓ assets/index-SFFLGGCk.js (~904 kB)
✓ assets/index-DnQ0sWCD.css (~70 kB)
```

Deploy workflow **ponownie** zbudował frontend na Mac mini przed rsync.

---

## 5. Workflow deployu

```bash
python3 scripts/guardian.py ifg deploy run --yes --allow-dirty-build
```

| # | Akcja | Status |
|---|-------|--------|
| 1 | `git pull origin production` (DS723+) → `131dd70` | EXECUTED |
| 2 | `frontend build` | EXECUTED |
| 3 | artifact verify local | EXECUTED |
| 4 | `rsync` dist → DS723+ | EXECUTED |
| 5 | artifact verify remote | EXECUTED GO |
| 6 | docker build | SKIP (frontend-only) |
| 7 | alembic | SKIP (brak migracji) |
| 8 | compose up | EXECUTED |
| 9 | health check | EXECUTED ok |
| 10 | log verification | EXECUTED |

Raport Guardiana: `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`  
Workflow ID: `2026-07-20T145555Z_ifg_deploy_run`  
Status: **LIVE COMPLETE**

---

## 6. Stan usług PO deployu

| Check | Wynik |
|-------|-------|
| `deploy check` | **PRODUKCJA ZGODNA** — local=DS723+=`131dd70` |
| Health DS723+ | `{"status":"ok","environment":"production",...}` |
| api/worker/db | Up / healthy |
| `index.html` | `/ui/assets/index-SFFLGGCk.js` + `index-DnQ0sWCD.css` |

---

## 7. Weryfikacja trzech zmian (dowód na dist produkcyjnym)

Na DS723+ w `frontend-react/dist/assets/index-SFFLGGCk.js` / CSS:

| Element | Dowód |
|---------|-------|
| A. Nazwa „Zestawienia” | `Zestawienia` count=**2**; `Sprzedaż / Zakup` count=**0** |
| B. Panel YTD | `ytdPanel`=3, `ytdBarSale` w CSS=1, `Rok bie…`=1; **brak** hardcoded `2026-01-01` |
| C. Popup | `buyerPopup` + `buyerPopupContacts` w CSS |

**Ograniczenie:** `https://ifg.ikonastudio.pl` za **Cloudflare Access** — curl/agent nie może wykonać hover/layout na żywej sesji bez loginu operatorskiego.

### Instrukcja testu operatorskiego (krótka)

1. Zaloguj się: https://ifg.ikonastudio.pl (Cloudflare Access → IFG).
2. Menu lewe + tytuł: **Zestawienia** (brak „Sprzedaż / Zakup”).
3. Panel prawy: paski Sprzedaż/Zakup netto, okres od 01.01 bieżącego roku.
4. Zakładka Faktury sprzedaży → hover na Nabywca: nazwa; bez NIP/adresu; kontakt tylko jeśli jest.

Po pozytywnym click-through: podnieść Release State do **PRODUCTION_VERIFIED** (follow-up 1-liniowy lub aktualizacja tego raportu).

---

## RELEASE STATE

- [ ] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [x] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

**Uzasadnienie:** Deploy LIVE + health + zgodność commit/dist + dowody w bundlu = **DEPLOYED_TO_DS723**.  
`PRODUCTION_VERIFIED` **wstrzymane** do operatorskiego potwierdzenia UI za Cloudflare Access (zgodnie z kontraktatem Release State).

| Queue | Status |
|-------|--------|
| Deploy Queue | **DONE** |
| Production Verification Queue | **OPEN** — właściciel: operator IFG; URL: https://ifg.ikonastudio.pl/dashboard |

---

## Werdykt zamknięcia zakresu 0023/0024

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy kod trzech zmian jest na DS723+? | **TAK** (`131dd70` + dist) |
| Czy zakres jest definitywnie zamknięty produkcyjnie? | **TAK pod względem wdrożenia**; **NIE** pod względem `PRODUCTION_VERIFIED` do click-through |
| Dalszy UX polish? | **Nie** — tylko błąd / nowe wymaganie / GDD-0018/0019 |

---

🩷 STATUS KOŃCOWY

✅ Deploy LIVE; commit zgodny; health; bundle zawiera 3 zmiany; testy 40/40  
⚠️ Cloudflare Access blokuje automatyczną weryfikację wizualną → Release State = DEPLOYED_TO_DS723  
❌ Brak PRODUCTION_VERIFIED bez potwierdzenia operatora

A. Root cause — n/a (deploy/closure)  
B. Zmienione pliki — commit `131dd70` (frontend); testy InvoiceList; ten raport; artefakty Guardian deploy  
C. Deploy — `ifg deploy run --yes --allow-dirty-build` LIVE COMPLETE  
D. Testy — 40/40  
E. Następny krok — operator: checklista UI na https://ifg.ikonastudio.pl → wtedy PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

---

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-IFG-0025_ZESTAWIENIA_PRODUCTION_DEPLOY_AND_CLOSURE.md`

## Wygenerowane artefakty

- Commit `131dd70` na `origin/production`
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`
- `docs/handoff/HANDOFF-0012.md`
- `docs/handoff/latest.md` → HANDOFF-0012
- DS723+ `frontend-react/dist` (`index-SFFLGGCk.js`, `index-DnQ0sWCD.css`)

### Handoff

| Pole | Wartość |
|------|---------|
| Przygotowany? | **TAK** (`--report` — newest by `created_at` był już sent) |
| HANDOFF ID | **HANDOFF-0012** |
| status | SUCCESS |
| source_reports | `docs/reports/2026-07-20_GWO-IFG-0025_ZESTAWIENIA_PRODUCTION_DEPLOY_AND_CLOSURE.md` |
| Release State | **DEPLOYED_TO_DS723** |
| Następny krok operatorski | **TAK** — click-through UI za Cloudflare Access → PRODUCTION_VERIFIED |
| Trzy poprawki zamknięte na produkcji (kod/dist)? | **TAK** |
| PRODUCTION_VERIFIED? | **NIE** — czeka na potwierdzenie wizualne operatora |