---
kind: gwo
project: GUARDIAN
workflow: GWO-GUARDIAN-0083
handoff: true
created_at: 2026-07-20T20:30:00Z
---

# GWO-GUARDIAN-0083 — Image rebuild hard gate (deploy)

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS (lokalnie; bez deployu produkcyjnego)  
**STATUS:** SUCCESS  

---

## Problem

W GWO-IFG-0029 `guardian ifg deploy run` zakończył się sukcesem z **docker build SKIP**, mimo zmian w `app/`. Dirty tree + puste porównanie lokalne vs `origin` nie wymusiło rebuildu. Obrazy API/worker wymagały ręcznego `docker compose build` na DS723+.

## Cel

Twardy gate: deploy **nie może** być sukcesem, jeśli kontekst obrazu zmienił się (lub nie zgadza się z wdrożonym obrazem), a obraz nie został przebudowany / zweryfikowany.

## A. Root cause

1. Decyzja rebuildu opierała się głównie na `origin/production...HEAD` + dirty tracked — **bez** porównania z labelami działającego obrazu.
2. `--allow-dirty-build` odblokowywało politykę dirty tree, ale **nie** ustawiało `backend.build_required`.
3. Dockerfile **nie** miał labelu z SHA źródeł → brak weryfikacji post-deploy.

## B. Zmienione pliki

### Gate / decyzje
- `scripts/ifg_guardian/plugins/ifg/deploy_decision/image_rebuild_gate.py` (nowy)
- `scripts/ifg_guardian/plugins/ifg/deploy_decision/image_inspect.py` (nowy)
- `scripts/ifg_guardian/plugins/ifg/deploy_decision/image_gate_resolve.py` (nowy)
- `scripts/ifg_guardian/plugins/ifg/deploy_decision/paths.py` — `IMAGE_CONTEXT_*`, `is_image_context_path`
- `scripts/ifg_guardian/plugins/ifg/deploy_decision/git_scope.py` — dirty/untracked/image-context helpers
- `scripts/ifg_guardian/plugins/ifg/doctor/checks.py` — `backend.image_rebuild_gate`
- `scripts/ifg_guardian/plugins/ifg/doctor/stages.py`
- `scripts/ifg_guardian/plugins/ifg/release_plan/build_detector.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`

### Pipeline / executors
- `scripts/ifg_guardian/plugins/ifg/deploy_run/pipeline.py` — force rebuild + krok `image verify`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/stages.py` — gate w BlockerStage
- `scripts/ifg_guardian/core/workflow/executors/docker_executor.py` — `--build-arg IFG_GIT_COMMIT`, `execute_image_verify`
- `scripts/ifg_guardian/core/workflow/executors/router.py` — `IMAGE_VERIFY`
- `scripts/ifg_guardian/core/workflow/executors/__init__.py`
- `scripts/ifg_guardian/core/workflow/intents.py` — `LocalExecIntent.meta`
- `scripts/ifg_guardian/core/progress/mapping.py`

### Obraz
- `docker/Dockerfile` — `ARG IFG_GIT_COMMIT` + labely `ifg.git.commit`, `org.opencontainers.image.revision`

### Testy
- `tests/unit/test_guardian_image_rebuild_gate.py` (nowy)
- `tests/unit/test_guardian_deploy_executors.py`
- `tests/unit/test_guardian_ifg_deploy_run_workflow.py`

## C. Deploy

**Nie wdrażano na produkcję** (wymóg: najpierw testy).

Pierwszy produkcyjny deploy po merge **musi** przebudować API/worker (stare obrazy bez labelu → `REQUIRE_REBUILD` / post-deploy verify bez labelu → FAIL do czasu rebuildu z nowym Dockerfile).

## D. Testy

| Suite | Wynik |
|-------|-------|
| `tests/unit/test_guardian_image_rebuild_gate.py` | **PASS** |
| `tests/unit/test_guardian_deploy_decision_engine.py` | **PASS** |
| `tests/unit/test_guardian_deploy_executors.py` | **PASS** |
| `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | **PASS** |
| `tests/guardian_platform/test_deploy_run.py` | **PASS** (25) |

**Łącznie powyższe:** 62 + 25 = **87 passed**.

### Macierz regresji (gate)

| Scenariusz | Oczekiwane | Dowód |
|------------|------------|--------|
| Czyste repo, label = HEAD | `ALLOW_SKIP` | `test_clean_repo_matching_label_allows_skip` |
| Zmiana w `app/` (committed) | `REQUIRE_REBUILD` | `test_app_change_requires_rebuild` |
| Zmiana w `app/` + dirty | `REQUIRE_REBUILD` lub `FAIL`, nigdy `SKIP` | `test_app_change_with_dirty_tree_never_skip_*` |
| Obraz z innym hashem | `REQUIRE_REBUILD` / post-deploy FAIL | `test_label_mismatch_*`, `test_mismatch_makes_deploy_unsuccessful` |

## E. Następny krok

1. Review + merge commitów GWO-GUARDIAN-0083.
2. Pierwszy `guardian ifg deploy run` na DS723+ z oczekiwanym **docker build** (labely).
3. Po deployu sprawdzić: `docker image inspect ifg-api:latest` → `ifg.git.commit` == remote `git rev-parse HEAD`.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Hard gate: dirty image-context → FAIL lub REQUIRE_REBUILD, nigdy SKIP
- Porównanie z labelami wdrożonego obrazu (nie tylko vs origin)
- Dockerfile labely + build-arg; krok `image verify` w pipeline
- Testy regresyjne macierzy scenariuszy — PASS

⚠️ Znane problemy
- Obrazy produkcyjne sprzed tego GWO nie mają labelu — pierwszy deploy wymusi rebuild
- Lokalny doctor używa `defer_remote_verify` (SSH dopiero w deploy run)

❌ Co nie działa
- Brak (w zakresie GWO); produkcja nie była wdrażana w tym zadaniu

---

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-GUARDIAN-0083_IMAGE_REBUILD_HARD_GATE.md`
