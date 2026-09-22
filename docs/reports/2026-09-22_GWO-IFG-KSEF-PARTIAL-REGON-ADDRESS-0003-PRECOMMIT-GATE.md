# GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0003-PRECOMMIT-GATE

Data: 2026-09-22
Cel: czysty commit KSeF-only — **bez commit**.

## 1. BASELINE FAIL — number_local

Potwierdzenie na czystym HEAD (tymczasowy worktree `/tmp/ifg_standalone_precommit_gate_*`, usunięty po teście):

```text
test_sale_requires_number_local_before_send
Expected regex: 'number_local'
Actual: 'Faktura sprzedaży nie ma numeru lokalnego. ...'
→ FAIL na HEAD 42b77fa
```

Diff GWO w `invoice.py` dotyczy wyłącznie `_has_minimum_address` → `can_build_adres_l1` — **nie** ścieżki `number_local`.

### BASELINE_NUMBER_LOCAL_FAIL

`PREEXISTING`

Gate #1: **PASS** (nie STOP).

---

## 2. EOL NOISE — STOP

### Fakty (2026-09-22, po oczyszczeniu CSS)

| Plik | HEAD | WT | Raw `--stat` | `--ignore-cr-at-eol` | Atrybuty |
|---|---|---|---|---|---|
| `app/services/contractor_service.py` | CRLF (288) | CRLF (289) | **577** | **3** | `text` + `eol=lf` |
| `frontend-react/src/api/contractors.js` | CRLF (12) | CRLF (15) | **27** | **3** | `text` + `eol=lf` |
| `InvoiceForm.module.css` | CRLF | CRLF (przywrócone) | **49** | **49** | `text=auto` `eol=lf` — **oczyszczone** |
| pozostałe pliki GWO (invoice, mapper, Form/Actions, …) | LF / OK | OK | mały | mały | OK |

Git ostrzega przy diffie:

```text
warning: in the working copy of 'app/services/contractor_service.py', CRLF will be replaced by LF the next time Git touches it
warning: in the working copy of 'frontend-react/src/api/contractors.js', CRLF will be replaced by LF the next time Git touches it
```

### Próby

1. WT = CRLF jak HEAD → raw nadal „cały plik” (smudge/clean + `eol=lf`).
2. Checkout HEAD + patch logiki bajtowo → ignore-cr = 3 linie; raw = 577.
3. CSS: pełny rewrite LF→CRLF cofnięty; raw = ignore-cr = +49 (tylko reguły adresu).

### Wniosek techniczny

**Nie da się** mieć feature-commita z `contractor_service.py` / `contractors.js` pokazującego tylko ~3 linie przy blobie HEAD = CRLF **oraz** `.gitattributes` `*.py`/`*.js` → `text eol=lf`.

Każdy commit tych plików **wymusi renormalizację EOL** w indeksie (masowy diff), albo wymaga **osobnego chore commit** `git add --renormalize` **przed** commitem funkcyjnym.

Zgodnie z bramką #2:

### EOL_NOISE_REMOVED

`NO` → **STOP** (nie READY_FOR_COMMIT).

---

## 3. SCOPE

### KSeF-only (planowane po odblokowaniu EOL)

| Plik | Klasa |
|---|---|
| `app/domain/party_address.py` | LOGIC_CHANGE |
| `app/domain/models/invoice.py` | LOGIC_CHANGE |
| `app/integrations/ksef/mapper.py` | LOGIC_CHANGE |
| `app/services/contractor_service.py` | LOGIC_CHANGE (+ EOL blocker) |
| `frontend-react/src/api/contractors.js` | LOGIC_CHANGE (+ EOL blocker) |
| `frontend-react/src/components/invoice/partyAddress.js` | LOGIC_CHANGE |
| `frontend-react/src/components/invoice/partyAddress.test.js` | TEST |
| `frontend-react/src/components/invoice/InvoiceForm.jsx` | UI |
| `frontend-react/src/components/invoice/InvoiceForm.module.css` | UI |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | UI |
| `frontend-react/src/components/invoice/InvoiceCardList.jsx` | UI |
| `tests/unit/test_ksef_partial_regon_address.py` | TEST |
| `docs/reports/…-0001.md` | REPORT |
| `docs/reports/…-0002-LOCAL-REVIEW.md` | REPORT |
| `docs/reports/…-0003-PRECOMMIT-GATE.md` | REPORT |

