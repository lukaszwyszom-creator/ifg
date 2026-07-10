# Guardian Preflight — PRECHECK_REPORT

**Generated:** 2026-07-08 22:32:52 UTC  
**Workflow:** `2026-07-08T223207Z_ifg_deploy_run`  
**Mode:** `LIVE`  
**Decision:** **GO**  
**Duration:** 5285 ms  

## Summary

| PASS | WARNING | FAIL |
|------|---------|------|
| 17 | 1 | 0 |

## Warnings

- Git clean: Production build from dirty working tree (--allow-dirty-build).

## Recommendations

- Review WARNING items — deploy may proceed with caution.

## Check results

| Status | Check | Description | Duration |
|--------|-------|-------------|----------|
| PASS | Repo accessible | root=/Users/lukasz/projekty/ifg_standalone | 0 ms |
| PASS | Compose file exists | /Users/lukasz/projekty/ifg_standalone/docker/docker-compose.prod.yml | 0 ms |
| PASS | .env exists | /Users/lukasz/projekty/ifg_standalone/.env.production | 0 ms |
| PASS | Correct branch | production | 23 ms |
| WARNING | Git clean | Production build from dirty working tree (--allow-dirty-build). | 23 ms |
| PASS | SSH works | zdalny_admin@ds723 | 324 ms |
| PASS | Docker available | 24.0.2 | 644 ms |
| PASS | Docker Compose available | 2.20.1-6047-g6817716 | 439 ms |
| PASS | Compose config valid | compose config OK | 408 ms |
| PASS | Compose config validation | project=ifg, postgres volume=docker_postgres_data | 464 ms |
| PASS | Remote .env exists | /volume1/docker/ifg_v2/ifg_standalone/.env.production | 342 ms |
| PASS | PostgreSQL volume exists | docker_postgres_data | 400 ms |
| PASS | External volume correct | external pin to docker_postgres_data | 0 ms |
| PASS | Backup exists | 2 backup artifact(s) found | 367 ms |
| PASS | Backup freshness | backup within 7 days | 343 ms |
| PASS | Health endpoint | {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_t | 469 ms |
| PASS | Disk space | 70 GB free | 668 ms |
| PASS | Docker permissions | docker ps OK | 364 ms |

## Details

### git.clean (WARNING)

- **sample:** `[' M app/persistence/mappers/invoice_mapper.py', ' M app/persistence/models/invoice.py', ' M app/persistence/repositories/transmission_repository.py', ' M app/services/invoice_number_policy.py', ' M app/services/payment_service.py']`
- **allow_dirty_build:** `True`

### compose.validation (PASS)

- **project:** `ifg`
- **volumes:** `['docker_ifg_prod', 'docker_postgres_data']`

### backup.exists (PASS)

- **files:** `['/volume1/docker/ifg_v2/backups/ksef_backend_20260708_230219.dump', '/volume1/docker/ifg_v2/backups/ksef_backend_20260708_230227.dump']`

### backup.freshness (PASS)

- **path:** `/volume1/docker/ifg_v2/backups/ksef_backend_20260708_230219.dump`

---

*Read-only preflight — no environment mutations.*