# Guardian Preflight — PRECHECK_REPORT

**Generated:** 2026-07-20 18:49:42 UTC  

## Executive Summary

| Field | Value |
|-------|-------|
| **Status** | `READY` |
| **Decision** | `GO` |
| **Risk** | `UNKNOWN` |
| **Workflow** | `2026-07-20T184908Z_ifg_deploy_run` |
| **Duration** | 4696 ms |
| **Mode** | `LIVE` |

## Decision Matrix

| Component | Decision | Confidence | Reason | Trigger files | Impact |
|-----------|----------|------------|--------|---------------|--------|
| Repo accessible | PASS | HIGH | root=/Users/lukasz/projekty/ifg_standalone | — | repo.accessible |
| Compose file exists | PASS | HIGH | /Users/lukasz/projekty/ifg_standalone/docker/docker-compose.prod.yml | — | compose.file |
| .env exists | PASS | HIGH | /Users/lukasz/projekty/ifg_standalone/.env.production | — | env.file |
| Correct branch | PASS | HIGH | production | — | git.branch |
| Git clean | WARN | HIGH | Production build from dirty working tree (--allow-dirty-build). | — | git.clean |
| SSH works | PASS | HIGH | zdalny_admin@ds723 | — | ssh.connectivity |
| Docker available | PASS | HIGH | 24.0.2 | — | docker.available |
| Docker Compose available | PASS | HIGH | 2.20.1-6047-g6817716 | — | compose.available |
| Compose config valid | PASS | HIGH | compose config OK | — | compose.config |
| Compose config validation | PASS | HIGH | project=ifg, postgres volume=docker_postgres_data | — | compose.validation |
| Remote .env exists | PASS | HIGH | /volume1/docker/ifg_v2/ifg_standalone/.env.production | — | env.remote |
| PostgreSQL volume exists | PASS | HIGH | docker_postgres_data | — | volume.postgres |
| External volume correct | PASS | HIGH | external pin to docker_postgres_data | — | volume.external |
| Backup exists | PASS | HIGH | 2 backup artifact(s) found | — | backup.exists |
| Backup freshness | WARN | HIGH | no backup newer than 7 days | — | backup.freshness |
| Health endpoint | PASS | HIGH | {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_t | — | health.endpoint |
| Disk space | PASS | HIGH | 63 GB free | — | disk.space |
| Docker permissions | PASS | HIGH | docker ps OK | — | permissions.docker |

## Trigger Files

Brak.

## Local vs Remote

### LOCAL

| Status | Check | Name | Message |
|--------|-------|------|---------|
| `PASS` | `repo.accessible` | Repo accessible | root=/Users/lukasz/projekty/ifg_standalone |
| `PASS` | `compose.file` | Compose file exists | /Users/lukasz/projekty/ifg_standalone/docker/docker-compose.prod.yml |
| `PASS` | `env.file` | .env exists | /Users/lukasz/projekty/ifg_standalone/.env.production |
| `PASS` | `git.branch` | Correct branch | production |
| `WARN` | `git.clean` | Git clean | Production build from dirty working tree (--allow-dirty-build). |
| `PASS` | `ssh.connectivity` | SSH works | zdalny_admin@ds723 |
| `PASS` | `docker.available` | Docker available | 24.0.2 |
| `PASS` | `compose.available` | Docker Compose available | 2.20.1-6047-g6817716 |
| `PASS` | `compose.config` | Compose config valid | compose config OK |
| `PASS` | `compose.validation` | Compose config validation | project=ifg, postgres volume=docker_postgres_data |
| `PASS` | `env.remote` | Remote .env exists | /volume1/docker/ifg_v2/ifg_standalone/.env.production |
| `PASS` | `volume.postgres` | PostgreSQL volume exists | docker_postgres_data |
| `PASS` | `volume.external` | External volume correct | external pin to docker_postgres_data |
| `PASS` | `backup.exists` | Backup exists | 2 backup artifact(s) found |
| `WARN` | `backup.freshness` | Backup freshness | no backup newer than 7 days |
| `PASS` | `health.endpoint` | Health endpoint | {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_t |
| `PASS` | `disk.space` | Disk space | 63 GB free |
| `PASS` | `permissions.docker` | Docker permissions | docker ps OK |

### REMOTE

Brak checków zdalnych.

## Impact

Brak wpływu na komponenty.

## Build Actions

| Action | Decision | Reason | Command |
|--------|----------|--------|---------|
| docker build api | NO | not applicable | `—` |
| docker build worker | NO | not applicable | `—` |
| npm build | NO | not applicable | `—` |
| alembic | NO | not applicable | `—` |
| compose up | NO | not applicable | `—` |
| health | NO | not applicable | `—` |
| logs | NO | not applicable | `—` |

## Operator Actions

- Review WARNING items — deploy may proceed with caution.
- Warning: Git clean: Production build from dirty working tree (--allow-dirty-build).
- Warning: Backup freshness: no backup newer than 7 days


## Preflight Summary

| PASS | WARNING | FAIL |
|------|---------|------|
| 16 | 2 | 0 |

*Read-only preflight — no environment mutations.*

## Wygenerowane raporty

Brak.

## Wygenerowane handoffy

Brak.


## Decyzje dla ChatGPT

Brak.
