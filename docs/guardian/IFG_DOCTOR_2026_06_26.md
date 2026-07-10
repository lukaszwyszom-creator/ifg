# IFG Guardian — IFG Doctor

**Generated:** 2026-06-26 21:44:00 UTC  
**Overall status:** `BLOCKED`  
**Question:** Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?  
**Workflow ID:** `2026-06-26T214359Z_ifg_doctor`  
**Duration:** 0 ms  

## Checks

### Environment

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | branch | on production (3451694) |
| `WARN` | git status | working tree dirty |
| `PASS` | ahead/behind | synced with origin/production |
| `PASS` | python | Python 3.13.13 |
| `PASS` | node | v25.9.0 |
| `PASS` | npm | 11.12.1 |

### Repository

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | repo audit | overall risk HIGH, 92 classified file(s) |
| `WARN` | dirty repo | working tree has tracked/untracked changes |
| `WARN` | line endings | 10 file(s) with unknown line endings |
| `WARN` | ignored files | 10 tracked/ignored conflict(s) |

### Frontend

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | frontend-react/src | uncommitted changes in frontend-react/src |
| `FAIL` | npm run build | ❌ [lokalnie] niezcommitowane zmiany frontend-react/src — brak dist (cd frontend-react && npm run build) |
| `FAIL` | dist freshness | ❌ [lokalnie] Frontend dist wymaga przebudowy (npm run build). |

### Backend

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | backend changes | 7 backend/alembic change(s) |
| `WARN` | build required | review backend changes |

### Docker

| Status | Check | Message |
|--------|-------|---------|
| `FAIL` | compose config | env file /Users/lukasz/projekty/ifg_standalone/.env.production not found: stat /Users/lukasz/projekty/ifg_standalone/.env.production: no such file or directory |
| `WARN` | remote docker | SSH/compose check unavailable: ssh: Could not resolve hostname : nodename nor servname provided, or not known |

### Database

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | postgres | postgres service declared in compose |
| `PASS` | connection | psycopg available locally |
| `PASS` | backup policy | backup documented in docs/migracja_mac_mini.md |

### Alembic

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | current | [Errno 2] No such file or directory: 'alembic' |
| `WARN` | head | [Errno 2] No such file or directory: 'alembic' |

### Configuration

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | .env.production.template | template present |
| `WARN` | .env.production | .env.production not found locally (may exist only on DS723+) |
| `PASS` | required variables | required keys documented in .env.example |

### Health

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | /health | health check unavailable: ssh: Could not resolve hostname : nodename nor servname provided, or not known |

## Summary

- **overall_status:** BLOCKED
- **checks_total:** 26
- **pass:** 11
- **warn:** 12
- **fail:** 3
- **critical:** 0
