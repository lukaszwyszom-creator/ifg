# GWO-IFG-0038A — Workspace Normalization Execution (Etap A)

**Data:** 2026-07-08  
**Branch:** `production`  
**Zakres:** wykonanie wyłącznie Etapu A z planu GWO-IFG-0038  
**Plan źródłowy:** `docs/reports/2026-07-08_GWO-IFG-0038_WORKSPACE_NORMALIZATION_PLAN.md`

---

## Podsumowanie wykonania

| Metryka | Przed | Po |
|---------|-------|-----|
| HEAD | `a8410f3` | `876900f` |
| Pozycje w `git status` | **166** | **150** |
| Modified | 41 | 31 |
| Untracked | 124 (+ plan 0038) | 119 (+ ten raport) |
| Commity Etapu A | 0 | **2** |

**Etap A:** ✅ **ZAKOŃCZONY**

---

## Wykonane commity

### Commit 1 — `2fff98c`

```
fix(ksef): GWO-IFG-0036 monitor UI remnants
```

**Pliki (4):**

| Plik | Zmiana merytoryczna |
|------|---------------------|
| `frontend-react/src/pages/advanced/AdvancedDashboard.jsx` | Zakładka `Monitor KSeF` |
| `frontend-react/src/api/transmissions.js` | Parametr `warnings_or_errors_only` |
| `frontend-react/src/components/dashboard/TransmissionTable.module.css` | Liczniki, filtr, metadata styles |
| `frontend-react/src/components/common/StatusBadge.jsx` | Severity KSeF (`info`, `warning`, `error`, `running`, …) |

**Przed commitem odrzucono (CRLF/whitespace):**  
`transmission_repository.py`, `invoice_mapper.py`, `invoice.py`, `invoice_number_policy.py`, `payment_service.py`, `invoices.js`, `InvoiceActions.jsx`, `vite.config.js`

**Testy po commicie:**

```text
pytest tests/unit/test_transmission_api.py -q -p no:cov
16 passed in 0.51s
```

**Weryfikacja indeksu:** `git show --name-only -1` → wyłącznie 4 pliki frontend.

---

### Commit 2 — `876900f`

```
feat(guardian): GWO-IFG-0037 release engine quality
```

**Pliki (12):**

| Plik |
|------|
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/classification.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/report.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/service.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/workflow.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/__init__.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/models.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py` |
| `scripts/ifg_guardian/policies/ifg_production.yaml` |
| `scripts/ifg_guardian/core/workflow/transaction.py` |
| `tests/unit/test_guardian_ifg_release_evaluate_workflow.py` |
| `docs/reports/2026-07-08_GWO-IFG-0037_RELEASE_ENGINE_QUALITY.md` |

**Wykluczono z commita (zgodnie z planem):** progress, dashboard, execution engine, executors, pyproject.toml, engine.py, plugin.py, itd.

**Testy po commicie:**

```text
pytest tests/unit/test_guardian_ifg_release_evaluate_workflow.py -q -p no:cov
13 passed in 0.16s
```

**Weryfikacja indeksu:** `git show --name-only -1` → wyłącznie 12 plików Grupy 2.

---

## Git log po Etapie A

```
876900f feat(guardian): GWO-IFG-0037 release engine quality
2fff98c fix(ksef): GWO-IFG-0036 monitor UI remnants
a8410f3 GWO-IFG-0036: fix KSeF monitor and production integrity policy
b7ad331 feat(ksef): split purchase auth from online session (GWO-IFG-0032/0033)
5a5d713 fix(guardian): hard-reset remote repo on deploy git sync
```

---

## Pozostałe zmiany (150 pozycji)

### Modified (31) — głównie Grupa 3 + szum CRLF

**Guardian eksperymenty (Grupa 3 — Etap B):**  
`engine.py`, executors (5), `config.py`, `deploy_config.py`, `frontend_artifacts.py`, moduły doctor/release_plan/cutover/workflow, raporty timeline, `plugin.py`, `deploy_run/service.py`, testy deploy/artifacts/plugins_sprint2, `pyproject.toml`

**Konfiguracja (Grupa 6):**  
`scripts/ds723.env`

**Szum CRLF (Grupa 5 — ponownie widoczny po commitach):**  
`invoice_mapper.py`, `invoice.py`, `transmission_repository.py`, `invoice_number_policy.py`, `payment_service.py`, `invoices.js`, `InvoiceActions.jsx`, `vite.config.js`  
*(brak diffu merytorycznego przy `--ignore-cr-at-eol`)*

### Untracked (119)

- **Grupa 3:** `core/progress/`, `core/dashboard/`, `core/execution/`, testy progress/dashboard, `ds723_pull_unblock.py`, `ifg_guardian_frontend_artifact_gate.py`
- **Grupa 4:** ~85 plików docs/reports + docs/guardian/
- **Grupa 5:** `invoiceCardListNumbering.test.js`
- **Raporty planów:** `GWO-IFG-0038`, `GWO-IFG-0038A` (ten plik)

---

## Release Engine po Etapie A

```text
PYTHONPATH=scripts python scripts/guardian.py release evaluate --no-progress

Decision: PRODUCTION_BLOCKED
Duration: 28260 ms
Release Score: 74/100
Executive Summary:
  Project status:     BLOCKED
  Environment status: WARNING
  Policy status:      BLOCK

Blockers:
  • dirty_working_tree_blocks_production
  • frontend_change_requires_passing_build (dirty tree + brak npm build)
```

**Wniosek:** Commity Etapu A są poprawne, ale **deploy nadal zablokowany** przez:
1. dirty working tree (150 pozostałych plików),
2. brak świeżego `frontend-react/dist` po commicie UI.

---

## Odpowiedzi na pytania kontrolne

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy Etap A zakończony? | **TAK** — 2 commity, 16 plików, testy passed |
| Ile plików poza commitami? | **150** (31 modified + 119 untracked) |
| Czy production gotowe do deploy? | **NIE** — `PRODUCTION_BLOCKED` (dirty tree + dist) |
| Czy można przejść do Etapu B? | **TAK** — Etap A domknięty; B = stash/branch Grupy 3 |

---

## Rekomendacja dalszych działań (Etap B — nie wykonano)

1. `git checkout --` na 8 plikach CRLF (Grupa 5).
2. Branch `feature/guardian-progress-dashboard` lub `git stash` dla Grupy 3 (54 pliki kodu).
3. `cd frontend-react && npm run build` po clean tree (przed deployem).
4. Commit archiwum docs (Grupa 4) lub `.gitignore` dla `docs/guardian/IFG_*`.
5. `release evaluate` ponownie — oczekiwany status po clean tree: `READY_WITH_WARNINGS` lub `READY_FOR_DEPLOY`.

---

## Wykonane analizy

- Porównanie `git status` przed/po (166 → 150)
- `git diff --cached --ignore-cr-at-eol` przed commitem 0036
- `git show --name-only` po każdym commicie
- `release evaluate` po Etapie A
- Weryfikacja CRLF na pozostałych plikach invoice

## Wykonane raporty

- `docs/reports/2026-07-08_GWO-IFG-0038A_WORKSPACE_NORMALIZATION_EXECUTION.md` (ten dokument)

---

🩷 STATUS KOŃCOWY

✅ Etap A wykonany — commity `2fff98c` + `876900f`, testy 16+13 passed  
⚠️ 150 plików poza commitami (G3 eksperymenty + docs)  
❌ Deploy — NOT READY (`PRODUCTION_BLOCKED`)
