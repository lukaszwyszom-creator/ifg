# IFG Guardian — Release Engine Evaluation

**Generated:** 2026-07-07 07:55:23 UTC  
**Decision:** `PRODUCTION_BLOCKED`  
**Policy Engine:** final decision authority  
**Release Score:** `81/100`  
**Deployment Recommendation:** **Deploy zablokowany**  
**Backup Required:** `True`  
**Staging Required:** `True`  
**Production Blocked:** `True`  
**Workflow ID:** `2026-07-07T075511Z_ifg_release_evaluate`  
**Duration:** 0 ms  

## Decision Rationale

Policy decision based on doctor status `BLOCKED`, facts from checks and advisory release score `81`.

## Blockers

- [backend] backend changes: 18 backend/alembic change(s)
- [backend] build required: rebuild api/worker required before deploy
- [docker] compose config: env file /Users/lukasz/projekty/ifg_standalone/.env.production not found: stat /Users/lukasz/projekty/ifg_standalone/.env.production: no such file or directory

## Warnings

- [environment] git status: working tree dirty
- [repository] dirty repo: working tree has tracked/untracked changes
- [repository] line endings: 8 file(s) with unknown line endings
- [frontend] frontend-react/src: uncommitted changes in frontend-react/src
- [alembic] current: Traceback (most recent call last):
  File "/Users/lukasz/projekty/ifg_standalone/.venv/bin/alembic", line 6, in <module>
    sys.exit(main())
             ~~~~^^
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/config.py", line 1047, in main
    CommandLine(prog=prog).main(argv=argv)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/config.py", line 1037, in main
    self.run_cmd(cfg, options)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/config.py", line 971, in run_cmd
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
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/command.py", line 722, in current
    script.run_env()
    ~~~~~~~~~~~~~~^^
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/script/base.py", line 545, in run_env
    util.load_python_file(self.dir, "env.py")
    ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/util/pyfiles.py", line 116, in load_python_file
    module = load_module_py(module_id, path)
  File "/Users/lukasz/projekty/ifg_standalone/.venv/lib/python3.13/site-packages/alembic/util/pyfiles.py", line 136, in load_module_py
    spec.loader.exec_module(module)  # type: ignore
    ~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "<frozen importlib._bootstrap_external>", line 1023, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "/Users/lukasz/projekty/ifg_standalone/alembic/env.py", line 68, in <module>
    run_migrations_online()
    ~~~~~~~~~~~~~~~~~~~~~^^
  File "/Users/lukasz/projekty/ifg_standalone/alembic/env.py", line 45, in run_migrations_online
    configuration["sqlalchemy.url"] = get_database_url()
                                      ~~~~~~~~~~~~~~~~^^
  File "/Users/lukasz/projekty/ifg_standalone/alembic/env.py", line 25, in get_database_url
    raise RuntimeError("Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic.")
RuntimeError: Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic.
- [configuration] .env.production: .env.production not found locally (may exist only on DS723+)

## Positive Signals

- [environment] branch: on production (8427144)
- [environment] ahead/behind: synced with origin/production
- [environment] python: Python 3.13.13
- [environment] node: v25.9.0
- [environment] npm: 11.12.1
- [repository] repo audit: overall risk HIGH, 122 classified file(s)
- [repository] ignored files: no tracked ignore conflicts
- [frontend] npm run build: ✅ [lokalnie] dist nowszy niż niezcommitowane zmiany src
- [frontend] dist freshness: ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src
- [docker] containers: api/worker/db running
- [docker] images: compose ps returned 3 service(s)
- [database] postgres: postgres service declared in compose
- Deploy check: production alignment confirmed.
- Test discovery passed (tests/unit).

## Release Score Breakdown

| Component | Weight | Score | Rationale |
|---|---:|---:|---|
| repo | 15 | 60 | repo+audit |
| tests | 15 | 100 | pytest collect |
| build | 15 | 80 | frontend build checks |
| migrations | 12 | 80 | alembic checks |
| docker | 10 | 55 | docker checks |
| configuration | 10 | 80 | env/config checks |
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

- `alembic_changes_require_staging`
- `critical_table_migration_requires_backup`
- `backend_change_requires_api_worker_rebuild`
- `suspicious_untracked_files_block`
- `doctor_fail_requires_staging`

## Required Actions Before Production

- Wykonaj backup DB przed produkcją (krytyczne tabele migracji: invoices, transmissions).
- Wymagany rebuild obrazów api/worker przed produkcją.
- Usuń/obsłuż podejrzane untracked pliki: .env.production.migration-test

## Next Step

Usuń blockery polityk i uruchom ponownie guardian release evaluate.