### UNRELATED (wykluczone z KSeF commit)

Guardian, Cursor/npm reports, `package.json`, numbering WIP (`invoiceCardListNumbering.test.js`), `docs/gwo/`, archiwum, starsze reports.

**UNRELATED w planowanym stage = 0** (selective add). Bloker = EOL, nie scope.

---

## 4. Finalny diff (dowód)

`git status --short` — KSeF + unrelated WIP (jak w sesji).

KSeF `--stat` (skrót):

```text
app/domain/models/invoice.py                       |  18 +-
app/integrations/ksef/mapper.py                    |  12 +-
app/services/contractor_service.py                 | 577 +++++++-------   ← EOL noise
frontend-react/src/api/contractors.js              |  27 +-               ← EOL noise
.../InvoiceActions.jsx                             |  65 +-
.../InvoiceCardList.jsx                            |   6 +-
.../InvoiceForm.jsx                                | 209 ++++-
.../InvoiceForm.module.css                         |  49 +                ← clean
```

```text
--ignore-cr-at-eol contractor_service + contractors.js:
  2 files changed, 5 insertions(+), 1 deletion(-)
```

`git diff --check` (KSeF UI CSS + party_address): **exit 0**.

---

## 5. Testy

```text
test_ksef_partial_regon_address.py     → 16 passed
test_contractor_service.py             → 6 passed
test_ksef_mapper + test_domain_invoice → 119 passed / 1 fail number_local (PREEXISTING)
partyAddress.test.js                   → 5 passed
invoice suite (bez numbering WIP)      → 16 passed
```

Zakres GWO: **PASS**.

---

## STATUS

`GATE_STOPPED_EOL`

## BASELINE_NUMBER_LOCAL_FAIL

`PREEXISTING`

## EOL_NOISE_REMOVED

`NO`

## DIFF_SCOPE_OK

`NO` (raw feature diff nieczysty przez CRLF↔LF na `contractor_service.py` + `contractors.js`)

## UNRELATED_FILES

`NONE` (przy selective add listy KSeF). W WT nadal: Guardian, Cursor reports, `package.json`, numbering WIP, `docs/gwo/`, archiwum — **poza** commit.

## BACKEND_TESTS

GWO PASS (16+6+mapper); 1 preexisting `number_local` FAIL poza GWO

## FRONTEND_TESTS

PASS (5 + 16 = 21)

## GIT_DIFF_CHECK

KSeF core/UI: **PASS** (exit 0 na sprawdzonych plikach). Pełne WT może FAIL na unrelated docs.

## FILES_READY_FOR_COMMIT

**Brak** — gate #2 STOP. Po chore renormalize EOL:

```text
app/domain/party_address.py
app/domain/models/invoice.py
app/integrations/ksef/mapper.py
app/services/contractor_service.py
frontend-react/src/api/contractors.js
frontend-react/src/components/invoice/partyAddress.js
frontend-react/src/components/invoice/partyAddress.test.js
frontend-react/src/components/invoice/InvoiceForm.jsx
frontend-react/src/components/invoice/InvoiceForm.module.css
frontend-react/src/components/invoice/InvoiceActions.jsx
frontend-react/src/components/invoice/InvoiceCardList.jsx
tests/unit/test_ksef_partial_regon_address.py
docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0001.md
docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0002-LOCAL-REVIEW.md
docs/reports/2026-09-22_GWO-IFG-KSEF-PARTIAL-REGON-ADDRESS-0003-PRECOMMIT-GATE.md
```

## READY_FOR_COMMIT

`NO`

## VERDICT

`STOP_EOL_BLOCKER`

Nie wykonano commit / push / deploy. Nie ruszano `number_local` ani numbering WIP ani `npm.autoDetect`.

### Propozycja odblokowania (decyzja)

1. **Chore commit** (osobno): renormalizacja EOL `contractor_service.py` + `contractors.js` do LF.
2. Ponów **0003 gate** → feature commit tylko logiki AdresL1 (~3+3 linie w tych plikach).

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

## Decyzje dla ChatGPT

1. Czy zaakceptować **osobny chore commit** renormalizacji EOL (`contractor_service.py`, `contractors.js`) przed feature commit KSeF?
2. Czy zamiast tego dopuścić feature commit z masowym EOL (odrzucone bramką 0003)?
