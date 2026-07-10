# IFG Guardian — Deploy Run

**Generated:** 2026-07-09 13:06:11 UTC  
**Mode:** DRY-RUN  
**Deployment risk:** `CRITICAL`  
**Doctor status:** `BLOCKED`  
**Release plan:** `2026-07-09T130555Z_ifg_release_plan`  
**Release evaluate:** `2026-07-09T130558Z_ifg_release_evaluate`  
**Release decision:** `PRODUCTION_BLOCKED`  
**Workflow ID:** `2026-07-09T130555Z_ifg_deploy_run`  
**Duration:** 0 ms  

## Dependencies

- `ifg.release.plan` → SUCCESS
- `ifg.release.evaluate` → SUCCESS

## Blockers

- 🛑 Release decision is PRODUCTION_BLOCKED
- 🛑 Policy blocker: [backend] backend changes: 7 backend/alembic change(s)
- 🛑 Policy blocker: [backend] build required: rebuild api/worker required before deploy
- 🛑 Policy blocker: Policy rule triggered: dirty_working_tree_blocks_production
- 🛑 Policy blocker: Policy rule triggered: tests_must_pass
- 🛑 Policy blocker: Production deployment blocked. Working tree contains uncommitted changes.

## Warnings

- ⚠ ACTION_REQUIRED: Zacommituj zmiany lub użyj jawnego override: guardian ifg deploy run --allow-dirty-build --yes
- ⚠ ACTION_REQUIRED: Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- ⚠ ACTION_REQUIRED: Napraw test discovery i uruchom ponownie evaluate.
- ⚠ ACTION_REQUIRED: Wymagany rebuild obrazów api/worker przed produkcją.
- ⚠ ACTION_REQUIRED: Zweryfikuj untracked pliki przed produkcją: .state/, docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md, docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md, docs/FV_NUMBERING_RENUMBERING_BUG.md, docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md, docs/FV_WZ_AUTO_SYNC_ANALYSIS.md, docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md, docs/IFG_PENDING_CHANGES_AUDIT.md

## Execution pipeline

| # | Action | Required | Status | Duration | Exit | Reason | Command |
|---|--------|----------|--------|----------|------|--------|---------|
| 1 | git pull | yes | SIMULATED | 0ms |  | Always required before deploy | `git pull origin production` |
| 2 | frontend build | yes | SIMULATED | 0ms |  | Mandatory — dist is not in git; API bind-mount requires host artifacts | `cd frontend-react && npm run build` |
| 3 | artifact verify local | yes | SIMULATED | 0ms |  | index.html and assets/*.js must exist before rsync | `python3 scripts/ifg_guardian_frontend_artifact_gate.py local` |
| 4 | dist sync | yes | SIMULATED | 0ms |  | Static assets must be on DS723+ before compose restart | `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/` |
| 5 | artifact verify | yes | SIMULATED | 0ms |  | index.html and assets/*.js must exist on host before compose up | `python3 scripts/ifg_guardian_frontend_artifact_gate.py remote` |
| 6 | docker build | yes | SIMULATED | 0ms |  | Rebuild API image — rebuild api/worker required before deploy | `docker compose -f docker/docker-compose.prod.yml build api worker` |
| 7 | alembic upgrade | no | SKIPPED | 0ms |  | Skipped — schema at head | `alembic upgrade head` |
| 8 | compose up | yes | SIMULATED | 0ms |  | Start api/worker after artifact gate GO (compose executor re-verifies) | `docker compose -f docker/docker-compose.prod.yml up -d` |
| 9 | health check | yes | SIMULATED | 0ms |  | Post-deploy verification | `curl -sS http://127.0.0.1:8000/health` |
| 10 | log verification | yes | SIMULATED | 0ms |  | Detect startup errors after deploy | `docker compose -f docker/docker-compose.prod.yml logs --tail=50 api worker` |

## Summary

- **mode:** DRY-RUN
- **release_decision:** PRODUCTION_BLOCKED
- **deployment_risk:** CRITICAL
- **blockers:** 6
- **steps_total:** 10
- **steps_required:** 9
- **steps_skipped:** 1
- **steps_simulated:** 9
- **steps_executed:** 0
- **steps_failed:** 0

## Decyzje dla ChatGPT

Brak.
