# IFG Guardian — Deploy Run

**Generated:** 2026-07-20 18:57:39 UTC  

## Executive Summary

| Field | Value |
|-------|-------|
| **Status** | `READY` |
| **Decision** | `READY_WITH_OVERRIDE` |
| **Risk** | `MEDIUM` |
| **Workflow** | `2026-07-20T184908Z_ifg_deploy_run` |
| **Duration** | 0 ms |
| **Mode** | `LIVE` |
| **Doctor status** | `READY_WITH_WARNINGS` |
| **Release decision** | `READY_WITH_OVERRIDE` |
| **Release plan** | `2026-07-20T184908Z_ifg_release_plan` |
| **Release evaluate** | `2026-07-20T184920Z_ifg_release_evaluate` |
| **Dirty override** | `YES` |

## Decision Matrix

| Component | Decision | Confidence | Reason | Trigger files | Impact |
|-----------|----------|------------|--------|---------------|--------|
| git pull | EXECUTED | HIGH | Always required before deploy | — | required |
| frontend build | EXECUTED | HIGH | Mandatory — dist is not in git; API bind-mount requires host artifacts | — | required |
| artifact verify local | EXECUTED | HIGH | index.html and assets/*.js must exist before rsync | — | required |
| dist sync | EXECUTED | HIGH | Static assets must be on DS723+ before compose restart | — | required |
| artifact verify | EXECUTED | HIGH | index.html and assets/*.js must exist on host before compose up | — | required |
| docker build | EXECUTED | HIGH | Wdrożony obraz ifg-api nie ma labelu ifg.git.commit — wymuszam rebuild (expected HEAD=9b4d187ef83c) | — | required |
| alembic upgrade | SKIPPED | HIGH | Skipped — schema at head | — | optional |
| compose up | EXECUTED | HIGH | Start api/worker after artifact gate GO (compose executor re-verifies) | — | required |
| health check | EXECUTED | HIGH | Post-deploy verification | — | required |
| image verify | EXECUTED | HIGH | Hard gate: image label must match remote HEAD after deploy | — | required |
| log verification | EXECUTED | HIGH | Detect startup errors after deploy | — | required |

## Trigger Files

Brak.

## Local vs Remote

### LOCAL

Brak checków lokalnych.

### REMOTE

Brak checków zdalnych.

## Impact

Brak wpływu na komponenty.

## Build Actions

| Action | Decision | Reason | Command |
|--------|----------|--------|---------|
| docker build api | NO | not applicable | `—` |
| docker build worker | NO | not applicable | `—` |
| npm build | YES | Mandatory — dist is not in git; API bind-mount requires host artifacts | `cd frontend-react && npm run build` |
| alembic | NO | not applicable | `—` |
| compose up | NO | not applicable | `—` |
| health | NO | not applicable | `—` |
| logs | YES | Detect startup errors after deploy | `docker compose -f docker/docker-compose.prod.yml logs --tail=50 api worker` |

## Operator Actions

- Production build from dirty working tree (--allow-dirty-build).
- Production build from dirty working tree (--allow-dirty-build).
- Image rebuild gate: Wdrożony obraz ifg-api nie ma labelu ifg.git.commit — wymuszam rebuild (expected HEAD=9b4d187ef83c)
- ACTION_REQUIRED: Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree).
- ACTION_REQUIRED: Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices).
- ACTION_REQUIRED: Zweryfikuj untracked pliki przed produkcją: docs/_archiwum/, frontend-react/scripts/sample-contractor-city-prod.py, frontend-react/src/components/invoice/invoiceCardListNumbering.test.js, scripts/ifg_guardian/core/reporting/adapters_precheck.py, scripts/ifg_guardian/core/reporting/renderer.py, scripts/ifg_guardian/core/reporting/schema.py, scripts/ifg_guardian/core/reporting/status.py, scripts/ifg_guardian/modules/ifg_env_reload.py


## Execution Pipeline

| # | Action | Required | Status | Duration | Exit | Reason | Command |
|---|--------|----------|--------|----------|------|--------|---------|
| 1 | git pull | yes | EXECUTED | 0ms | 0 | Always required before deploy | `git pull origin production` |
| 2 | frontend build | yes | EXECUTED | 0ms | 0 | Mandatory — dist is not in git; API bind-mount requires host artifacts | `cd frontend-react && npm run build` |
| 3 | artifact verify local | yes | EXECUTED | 0ms |  | index.html and assets/*.js must exist before rsync | `python3 scripts/ifg_guardian_frontend_artifact_gate.py local` |
| 4 | dist sync | yes | EXECUTED | 0ms | 0 | Static assets must be on DS723+ before compose restart | `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/` |
| 5 | artifact verify | yes | EXECUTED | 0ms | 0 | index.html and assets/*.js must exist on host before compose up | `python3 scripts/ifg_guardian_frontend_artifact_gate.py remote` |
| 6 | docker build | yes | EXECUTED | 0ms | 0 | Wdrożony obraz ifg-api nie ma labelu ifg.git.commit — wymuszam rebuild (expected HEAD=9b4d187ef83c) | `docker compose -f docker/docker-compose.prod.yml build api worker` |
| 7 | alembic upgrade | no | SKIPPED | 0ms |  | Skipped — schema at head | `alembic upgrade head` |
| 8 | compose up | yes | EXECUTED | 0ms | 0 | Start api/worker after artifact gate GO (compose executor re-verifies) | `docker compose -f docker/docker-compose.prod.yml up -d` |
| 9 | health check | yes | EXECUTED | 0ms |  | Post-deploy verification | `curl -sS http://127.0.0.1:8000/health` |
| 10 | image verify | yes | EXECUTED | 0ms | 0 | Hard gate: image label must match remote HEAD after deploy | `ifg_guardian_image_verify` |
| 11 | log verification | yes | EXECUTED | 0ms | 0 | Detect startup errors after deploy | `docker compose -f docker/docker-compose.prod.yml logs --tail=50 api worker` |

## Wygenerowane raporty

- /Users/lukasz/projekty/ifg_standalone/docs/guardian/PRECHECK_REPORT_2026_07_20.md

## Wygenerowane handoffy

Brak.


## Decyzje dla ChatGPT

Brak.
