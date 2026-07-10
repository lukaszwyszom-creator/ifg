# IFG Guardian — Release Plan

**Generated:** 2026-07-05 22:21:38 UTC  
**Question:** Co dokładnie zostanie wykonane, jeżeli uruchomię deploy?  
**Deployment risk:** `CRITICAL`  
**Doctor status:** `BLOCKED`  
**Workflow ID:** `2026-07-05T222137Z_ifg_release_plan`  
**Duration:** 0 ms  

## Dependencies

- `ifg.doctor` → SUCCESS (2026-07-05T222137Z_ifg_doctor)

## Repository

- Branch: `production`
- HEAD: `a405646` (`a4056464e1c1f8890e778b9e9c02ec8ba159879d`)
- Dirty: True
- Ahead/behind: 0/0

## Build decisions

| Decision | Required | Confidence | Reason |
|----------|----------|------------|--------|
| Frontend Build | yes | HIGH | ❌ [lokalnie] niezcommitowane zmiany frontend-react/src — dist nieaktualny (cd frontend-react && npm run build) |
| Backend Build | yes | HIGH | app/ or alembic/ changes detected |
| Worker Build | yes | HIGH | worker shares api image rebuild when backend changes |
| Compose Restart | yes | HIGH | services must restart after image/build/migration changes |
| Migration Required | no | HIGH | schema at head |
| Static Files | yes | HIGH | frontend dist must be rebuilt and synced to DS723+ |

## Artifacts

- **Git SHA:** `a4056464e1c1f8890e778b9e9c02ec8ba159879d` — target commit for deploy
- **Frontend bundle:** `33d4bd58fecb` — planned dist/assets fingerprint
- **Docker image API:** `ifg-api:a405646` — planned tag — not built in plan mode
- **Docker image Worker:** `ifg-worker:a405646` — planned tag — not built in plan mode
- **Alembic revision:** `[Errno 2] No such file or directory: 'alembic'` — target schema revision
- **Compose file:** `docker/docker-compose.prod.yml` — production compose definition
- **Compose service:** `api` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `worker` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `db` — service managed by docker/docker-compose.prod.yml

## Execution plan

1. **git pull** (required) — Synchronize DS723+ repository with origin/production
2. **frontend build** (required) — cd frontend-react && npm run build — ❌ [lokalnie] niezcommitowane zmiany frontend-react/src — dist nieaktualny (cd frontend-react && npm run build)
3. **docker build api** (required) — Rebuild API image — app/ or alembic/ changes detected
4. **docker build worker** (required) — Rebuild worker image — worker shares api image rebuild when backend changes
5. **migration** (optional) — Skipped — schema at head
6. **restart** (required) — docker compose up -d — services must restart after image/build/migration changes
7. **health** (required) — Verify /health and container states on DS723+
8. **log verification** (required) — Review api/worker logs for startup errors

## Risk rationale

- Doctor status: BLOCKED
