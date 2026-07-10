# IFG Guardian — Deploy Run

**Generated:** 2026-07-05 22:21:42 UTC  
**Mode:** DRY-RUN  
**Deployment risk:** `CRITICAL`  
**Doctor status:** `BLOCKED`  
**Release plan:** `2026-07-05T222137Z_ifg_release_plan`  
**Workflow ID:** `2026-07-05T222137Z_ifg_deploy_run`  
**Duration:** 0 ms  

## Dependencies

- `ifg.release.plan` → SUCCESS

## Blockers

- 🛑 Doctor status is BLOCKED (workflow 2026-07-05T222137Z_ifg_doctor)
- 🛑 Deployment risk is CRITICAL: Doctor status: BLOCKED

## Execution pipeline

| # | Action | Required | Status | Duration | Reason | Command |
|---|--------|----------|--------|----------|--------|---------|
| 1 | git pull | yes | SIMULATED | 0ms | Always required before deploy | `git pull origin production` |
| 2 | frontend build | yes | SIMULATED | 0ms | cd frontend-react && npm run build — ❌ [lokalnie] niezcommitowane zmiany frontend-react/src — dist nieaktualny (cd frontend-react && npm run build) | `cd frontend-react && npm run build` |
| 3 | dist sync | yes | SIMULATED | 0ms | Static assets must match local build before compose restart | `rsync -av frontend-react/dist/ /volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/` |
| 4 | docker build | yes | SIMULATED | 0ms | Rebuild API image — app/ or alembic/ changes detected | `docker compose -f docker/docker-compose.prod.yml build api worker` |
| 5 | alembic upgrade | no | SKIPPED | 0ms | Skipped — schema at head | `alembic upgrade head` |
| 6 | compose up | yes | SIMULATED | 0ms | docker compose up -d — services must restart after image/build/migration changes | `docker compose -f docker/docker-compose.prod.yml up -d` |
| 7 | health check | yes | SIMULATED | 0ms | Post-deploy verification | `curl -sS http://127.0.0.1:8000/health` |
| 8 | log verification | yes | SIMULATED | 0ms | Detect startup errors after deploy | `docker compose -f docker/docker-compose.prod.yml logs --tail=50 api worker` |

## Summary

- **mode:** DRY-RUN
- **deployment_risk:** CRITICAL
- **blockers:** 2
- **steps_total:** 8
- **steps_required:** 7
- **steps_skipped:** 1
- **steps_simulated:** 7
- **steps_executed:** 0
- **steps_failed:** 0
