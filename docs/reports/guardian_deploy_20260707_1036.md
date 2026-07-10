# IFG Guardian — Deploy Run

**Generated:** 2026-07-07 10:36:43 UTC  
**Mode:** DRY-RUN  
**Rollback available:** `True`  
**Workflow ID:** `2026-07-07T103642Z_ifg_deploy_run`  
**Duration:** 0 ms  

## Pipeline

| # | Action | Status | Command |
|---|--------|--------|---------|
| 1 | git validation | SIMULATED | `git fetch origin production --quiet && git status --short` |
| 2 | backup database | SIMULATED | `ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && sudo docker compose -f docker/docker-compose.prod.yml exec -T db pg_dump -U postgres ifg > backups/guardian_pre_deploy.sql'` |
| 3 | alembic upgrade | SIMULATED | `ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && alembic upgrade head'` |
| 4 | frontend build | SIMULATED | `cd frontend-react && npm run build` |
| 5 | docker build | SIMULATED | `ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && sudo docker compose -f docker/docker-compose.prod.yml build api worker'` |
| 6 | container restart | SIMULATED | `ssh ds723 'cd /volume1/docker/ifg_v2/ifg_standalone && sudo docker compose -f docker/docker-compose.prod.yml up -d api worker'` |
| 7 | health verification | SIMULATED | `ssh ds723 'curl -sS -m 10 http://127.0.0.1:8000/health'` |
| 8 | smoke tests | SIMULATED | `ssh ds723 'curl -sS -m 10 http://127.0.0.1:8000/openapi.json | head -c 200'` |

## Summary

- **mode:** DRY-RUN
- **steps:** 8
- **rollback_available:** True
- **smoke_ok:** False
- **halted:** False
