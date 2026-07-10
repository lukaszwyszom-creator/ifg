# IFG Guardian — Release Plan

**Generated:** 2026-07-08 22:32:18 UTC  
**Question:** Co dokładnie zostanie wykonane, jeżeli uruchomię deploy?  
**Deployment risk:** `MEDIUM`  
**Doctor status:** `READY_WITH_WARNINGS`  
**Workflow ID:** `2026-07-08T223207Z_ifg_release_plan`  
**Duration:** 0 ms  

## Dependencies

- `ifg.doctor` → SUCCESS (2026-07-08T223207Z_ifg_doctor)

## Repository

- Branch: `production`
- HEAD: `f5215b0` (`f5215b0984dfc12b416e5057713ea8382940c0fd`)
- Dirty: True
- Ahead/behind: 0/0

## Build decisions

| Decision | Required | Confidence | Reason |
|----------|----------|------------|--------|
| Frontend Build | yes | MEDIUM | frontend-react/src changes detected |
| Backend Build | yes | HIGH | app/ or alembic/ changes detected |
| Worker Build | yes | HIGH | worker shares api image rebuild when backend changes |
| Compose Restart | yes | HIGH | services must restart after image/build/migration changes |
| Migration Required | no | HIGH | schema at head |
| Static Files | yes | MEDIUM | frontend dist must be rebuilt and synced to DS723+ |

## Artifacts

- **Git SHA:** `f5215b0984dfc12b416e5057713ea8382940c0fd` — target commit for deploy
- **Frontend bundle:** `3c5232ab4e9a` — planned dist/assets fingerprint
- **Docker image API:** `ifg-api:f5215b0` — planned tag — not built in plan mode
- **Docker image Worker:** `ifg-worker:f5215b0` — planned tag — not built in plan mode
- **Alembic revision:** `[Errno 2] No such file or directory: 'alembic'` — target schema revision
- **Compose file:** `docker/docker-compose.prod.yml` — production compose definition
- **Compose service:** `api` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `worker` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `db` — service managed by docker/docker-compose.prod.yml

## Execution plan

1. **git pull** (required) — Synchronize DS723+ repository with origin/production
2. **frontend build** (required) — cd frontend-react && npm run build — frontend-react/src changes detected
3. **docker build api** (required) — Rebuild API image — app/ or alembic/ changes detected
4. **docker build worker** (required) — Rebuild worker image — worker shares api image rebuild when backend changes
5. **migration** (optional) — Skipped — schema at head
6. **restart** (required) — docker compose up -d — services must restart after image/build/migration changes
7. **health** (required) — Verify /health and container states on DS723+
8. **log verification** (required) — Review api/worker logs for startup errors

## Risk rationale

- Doctor status: READY_WITH_WARNINGS
