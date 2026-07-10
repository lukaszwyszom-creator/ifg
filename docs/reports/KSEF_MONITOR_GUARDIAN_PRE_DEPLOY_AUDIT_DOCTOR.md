# IFG Guardian — IFG Doctor

**Generated:** 2026-07-07 07:28:37 UTC  
**Overall status:** `BLOCKED`  
**Question:** Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?  
**Workflow ID:** `2026-07-07T072835Z_ifg_doctor`  
**Duration:** 0 ms  

## Checks

### Environment

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | branch | on production (8427144) |
| `WARN` | git status | working tree dirty |
| `PASS` | ahead/behind | synced with origin/production |
| `PASS` | python | Python 3.13.13 |
| `PASS` | node | v25.9.0 |
| `PASS` | npm | 11.12.1 |

### Repository

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | repo audit | overall risk HIGH, 110 classified file(s) |
| `WARN` | dirty repo | working tree has tracked/untracked changes |
| `WARN` | line endings | 8 file(s) with unknown line endings |
| `PASS` | ignored files | no tracked ignore conflicts |

### Frontend

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | frontend-react/src | uncommitted changes in frontend-react/src |
| `PASS` | npm run build | ✅ [lokalnie] dist nowszy niż niezcommitowane zmiany src |
| `PASS` | dist freshness | ✅ [lokalnie] frontend-react/dist aktualny względem ostatniego commita src |

### Backend

| Status | Check | Message |
|--------|-------|---------|
| `FAIL` | backend changes | 18 backend/alembic change(s) |
| `FAIL` | build required | rebuild api/worker required before deploy |

### Docker

| Status | Check | Message |
|--------|-------|---------|
| `FAIL` | compose config | env file /Users/lukasz/projekty/ifg_standalone/.env.production not found: stat /Users/lukasz/projekty/ifg_standalone/.env.production: no such file or directory |
| `WARN` | remote containers | skipped in dry-run (would inspect DS723+ via SSH) |

### Database

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | postgres | postgres service declared in compose |
| `WARN` | connection | skipped in dry-run |
| `PASS` | backup policy | backup documented in docs/migracja_mac_mini.md |

### Alembic

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | current | Traceback (most recent call last):
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
RuntimeError: Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic. |
| `PASS` | pending migration | schema at head |

### Configuration

| Status | Check | Message |
|--------|-------|---------|
| `PASS` | .env.production.template | template present |
| `WARN` | .env.production | .env.production not found locally (may exist only on DS723+) |
| `PASS` | required variables | required keys documented in .env.example |

### Health

| Status | Check | Message |
|--------|-------|---------|
| `WARN` | /health | skipped in dry-run (would curl DS723+ /health) |

## Summary

- **overall_status:** BLOCKED
- **checks_total:** 26
- **pass:** 14
- **warn:** 9
- **fail:** 3
- **critical:** 0
