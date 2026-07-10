# IFG Guardian — IFG Doctor

**Generated:** 2026-07-10 22:36:14 UTC  
**Overall status:** `READY_WITH_WARNINGS`  
**Question:** Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?  
**Workflow ID:** `2026-07-10T223612Z_ifg_doctor`  
**Duration:** 0 ms  

## Checks

### Environment

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | branch | on production (42e76dc) |
| `PASS` | git status | working tree clean |
| `WARN` | ahead/behind | ahead=6, behind=0 vs origin/production |
| `PASS` | python | Python 3.14.5 |
| `PASS` | node | v25.9.0 |
| `PASS` | npm | 11.12.1 |

### Repository

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | repo audit | overall risk MEDIUM, 0 classified file(s) |
| `PASS` | dirty repo | working tree clean (audit) |
| `PASS` | line endings | no line-ending issues detected |
| `PASS` | ignored files | no tracked ignore conflicts |

### Frontend

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | frontend-react/src | no uncommitted src changes |
| `PASS` | npm run build | ✅ [lokalnie] brak niezcommitowanych zmian frontend-react/src |
| `PASS` | dist freshness | ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src |

### Backend

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | backend changes | no pending backend/alembic changes |

### Docker

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | compose config | compose file valid |
| `PASS` | containers | api/worker/db running |
| `PASS` | images | compose ps returned 3 service(s) |

### Database

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | postgres | postgres service declared in compose |
| `PASS` | connection | psycopg available locally |
| `PASS` | backup policy | backup documented in docs/migracja_mac_mini.md |

### Alembic

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | current | Traceback (most recent call last):
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
RuntimeError: Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic. |
| `PASS` | pending migration | schema at head |

### Configuration

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | .env.production.template | template present |
| `PASS` | .env.production | .env.production present locally |
| `PASS` | required variables | required keys documented in .env.example |

### Health

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | /health | {"status":"ok","app_name":"IFG Faktury","version":"1.0.0","environment":"production","db_timezone":"Europe/Warsaw","db_timezone_utc":false,"regon":{"environment":"production","configured":true}} |

## Summary

- **overall_status:** READY_WITH_WARNINGS
- **checks_total:** 26
- **pass:** 24
- **warn:** 2
- **fail:** 0
- **critical:** 0

## Decyzje dla ChatGPT

Brak.
