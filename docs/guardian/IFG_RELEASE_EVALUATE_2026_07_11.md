# IFG Guardian — Release Engine Evaluation

**Generated:** 2026-07-11 21:25:42 UTC  
**Decision:** `READY_WITH_OVERRIDE`  
**Deployment Profile:** `single_production`  
**Policy Engine:** final decision authority  
**Release Score:** `62/100`  
**Deployment Recommendation:** **Deploy możliwy z jawnym override dirty tree**  
**Backup Required:** `False`  
**Staging Required:** `False`  
**Production Blocked:** `False`  
**Workflow ID:** `2026-07-11T212535Z_ifg_release_evaluate`  
**Duration:** 6626 ms  
## Executive Summary

| Dimension | Status |
|---|---|
| **Project status** | `BLOCKED` |
| **Environment status** | `WARNING` |
| **Policy status** | `WARN` |
| **Deployment recommendation** | `Deploy możliwy z jawnym override dirty tree` |

Operator note: blockers in **BLOCKERS** concern the project or policy. Items in **LOCAL ENVIRONMENT** reflect this machine's interpreter/tools — they do not block release by themselves.

## Decision Rationale

Policy decision based on doctor status `BLOCKED`, facts from checks and advisory release score `87`.

## BLOCKERS

- [frontend] dist freshness: ❌ [lokalnie] Frontend dist wymaga przebudowy (npm run build). (dist starszy niż commit 4a71c14 w frontend-react/src)

## WARNINGS

- [environment] git status: working tree dirty
- [repository] dirty repo: working tree has tracked/untracked changes
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
- Policy rule triggered: dirty_tree_build_with_override
- Policy rule triggered: doctor_fail_warn_single_production
- Deploy check returned exit code 1

## LOCAL ENVIRONMENT

- None

## INFORMATION

- [environment] branch: on production (4a71c14)
- [environment] ahead/behind: synced with origin/production
- [environment] python: Python 3.14.5
- [environment] node: v25.9.0
- [environment] npm: 11.12.1
- [repository] repo audit: overall risk MEDIUM, 15 classified file(s)
- [repository] line endings: no line-ending issues detected
- [repository] ignored files: no tracked ignore conflicts
- [frontend] frontend-react/src: no uncommitted src changes
- [frontend] npm run build: ✅ [lokalnie] brak niezcommitowanych zmian frontend-react/src
- [backend] backend changes: no pending backend/alembic changes
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
- Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree).


## Release Score Breakdown

| Component | Weight | Score | Rationale |
|---|---:|---:|---|
| repo | 15 | 80 | repo+audit |
| tests | 15 | 100 | pytest collect |
| build | 15 | 55 | frontend build checks |
| migrations | 12 | 80 | alembic checks |
| docker | 10 | 100 | docker checks |
| configuration | 10 | 100 | env/config checks |
| rollback_readiness | 13 | 100 | backup policy + recovery readiness |
| documentation | 10 | 100 | ops docs and templates |

## Change Impact

| Area | Impact |
|---|---|
| Backend | LOW |
| Frontend | LOW |
| Mobile | LOW |
| Docker | LOW |
| DB | LOW |
| Alembic | LOW |
| Worker | LOW |
| KSeF | LOW |
| Warehouse | LOW |
| Payments | LOW |

## Policy Rules Triggered

- `dirty_tree_build_with_override`
- `doctor_fail_warn_single_production`

## Required Actions Before Production

- Potwierdź świadomy deploy z flagą --allow-dirty-build (build z lokalnego dirty tree).

## Next Step

Uruchom deploy z --allow-dirty-build --yes po świadomej akceptacji ryzyka.


## Decyzje dla ChatGPT

Brak.
