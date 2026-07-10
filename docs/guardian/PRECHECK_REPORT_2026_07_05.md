# Guardian Preflight — PRECHECK_REPORT

**Generated:** 2026-07-05 22:21:42 UTC  
**Workflow:** `2026-07-05T222137Z_ifg_deploy_run`  
**Mode:** `DRY_RUN`  
**Decision:** **GO**  
**Duration:** 4425 ms  

## Summary

| PASS | WARNING | FAIL |
|------|---------|------|
| 12 | 6 | 0 |

## Warnings

- .env exists: local .env.production not found — will verify on remote
- Git clean: uncommitted changes (50 line(s))
- External volume correct: no external pin in compose (pre-migration state acceptable)
- Backup exists: no backups found in /volume1/docker/ifg_v2/backups
- Backup freshness: no backup newer than 7 days
- Health endpoint: health unreachable (stack may be stopped)

## Recommendations

- Review WARNING items — deploy may proceed with caution.

## Check results

| Status | Check | Description | Duration |
|--------|-------|-------------|----------|
| PASS | Repo accessible | root=/Users/lukasz/projekty/ifg_standalone | 0 ms |
| PASS | Compose file exists | /Users/lukasz/projekty/ifg_standalone/docker/docker-compose.prod.yml | 0 ms |
| WARNING | .env exists | local .env.production not found — will verify on remote | 0 ms |
| PASS | Correct branch | production | 7 ms |
| WARNING | Git clean | uncommitted changes (50 line(s)) | 11 ms |
| PASS | SSH works | zdalny_admin@ds723 | 330 ms |
| PASS | Docker available | 24.0.2 | 410 ms |
| PASS | Docker Compose available | 2.20.1-6047-g6817716 | 391 ms |
| PASS | Compose config valid | compose config OK | 406 ms |
| PASS | Compose config validation | project=docker, postgres volume=docker_postgres_data | 402 ms |
| PASS | Remote .env exists | /volume1/docker/ifg_v2/ifg_standalone/.env.production | 331 ms |
| PASS | PostgreSQL volume exists | docker_postgres_data | 356 ms |
| WARNING | External volume correct | no external pin in compose (pre-migration state acceptable) | 1 ms |
| WARNING | Backup exists | no backups found in /volume1/docker/ifg_v2/backups | 347 ms |
| WARNING | Backup freshness | no backup newer than 7 days | 351 ms |
| WARNING | Health endpoint | health unreachable (stack may be stopped) | 361 ms |
| PASS | Disk space | 71 GB free | 357 ms |
| PASS | Docker permissions | docker ps OK | 357 ms |

## Details

### git.clean (WARNING)

- **sample:** `[' M app/api/deps.py', ' M app/domain/enums.py', ' M app/persistence/mappers/invoice_mapper.py', ' M app/persistence/models/invoice.py', ' M app/persistence/repositories/transmission_repository.py']`

### compose.validation (PASS)

- **project:** `docker`
- **volumes:** `['docker_ifg_prod', 'docker_postgres_data']`

---

*Read-only preflight — no environment mutations.*