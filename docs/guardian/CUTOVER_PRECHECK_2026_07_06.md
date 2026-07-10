# Guardian Preflight — PRECHECK_REPORT

**Generated:** 2026-07-06 21:49:30 UTC  
**Workflow:** `2026-07-06T214930Z_ifg_container_cutover`  
**Mode:** `DRY_RUN`  
**Decision:** **GO**  
**Duration:** 22 ms  

## Summary

| PASS | WARNING | FAIL |
|------|---------|------|
| 4 | 14 | 0 |

## Warnings

- .env exists: local .env.production not found — will verify on remote
- Git clean: uncommitted changes (88 line(s))
- SSH works: remote checks skipped
- Docker available: remote checks skipped
- Docker Compose available: remote checks skipped
- Compose config valid: remote checks skipped
- Compose config validation: remote checks skipped
- Remote .env exists: remote checks skipped
- PostgreSQL volume exists: remote checks skipped
- Backup exists: remote checks skipped
- Backup freshness: remote checks skipped
- Health endpoint: remote checks skipped
- Disk space: remote checks skipped
- Docker permissions: remote checks skipped

## Recommendations

- Review WARNING items — deploy may proceed with caution.

## Check results

| Status | Check | Description | Duration |
|--------|-------|-------------|----------|
| PASS | Repo accessible | root=/Users/lukasz/projekty/ifg_standalone | 0 ms |
| PASS | Compose file exists | /Users/lukasz/projekty/ifg_standalone/docker/docker-compose.prod.yml | 0 ms |
| WARNING | .env exists | local .env.production not found — will verify on remote | 0 ms |
| PASS | Correct branch | production | 9 ms |
| WARNING | Git clean | uncommitted changes (88 line(s)) | 12 ms |
| WARNING | SSH works | remote checks skipped | 0 ms |
| WARNING | Docker available | remote checks skipped | 0 ms |
| WARNING | Docker Compose available | remote checks skipped | 0 ms |
| WARNING | Compose config valid | remote checks skipped | 0 ms |
| WARNING | Compose config validation | remote checks skipped | 0 ms |
| WARNING | Remote .env exists | remote checks skipped | 0 ms |
| WARNING | PostgreSQL volume exists | remote checks skipped | 0 ms |
| PASS | External volume correct | external pin to docker_postgres_data | 0 ms |
| WARNING | Backup exists | remote checks skipped | 0 ms |
| WARNING | Backup freshness | remote checks skipped | 0 ms |
| WARNING | Health endpoint | remote checks skipped | 0 ms |
| WARNING | Disk space | remote checks skipped | 0 ms |
| WARNING | Docker permissions | remote checks skipped | 0 ms |

## Details

### git.clean (WARNING)

- **sample:** `[' M app/api/deps.py', ' M app/domain/enums.py', ' M app/persistence/mappers/invoice_mapper.py', ' M app/persistence/models/invoice.py', ' M app/persistence/repositories/transmission_repository.py']`

---

*Read-only preflight — no environment mutations.*