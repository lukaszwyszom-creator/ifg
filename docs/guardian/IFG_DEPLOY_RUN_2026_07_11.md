# IFG Guardian — Deploy Run

**Generated:** 2026-07-11 21:26:06 UTC  
**Mode:** LIVE  
**Deployment risk:** `CRITICAL`  
**Doctor status:** `BLOCKED`  
**Release plan:** `2026-07-11T212532Z_ifg_release_plan`  
**Release evaluate:** `2026-07-11T212535Z_ifg_release_evaluate`  
**Release decision:** `READY_WITH_OVERRIDE`  
**Dirty tree override:** `YES` (--allow-dirty-build)  
**Workflow ID:** `2026-07-11T212532Z_ifg_deploy_run`  
**Duration:** 0 ms  

## Dependencies

- `ifg.release.plan` → SUCCESS
- `ifg.release.evaluate` → SUCCESS

## Rollback point

- **commit_before:** `4a71c14`
- **images_before:** `ifg-api:latest
ifg-frontend:latest
ifg-api:amd64
ifg-frontend:amd64
docker-api:latest`
- **alembic_before:** `a9b1c2d3e4f5 (head)`

## Warnings

- ⚠ Production build from dirty working tree (--allow-dirty-build).
- ⚠ Production build from dirty working tree (--allow-dirty-build).
- ⚠ ACTION_REQUIRED: Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree).

## Execution pipeline

| # | Action | Required | Status | Duration | Exit | Reason | Command |
|---|--------|----------|--------|----------|------|--------|---------|
| 1 | git pull | yes | EXECUTED | 0ms | 0 | Always required before deploy | `git pull origin production` |
| 2 | frontend build | yes | EXECUTED | 0ms | 0 | Mandatory — dist is not in git; API bind-mount requires host artifacts | `cd frontend-react && npm run build` |
| 3 | artifact verify local | yes | EXECUTED | 0ms |  | index.html and assets/*.js must exist before rsync | `python3 scripts/ifg_guardian_frontend_artifact_gate.py local` |
| 4 | dist sync | yes | EXECUTED | 0ms | 0 | Static assets must be on DS723+ before compose restart | `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/` |
| 5 | artifact verify | yes | EXECUTED | 0ms | 0 | index.html and assets/*.js must exist on host before compose up | `python3 scripts/ifg_guardian_frontend_artifact_gate.py remote` |
| 6 | docker build | no | SKIPPED | 0ms |  | No image rebuild required | `docker compose -f docker/docker-compose.prod.yml build api worker` |
| 7 | alembic upgrade | no | SKIPPED | 0ms |  | Skipped — schema at head | `alembic upgrade head` |
| 8 | compose up | yes | EXECUTED | 0ms | 0 | Start api/worker after artifact gate GO (compose executor re-verifies) | `docker compose -f docker/docker-compose.prod.yml up -d` |
| 9 | health check | yes | EXECUTED | 0ms | 0 | Post-deploy verification | `curl -sS http://127.0.0.1:8000/health` |
| 10 | log verification | yes | EXECUTED | 0ms | 0 | Detect startup errors after deploy | `docker compose -f docker/docker-compose.prod.yml logs --tail=50 api worker` |

## Executed commands

- `rollback_commit: ssh zdalny_admin@ds723`
- `rollback_alembic: ssh zdalny_admin@ds723`
- `rollback_images: ssh zdalny_admin@ds723`
- `git pull origin production`
- `git_pull_remote: ssh zdalny_admin@ds723`
- `cd frontend-react && npm run build`
- `python3 scripts/ifg_guardian_frontend_artifact_gate.py local`
- `rsync -av --rsync-path=/bin/rsync -e "ssh -p 32122" frontend-react/dist/ zdalny_admin@ds723:/volume1/docker/ifg_v2/ifg_standalone/frontend-react/dist/`
- `python3 scripts/ifg_guardian_frontend_artifact_gate.py remote`
- `artifact_gate_remote: ssh zdalny_admin@ds723`
- `artifact_gate_pre_compose: ssh zdalny_admin@ds723`
- `compose_up: ssh zdalny_admin@ds723`
- `compose_ps: ssh zdalny_admin@ds723`
- `curl -fsS "http://127.0.0.1:8000/health"`
- `http_health: ssh zdalny_admin@ds723`
- `compose_logs: ssh zdalny_admin@ds723`

## Health

```
{"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
```

## Containers

```
NAME                IMAGE               COMMAND                  SERVICE             CREATED             STATUS                 PORTS
ifg-api-1           ifg-api:latest      "uvicorn app.main:ap…"   api                 12 hours ago        Up 4 hours (healthy)   127.0.0.1:8000->8000/tcp
ifg-db-1            postgres:17         "docker-entrypoint.s…"   db                  12 hours ago        Up 4 hours (healthy)   5432/tcp
ifg-worker-1        ifg-api:latest      "sh -c 'python -m ap…"   worker              12 hours ago        Up 4 hours
```

## Summary

- **mode:** LIVE
- **release_decision:** READY_WITH_OVERRIDE
- **deployment_risk:** CRITICAL
- **blockers:** 0
- **steps_total:** 10
- **steps_required:** 8
- **steps_skipped:** 2
- **steps_simulated:** 0
- **steps_executed:** 8
- **steps_failed:** 0

## Decyzje dla ChatGPT

Brak.
