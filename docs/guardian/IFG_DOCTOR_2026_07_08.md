# IFG Guardian — IFG Doctor

**Generated:** 2026-07-08 22:32:21 UTC  
**Overall status:** `READY_WITH_WARNINGS`  
**Question:** Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?  
**Workflow ID:** `2026-07-08T223218Z_ifg_doctor`  
**Duration:** 0 ms  

## Checks

### Environment

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | branch | on production (f5215b0) |
| `WARN` | git status | working tree dirty |
| `PASS` | ahead/behind | synced with origin/production |
| `PASS` | python | Python 3.13.13 |
| `PASS` | node | v25.9.0 |
| `PASS` | npm | 11.12.1 |

### Repository

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | repo audit | overall risk HIGH, 167 classified file(s) |
| `WARN` | dirty repo | working tree has tracked/untracked changes |
| `WARN` | line endings | 8 file(s) with unknown line endings |
| `PASS` | ignored files | no tracked ignore conflicts |

### Frontend

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | frontend-react/src | uncommitted changes in frontend-react/src |
| `PASS` | npm run build | ✅ [lokalnie] dist nowszy niż niezcommitowane zmiany src |
| `PASS` | dist freshness | ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src |

### Backend

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | backend changes | 5 backend/alembic change(s) |
| `WARN` | build required | review backend changes |

### Docker

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | compose config | compose file valid |
| `PASS` | containers | api/worker/db running |
| `PASS` | images | compose ps returned 3 service(s) |

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
| `PASS` | .env.production | .env.production present locally |
| `PASS` | required variables | required keys documented in .env.example |

### Health

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | /health | {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}} |

## Summary

- **overall_status:** READY_WITH_WARNINGS
- **checks_total:** 27
- **pass:** 19
- **warn:** 8
- **fail:** 0
- **critical:** 0
