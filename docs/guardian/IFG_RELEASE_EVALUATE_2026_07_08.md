# IFG Guardian — Release Engine Evaluation

**Generated:** 2026-07-08 22:32:30 UTC  
**Decision:** `READY_WITH_OVERRIDE`  
**Deployment Profile:** `single_production`  
**Policy Engine:** final decision authority  
**Release Score:** `61/100`  
**Deployment Recommendation:** **Deploy możliwy z jawnym override dirty tree**  
**Backup Required:** `True`  
**Staging Required:** `False`  
**Production Blocked:** `False`  
**Workflow ID:** `2026-07-08T223218Z_ifg_release_evaluate`  
**Duration:** 11812 ms  
## Executive Summary

| Dimension | Status |
|---|---|
| **Project status** | `WARNING` |
| **Environment status** | `WARNING` |
| **Policy status** | `WARN` |
| **Deployment recommendation** | `Deploy możliwy z jawnym override dirty tree` |

Operator note: blockers in **BLOCKERS** concern the project or policy. Items in **LOCAL ENVIRONMENT** reflect this machine's interpreter/tools — they do not block release by themselves.

## Decision Rationale

Policy decision based on doctor status `READY_WITH_WARNINGS`, facts from checks and advisory release score `86`.

## BLOCKERS

- None

## WARNINGS

- [environment] git status: working tree dirty
- [repository] dirty repo: working tree has tracked/untracked changes
- [repository] line endings: 8 file(s) with unknown line endings
- [frontend] frontend-react/src: uncommitted changes in frontend-react/src
- [backend] backend changes: 5 backend/alembic change(s)
- [backend] build required: review backend changes
- Policy rule triggered: dirty_tree_build_with_override
- Policy rule triggered: critical_db_change_requires_verified_backup
- Policy rule triggered: untracked_files_warn

## LOCAL ENVIRONMENT

- [alembic] current: [Errno 2] No such file or directory: 'alembic'
- [alembic] head: [Errno 2] No such file or directory: 'alembic'

## INFORMATION

- [environment] branch: on production (f5215b0)
- [environment] ahead/behind: synced with origin/production
- [environment] python: Python 3.13.13
- [environment] node: v25.9.0
- [environment] npm: 11.12.1
- [repository] repo audit: overall risk HIGH, 167 classified file(s)
- [repository] ignored files: no tracked ignore conflicts
- [frontend] npm run build: ✅ [lokalnie] dist nowszy niż niezcommitowane zmiany src
- [frontend] dist freshness: ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src
- [docker] compose config: compose file valid
- [docker] containers: api/worker/db running
- [docker] images: compose ps returned 3 service(s)
- [database] postgres: postgres service declared in compose
- [database] connection: psycopg available locally
- [database] backup policy: backup documented in docs/migracja_mac_mini.md
- [configuration] .env.production.template: template present
- [configuration] .env.production: .env.production present locally
- [configuration] required variables: required keys documented in .env.example
- [health] /health: {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
- Policy rule triggered: backend_change_requires_api_worker_rebuild
- Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree).
- Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- Wymagany rebuild obrazów api/worker przed produkcją.
- Zweryfikuj untracked pliki przed produkcją: docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md, docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md, docs/FV_NUMBERING_RENUMBERING_BUG.md, docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md, docs/FV_WZ_AUTO_SYNC_ANALYSIS.md, docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md, docs/IFG_PENDING_CHANGES_AUDIT.md, docs/KK_CREATION_FIX.md


## Release Score Breakdown

| Component | Weight | Score | Rationale |
|---|---:|---:|---|
| repo | 15 | 60 | repo+audit |
| tests | 15 | 100 | pytest collect |
| build | 15 | 80 | frontend build checks |
| migrations | 12 | 60 | alembic checks |
| docker | 10 | 100 | docker checks |
| configuration | 10 | 100 | env/config checks |
| rollback_readiness | 13 | 100 | backup policy + recovery readiness |
| documentation | 10 | 100 | ops docs and templates |

## Change Impact

| Area | Impact |
|---|---|
| Backend | MEDIUM |
| Frontend | MEDIUM |
| Mobile | LOW |
| Docker | LOW |
| DB | LOW |
| Alembic | LOW |
| Worker | LOW |
| KSeF | HIGH |
| Warehouse | HIGH |
| Payments | HIGH |

## Policy Rules Triggered

- `dirty_tree_build_with_override`
- `critical_db_change_requires_verified_backup`
- `backend_change_requires_api_worker_rebuild`
- `untracked_files_warn`

## Required Actions Before Production

- Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree).
- Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- Wymagany rebuild obrazów api/worker przed produkcją.
- Zweryfikuj untracked pliki przed produkcją: docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md, docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md, docs/FV_NUMBERING_RENUMBERING_BUG.md, docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md, docs/FV_WZ_AUTO_SYNC_ANALYSIS.md, docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md, docs/IFG_PENDING_CHANGES_AUDIT.md, docs/KK_CREATION_FIX.md

## Next Step

Uruchom deploy z --allow-dirty-build --yes po świadomej akceptacji ryzyka.
