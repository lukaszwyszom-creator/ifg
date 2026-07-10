# IFG Guardian — Release Engine Evaluation

**Generated:** 2026-07-07 09:14:18 UTC  
**Decision:** `PRODUCTION_BLOCKED`  
**Deployment Profile:** `single_production`  
**Policy Engine:** final decision authority  
**Release Score:** `76/100`  
**Deployment Recommendation:** **Deploy zablokowany**  
**Backup Required:** `True`  
**Staging Required:** `False`  
**Production Blocked:** `True`  
**Workflow ID:** `2026-07-07T091407Z_ifg_release_evaluate`  
**Duration:** 0 ms  

## Decision Rationale

Policy decision based on doctor status `BLOCKED`, facts from checks and advisory release score `76`.

## Blockers

- Test discovery failed.

## Warnings

- [environment] git status: working tree dirty
- [repository] dirty repo: working tree has tracked/untracked changes
- [repository] line endings: 8 file(s) with unknown line endings
- [frontend] frontend-react/src: uncommitted changes in frontend-react/src
- [backend] backend changes: 18 backend/alembic change(s)
- [backend] build required: rebuild api/worker required before deploy
- [database] connection: psycopg check: Traceback (most recent call last):
  File "<string>", line 1, in <module>
    import psycopg; print('ok')
    ^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'psycopg'
- [alembic] current: [Errno 2] No such file or directory: 'alembic'
- [alembic] head: [Errno 2] No such file or directory: 'alembic'
- Test discovery warning: /opt/homebrew/opt/python@3.14/bin/python3.14: No module named pytest

## Positive Signals

- [environment] branch: on production (8427144)
- [environment] ahead/behind: synced with origin/production
- [environment] python: Python 3.14.5
- [environment] node: v25.9.0
- [environment] npm: 11.12.1
- [repository] repo audit: overall risk HIGH, 142 classified file(s)
- [repository] ignored files: no tracked ignore conflicts
- [frontend] npm run build: ✅ [lokalnie] dist nowszy niż niezcommitowane zmiany src
- [frontend] dist freshness: ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src
- [docker] compose config: compose file valid
- [docker] containers: api/worker/db running
- [docker] images: compose ps returned 3 service(s)
- Deploy check: production alignment confirmed.

## Release Score Breakdown

| Component | Weight | Score | Rationale |
|---|---:|---:|---|
| repo | 15 | 60 | repo+audit |
| tests | 15 | 35 | pytest collect |
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
| DB | HIGH |
| Alembic | HIGH |
| Worker | HIGH |
| KSeF | HIGH |
| Warehouse | HIGH |
| Payments | HIGH |

## Policy Rules Triggered

- `migration_change_requires_controlled_deploy`
- `critical_db_change_requires_verified_backup`
- `tests_must_pass`
- `backend_change_requires_api_worker_rebuild`
- `untracked_files_warn`
- `doctor_fail_warn_single_production`

## Required Actions Before Production

- Wykonaj migrację DB w kontrolowanym deploy pipeline.
- Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- Napraw test discovery i uruchom ponownie evaluate.
- Wymagany rebuild obrazów api/worker przed produkcją.
- Zweryfikuj untracked pliki przed produkcją: alembic/versions/a9b1c2d3e4f5_ksef_monitor_transmissions_unified.py, app/services/ksef_transmission_journal_service.py, docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md, docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md, docs/FV_NUMBERING_RENUMBERING_BUG.md, docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md, docs/FV_WZ_AUTO_SYNC_ANALYSIS.md, docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md

## Next Step

Usuń blockery polityk i uruchom ponownie guardian release evaluate.
