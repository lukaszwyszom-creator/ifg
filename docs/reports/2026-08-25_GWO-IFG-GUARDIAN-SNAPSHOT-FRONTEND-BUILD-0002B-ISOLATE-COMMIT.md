# GWO-IFG-GUARDIAN-SNAPSHOT-FRONTEND-BUILD-0002B-ISOLATE-COMMIT

**Data:** 2026-08-25  
**Repo:** `/Users/lukasz/projekty/ifg_standalone`  
**Base:** `b312a81`  
**Commit:** `831c7327540bbf96a434b378601b5def0fcca2c8`

---

## STATUS: SUCCESS

Odizolowany commit zawiera wyłącznie implementację GWO-0002 (12 plików). Wcześniejszy WIP pozostał unstaged/untracked.

---

## STAGED MANIFEST (pre-commit)

```text
git diff --cached --name-only  → 12 plików
git diff --cached --check      → PASS (brak błędów)
```

| # | Plik | Uwagi |
|---|------|-------|
| 1 | `scripts/ifg_guardian/core/build_snapshot.py` | pełny |
| 2 | `scripts/ifg_guardian/core/workflow/executors/__init__.py` | pełny |
| 3 | `scripts/ifg_guardian/core/workflow/executors/router.py` | pełny |
| 4 | `scripts/ifg_guardian/plugins/ifg/deploy_run/pipeline.py` | pełny |
| 5 | `scripts/ifg_guardian/plugins/ifg/doctor/aggregation.py` | **tylko 0002** (BUILD_REQUIRED/IMAGE_REBUILD demotion) |
| 6 | `scripts/ifg_guardian/plugins/ifg/doctor/checks.py` | pełny |
| 7 | `scripts/ifg_guardian/plugins/ifg/release_evaluate/classification.py` | pełny |
| 8 | `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py` | pełny |
| 9 | `scripts/ifg_guardian/policies/ifg_production.yaml` | pełny |
| 10 | `tests/unit/test_guardian_deploy_executors.py` | pełny |
| 11 | `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | pełny |
| 12 | `tests/unit/test_guardian_frontend_snapshot_build.py` | pełny (nowy) |

### `aggregation.py` — selektywny stage

**W commicie (0002):** `_BUILD_REQUIRED_CHECK_IDS`, `_IMAGE_REBUILD_REQUIRED_IDS`, `effective_check_status` (demotion FAIL→WARN), `worst_check_status` / `aggregate_overall_status` przez `effective_check_status`.

**Pozostało unstaged (wcześniejszy WIP):** `_LOCAL_SOFT_FAIL_IDS` (alembic), `_is_local_db_unavailable`, gałąź alembic w `effective_check_status`.

---

## STAGED-ONLY VERIFICATION

1. `git archive b312a81` → `/tmp/ifg-0002b-staged-verify`
2. `git diff --cached` → patch → `git apply` (tylko staged)
3. Testy + npm + gate na drzewie bez dostępu do unstaged WIP głównego repo

### Testy

| Zestaw | Wynik | Uwagi |
|--------|-------|-------|
| 0002-core (5 plików testów) | **68 passed** | staged-only |
| Pełny zestaw 0002 (7 plików bez deploy_decision_engine) | **94 passed, 1 failed** | 1 fail pre-existing na `b312a81` |
| `test_guardian_deploy_decision_engine.py` | **N/A (12 testów)** | plik untracked WIP — nie w `b312a81`, zabroniony w commicie |

**Pre-existing fail (nie regresja 0002):**  
`test_guardian_ifg_doctor_workflow.py::TestReportRendering::test_markdown_report` — na czystym `b312a81` oczekuje `"Workflow ID"`, raport ma `"| **Workflow** |"`. Fix jest w unstaged WIP (zabroniony plik).

### npm ci + build + artifact gate (staged-only tree)

| Krok | Wynik |
|------|-------|
| `npm ci --prefer-offline --no-audit --no-fund` | PASS |
| `npm run build` | PASS (Vite, `dist/index.html` + `assets/*.js`) |
| `verify_local_dist` | **GO** (`js_count=1`) |

4. Katalog tymczasowy usunięty po weryfikacji.

---

## COMMIT

```text
831c7327540bbf96a434b378601b5def0fcca2c8
fix: make snapshot frontend builds reproducible
12 files changed, 486 insertions(+), 40 deletions(-)
```

---

## WIP PO COMMICIE (nietknięty)

```text
 M docs/GUARDIAN2_RECOVERY_DS723.md
 M docs/_archiwum/migracja_mac_mini.md
 M scripts/ifg_guardian/plugins/ifg/doctor/aggregation.py   ← alembic soft-fail WIP
 M scripts/ifg_guardian/plugins/ifg/release_plan/stages.py
 M tests/unit/test_guardian_ifg_doctor_workflow.py
 M tests/unit/test_guardian_ifg_handoff.py
 M tests/unit/test_guardian_preflight.py
?? docs/gwo/
?? docs/reports/2026-07-20_GWO-GUARDIAN_IFG_RELEASE_STATE_CONTRACT.md
?? frontend-react/src/components/invoice/invoiceCardListNumbering.test.js
?? tests/unit/test_guardian_deploy_decision_engine.py
```

---

## Bezpieczeństwo operacyjne

| Akcja | Wynik |
|-------|-------|
| DEPLOY | **NIE WYKONANY** |
| PUSH | **NIE WYKONANY** |
| `--yes` | nie użyto |
| `--allow-dirty-build` | nie użyto |
| stash / reset --hard | nie użyto |
| DS723+ | **NIETKNIĘTY** |

---

## RELEASE STATE

- [x] LOCAL_REVIEW_REQUIRED
- [ ] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

---

## Decyzje dla ChatGPT

Brak.

## GENERATED REPORTS

/Users/lukasz/projekty/ifg_standalone/docs/reports/2026-08-25_GWO-IFG-GUARDIAN-SNAPSHOT-FRONTEND-BUILD-0002B-ISOLATE-COMMIT.md
