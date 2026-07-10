# Guardian Preflight — PRECHECK_REPORT

**Generated:** 2026-07-07 22:08:31 UTC  
**Workflow:** `2026-07-07T220808Z_ifg_deploy_run`  
**Mode:** `LIVE`  
**Decision:** **NO_GO**  
**Duration:** 22538 ms  

## Summary

| PASS | WARNING | FAIL |
|------|---------|------|
| 11 | 5 | 2 |

## Blocking items (NO_GO)

- Compose file exists: missing: /private/var/folders/pm/1yzkzq_5699clb0xl8hnzxwr0000gn/T/pytest-of-lukasz/pytest-47/test_live_executes_with_mocked0/docker/docker-compose.prod.yml
- Backup exists: no backups found in /volume1/docker/ifg_v2/backups

## Warnings

- .env exists: local .env.production not found — will verify on remote
- Correct branch: not a git repository
- Git clean: git status unavailable
- External volume correct: compose file not local
- Backup freshness: no backup newer than 7 days

## Recommendations

- Resolve all FAIL items before LIVE deploy.
- Review PRECHECK_REPORT.md for details.

## Check results

| Status | Check | Description | Duration |
|--------|-------|-------------|----------|
| PASS | Repo accessible | root=/private/var/folders/pm/1yzkzq_5699clb0xl8hnzxwr0000gn/T/pytest-of-lukasz/pytest-47/test_live_executes_with_mocked0 | 0 ms |
| FAIL | Compose file exists | missing: /private/var/folders/pm/1yzkzq_5699clb0xl8hnzxwr0000gn/T/pytest-of-lukasz/pytest-47/test_live_executes_with_mocked0/docker/docker-compose.prod.yml | 0 ms |
| WARNING | .env exists | local .env.production not found — will verify on remote | 0 ms |
| WARNING | Correct branch | not a git repository | 10 ms |
| WARNING | Git clean | git status unavailable | 9 ms |
| PASS | SSH works | zdalny_admin@ds723 | 2469 ms |
| PASS | Docker available | 24.0.2 | 5584 ms |
| PASS | Docker Compose available | 2.20.1-6047-g6817716 | 2731 ms |
| PASS | Compose config valid | compose config OK | 2717 ms |
| PASS | Compose config validation | project=ifg, postgres volume=docker_postgres_data | 1139 ms |
| PASS | Remote .env exists | /volume1/docker/ifg_v2/ifg_standalone/.env.production | 738 ms |
| PASS | PostgreSQL volume exists | docker_postgres_data | 1477 ms |
| WARNING | External volume correct | compose file not local | 0 ms |
| FAIL | Backup exists | no backups found in /volume1/docker/ifg_v2/backups | 728 ms |
| WARNING | Backup freshness | no backup newer than 7 days | 1036 ms |
| PASS | Health endpoint | {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_t | 951 ms |
| PASS | Disk space | 70 GB free | 1028 ms |
| PASS | Docker permissions | docker ps OK | 1912 ms |

## Details

### compose.validation (PASS)

- **project:** `ifg`
- **volumes:** `['docker_ifg_prod', 'docker_postgres_data']`

---

*Read-only preflight — no environment mutations.*