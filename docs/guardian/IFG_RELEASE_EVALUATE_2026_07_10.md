# IFG Guardian — Release Engine Evaluation

**Generated:** 2026-07-10 22:05:24 UTC  
**Decision:** `PRODUCTION_BLOCKED`  
**Deployment Profile:** `single_production`  
**Policy Engine:** final decision authority  
**Release Score:** `88/100`  
**Deployment Recommendation:** **Deploy zablokowany**  
**Backup Required:** `True`  
**Staging Required:** `False`  
**Production Blocked:** `True`  
**Workflow ID:** `2026-07-10T220516Z_ifg_release_evaluate`  
**Duration:** 8244 ms  
## Executive Summary

| Dimension | Status |
|---|---|
| **Project status** | `BLOCKED` |
| **Environment status** | `WARNING` |
| **Policy status** | `BLOCK` |
| **Deployment recommendation** | `Deploy zablokowany` |

Operator note: blockers in **BLOCKERS** concern the project or policy. Items in **LOCAL ENVIRONMENT** reflect this machine's interpreter/tools — they do not block release by themselves.

## Decision Rationale

Policy decision based on doctor status `BLOCKED`, facts from checks and advisory release score `88`.

## BLOCKERS

- [backend] backend changes: 7 backend/alembic change(s)
- [backend] build required: rebuild api/worker required before deploy
- Policy rule triggered: dirty_working_tree_blocks_production
- Production deployment blocked. Working tree contains uncommitted changes.

## WARNINGS

- [environment] git status: working tree dirty
- [repository] dirty repo: working tree has tracked/untracked changes
- [repository] line endings: 8 file(s) with unknown line endings
- [frontend] frontend-react/src: uncommitted changes in frontend-react/src
- [alembic] current: Traceback (most recent call last):
  File "/opt/homebrew/bin/alembic", line 6, in <module>
    sys.exit(main())
             ~~~~^^
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/config.py", line 1047, in main
    CommandLine(prog=prog).main(argv=argv)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/config.py", line 1037, in main
    self.run_cmd(cfg, options)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/config.py", line 971, in run_cmd
    fn(
    ~~^
        config,
        ^^^^^^^
        *[getattr(options, k, None) for k in positional],
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
        **{k: getattr(options, k, None) for k in kwarg},
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/command.py", line 729, in current
    script.run_env()
    ~~~~~~~~~~~~~~^^
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/script/base.py", line 556, in run_env
    util.load_python_file(self.dir, "env.py")
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/util/pyfiles.py", line 116, in load_python_file
    module = load_module_py(module_id, path)
  File "/opt/homebrew/lib/python3.14/site-packages/alembic/util/pyfiles.py", line 136, in load_module_py
    spec.loader.exec_module(module)  # type: ignore
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "<frozen importlib._bootstrap_external>", line 759, in exec_module
  File "<frozen importlib._bootstrap>", line 491, in _call_with_frames_removed
  File "/Users/lukasz/projekty/ifg_standalone/alembic/env.py", line 68, in <module>
    run_migrations_online()
    ~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/lukasz/projekty/ifg_standalone/alembic/env.py", line 45, in run_migrations_online
    configuration["sqlalchemy.url"] = get_database_url()
                                      ~~~~~~~~~~~~~~~~^^
  File "/Users/lukasz/projekty/ifg_standalone/alembic/env.py", line 25, in get_database_url
    raise RuntimeError("Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic.")
RuntimeError: Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic.
- Policy rule triggered: critical_db_change_requires_verified_backup
- Policy rule triggered: untracked_files_warn
- Policy rule triggered: doctor_fail_warn_single_production

## LOCAL ENVIRONMENT

- None

## INFORMATION

- [environment] branch: on production (f5215b0)
- [environment] ahead/behind: synced with origin/production
- [environment] python: Python 3.14.5
- [environment] node: v25.9.0
- [environment] npm: 11.12.1
- [repository] repo audit: overall risk HIGH, 217 classified file(s)
- [repository] ignored files: no tracked ignore conflicts
- [frontend] npm run build: ✅ [lokalnie] dist nowszy niż niezcommitowane zmiany src
- [frontend] dist freshness: ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src
- [docker] compose config: compose file valid
- [docker] containers: api/worker/db running
- [docker] images: compose ps returned 3 service(s)
- [database] postgres: postgres service declared in compose
- [database] connection: psycopg available locally
- [database] backup policy: backup documented in docs/migracja_mac_mini.md
- [alembic] pending migration: schema at head
- [configuration] .env.production.template: template present
- [configuration] .env.production: .env.production present locally
- [configuration] required variables: required keys documented in .env.example
- [health] /health: {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}}
- Policy rule triggered: backend_change_requires_api_worker_rebuild
- Zacommituj zmiany lub użyj jawnego override: guardian ifg deploy run --allow-dirty-build --yes
- Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- Wymagany rebuild obrazów api/worker przed produkcją.
- Zweryfikuj untracked pliki przed produkcją: .state/, Architecture/, docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md, docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md, docs/FV_NUMBERING_RENUMBERING_BUG.md, docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md, docs/FV_WZ_AUTO_SYNC_ANALYSIS.md, docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md


## Release Score Breakdown

| Component | Weight | Score | Rationale |
|---|---:|---:|---|
| repo | 15 | 60 | repo+audit |
| tests | 15 | 100 | pytest collect |
| build | 15 | 80 | frontend build checks |
| migrations | 12 | 80 | alembic checks |
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

- `dirty_working_tree_blocks_production`
- `critical_db_change_requires_verified_backup`
- `backend_change_requires_api_worker_rebuild`
- `untracked_files_warn`
- `doctor_fail_warn_single_production`

## Required Actions Before Production

- Zacommituj zmiany lub użyj jawnego override: guardian ifg deploy run --allow-dirty-build --yes
- Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- Wymagany rebuild obrazów api/worker przed produkcją.
- Zweryfikuj untracked pliki przed produkcją: .state/, Architecture/, docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md, docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md, docs/FV_NUMBERING_RENUMBERING_BUG.md, docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md, docs/FV_WZ_AUTO_SYNC_ANALYSIS.md, docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md

## Next Step

Usuń blockery polityk i uruchom ponownie guardian release evaluate.


## Decyzje dla ChatGPT

Brak.
