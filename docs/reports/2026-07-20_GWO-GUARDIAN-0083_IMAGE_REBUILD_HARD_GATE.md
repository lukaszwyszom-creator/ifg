---
kind: gwo
project: GUARDIAN
workflow: GWO-GUARDIAN-0083
handoff: true
created_at: 2026-07-20T20:30:00Z
updated_at: 2026-07-20T19:00:00Z
---

# GWO-GUARDIAN-0083 — Image rebuild hard gate (deploy)

**Data:** 2026-07-20  
**Implementation Status:** SUCCESS  
**STATUS:** PRODUCTION_VERIFIED  

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

**Commity:** `969bea3`, `c6a5dcf`, `378b5f7`, `9b4d187` (+ ten raport po weryfikacji)

## C. Deploy (produkcja DS723+)

| Pole | Wartość |
|------|---------|
| Workflow | `2026-07-20T184908Z_ifg_deploy_run` |
| Mode | LIVE |
| Outcome | **SUCCESS** |
| Duration | ~8m30s |
| Push | `origin/production` `a25526e..9b4d187` |
| Remote HEAD | `9b4d187ef83cd54f9a433d238c9d43c35198699c` |
| Komenda | `guardian ifg deploy run --yes --allow-dirty-build` |

### Hard gate — pierwszy deploy bez labeli

| Krok | Status | Dowód |
|------|--------|-------|
| Gate reason | REQUIRE_REBUILD | „Wdrożony obraz ifg-api nie ma labelu ifg.git.commit — wymuszam rebuild (expected HEAD=9b4d187ef83c)” |
| docker build api/worker | **EXECUTED** (nie SKIP) | ~7m10s build |
| image verify | **EXECUTED** | `ifg.git.commit=9b4d187ef83c` `image_id=sha256:eab0e1d3c376…` |

### Niezależna weryfikacja SSH (po deployu)

```
Id=sha256:eab0e1d3c3761b9d49c8c2fd70d2ac8421c0b8ea3471ab65314950edbe2d7a0f
ifg.git.commit=9b4d187ef83cd54f9a433d238c9d43c35198699c
oci.revision=9b4d187ef83cd54f9a433d238c9d43c35198699c
git rev-parse HEAD=9b4d187ef83cd54f9a433d238c9d43c35198699c
api image == worker image == ifg-api:latest Id (zgodne)
```

### Health usług

| Usługa | Status |
|--------|--------|
| ifg-api-1 | running, **healthy** |
| ifg-worker-1 | running (worker startuje OK) |
| ifg-db-1 | running, **healthy** |
| `GET /health` | `status=ok`, `environment=production`, `app_name=IFG Faktury` |
| `GET /openapi.json` | 200 |
| `GET /` (frontend) | 302 |

Raport Guardian: `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`  
Transaction: `.guardian/workflows/2026-07-20T184908Z_ifg_deploy_run/transaction.json`

## D. Testy

| Suite | Wynik |
|-------|-------|
| `tests/unit/test_guardian_image_rebuild_gate.py` | **PASS** |
| `tests/unit/test_guardian_deploy_decision_engine.py` | **PASS** |
| `tests/unit/test_guardian_deploy_executors.py` | **PASS** |
| `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | **PASS** |
| `tests/guardian_platform/test_deploy_run.py` | **PASS** (25) |

**Łącznie:** 87 passed (przed deployem).

### Macierz regresji (gate)

| Scenariusz | Oczekiwane | Dowód |
|------------|------------|--------|
| Czyste repo, label = HEAD | `ALLOW_SKIP` | unit test |
| Zmiana w `app/` | `REQUIRE_REBUILD` | unit test |
| Zmiana w `app/` + dirty | rebuild lub FAIL, nigdy SKIP | unit test |
| Obraz bez / z innym hashem | REQUIRE_REBUILD / FAIL | **prod:** brak labelu → EXECUTED rebuild + verify |

## E. Review commitów (przed push)

| Commit | Werdykt |
|--------|---------|
| `969bea3` feat gate + Dockerfile | OK — scope zgodny z celem |
| `c6a5dcf` testy | OK — macierz scenariuszy |
| `378b5f7` raport | OK |
| `9b4d187` handoff | OK (dociąga też historyczne HANDOFF-0002..0013) |

Gałąź: lokalne `production` == `origin/production` po push (`9b4d187`).  
Dirty tree lokalny (docs/WIP) **nie** obejmował image-context → gate nie FAIL; `--allow-dirty-build` tylko dla policy dirty tree.

## F. Następny krok

Zamknięte. Kolejne deploye przy zgodnym labelu mogą SKIP docker build; zmiana image-context / mismatch labelu wymusi rebuild.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Hard gate wymusił rebuild przy braku labelu (nie SKIP)
- Label `ifg.git.commit` = remote HEAD = `9b4d187…`
- Image Id api/worker zgodne; health API/DB healthy; worker running
- Smoke: `/health`, `/openapi.json`, `/` OK

⚠️ Znane problemy
- Lokalny dirty tree (docs archive / WIP) nadal wymaga `--allow-dirty-build` do policy — nie omija hard gate
- Adapter raportu „Build Actions” nadal pokazuje `docker build api/worker: NO` mimo EXECUTED w pipeline (kosmetyka raportu)

❌ Co nie działa
- Brak w zakresie GWO

---

## Technical Debt

- **LOW** — docstring w `image_rebuild_gate.py` nadal wspomina GWO-GUARDIAN-0080 zamiast 0083  
- **MEDIUM** — Decision Matrix „Build Actions” w deploy report nie mapuje kroku `docker build` pipeline → mylący `NO` przy faktycznym EXECUTED  
- **MEDIUM** — Label `ifg.git.commit` = pełny HEAD; commit tylko docs po deployu powoduje REQUIRE_REBUILD przy kolejnym deployu (świadomie konserwatywne; lepszy content-hash image-context poza zakresem)

## Decyzje dla ChatGPT

Brak.

## Wygenerowane raporty

- `docs/reports/2026-07-20_GWO-GUARDIAN-0083_IMAGE_REBUILD_HARD_GATE.md`
- `docs/guardian/IFG_DEPLOY_RUN_2026_07_20.md`
- `docs/handoff/HANDOFF-0017.md` (initial)
- `docs/handoff/HANDOFF-0018.md` (PRODUCTION_VERIFIED)
