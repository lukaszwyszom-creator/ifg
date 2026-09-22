# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0004-FEATURE-COMMIT

Data: 2026-09-22
Cel: czysty feature commit KSeF (partial REGON / buyer address) — **bez push / bez deploy**.

## ETAP 1 — HEAD / EOL BASELINE (przed feature commit)

```text
PREVIOUS_HEAD = c87452fbf7f8f6a2a6b4d124d81fd41ea0345358
c87452f chore(ifg): normalize invoice form CSS to LF
```

Odblokowanie CSS EOL (blocker z wcześniejszego STOP 0004): osobny chore `c87452f` znormalizował `InvoiceForm.module.css` HEAD CRLF→LF.
Wcześniejszy chore `e686bac` znormalizował pair `contractor_service.py` / `contractors.js`.

EOL_BASELINE_OK: **YES**

## ETAP 2 — FEATURE DIFF (contractor + CSS)

| Plik | cached `--stat` |
|---|---|
| `contractor_service.py` | +3/−1 (bez masowego EOL) |
| `contractors.js` | +3 (bez masowego EOL) |
| `InvoiceForm.module.css` | +49 (tylko reguły adresu, LF) |

`git diff --cached --check` → exit 0.
FEATURE_EOL_NOISE: **NO**

## ETAP 3 — SCOPE (whitelist w feature commit)

16 ścieżek (dokładnie whitelist):

- `app/domain/party_address.py` (new)
- `app/domain/models/invoice.py`
- `app/integrations/ksef/mapper.py`
- `app/services/contractor_service.py`
- `frontend-react/src/api/contractors.js`
- `frontend-react/src/components/invoice/partyAddress.js` (new)
- `frontend-react/src/components/invoice/partyAddress.test.js` (new)
- `frontend-react/src/components/invoice/InvoiceForm.jsx`
- `frontend-react/src/components/invoice/InvoiceForm.module.css`
- `frontend-react/src/components/invoice/InvoiceActions.jsx`
- `frontend-react/src/components/invoice/InvoiceCardList.jsx`
- `tests/unit/test_ksef_partial_regon_address.py` (new)
- reports KSeF 0001, 0002, 0003, 0004

Wykluczone (pozostają w WT): `package.json`, Cursor/npm, EOL reports, Guardian, numbering WIP, `docs/gwo`, inne docs.

DIFF_SCOPE_OK: **YES**

## ETAP 4 — TESTY (z GWO / lokalny review)

| Suite | Wynik |
|---|---|
| `test_ksef_partial_regon_address.py` | 16 PASS |
| `test_contractor_service.py` | 6 PASS |
| `test_ksef_mapper.py` | 91 PASS |
| `test_domain_invoice` number_local | 1 FAIL **PREEXISTING** |
| `partyAddress.test.js` | 5 PASS |
| invoice suite (bez numbering WIP) | 8 PASS |

Feature GWO: **PASS**.

## ETAP 5 — COMMIT (wykonany)

```text
23c72b2 fix(ksef): support partial REGON buyer addresses
16 files changed, 1464 insertions(+), 61 deletions(-)
PARENT = c87452fbf7f8f6a2a6b4d124d81fd41ea0345358
```

Push / deploy: **NIE** w tym GWO.

## STATUS

```
STATUS: FEATURE_COMMIT_READY_FOR_PUSH
PREVIOUS_HEAD: c87452fbf7f8f6a2a6b4d124d81fd41ea0345358
FEATURE_COMMIT_SHA: 23c72b2af99e30870dd7793b92050366102633df
EOL_BASELINE_OK: YES
FEATURE_EOL_NOISE: NO
DIFF_SCOPE_OK: YES
BACKEND_TESTS: GWO PASS; number_local PREEXISTING FAIL
FRONTEND_TESTS: PASS
FILES_IN_COMMIT: 16 whitelist paths (code + reports 0001–0004)
UNRELATED_WIP_PRESERVED: YES
READY_FOR_PUSH: YES (commit lokalny; push poza zakresem)
VERDICT: FEATURE_COMMIT_READY_FOR_PUSH
```

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

- `/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0004-FEATURE-COMMIT.md`
