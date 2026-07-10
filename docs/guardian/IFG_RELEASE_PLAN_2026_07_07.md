# IFG Guardian — Release Plan

**Generated:** 2026-07-07 20:48:22 UTC  
**Question:** Co dokładnie zostanie wykonane, jeżeli uruchomię deploy?  
**Deployment risk:** `MEDIUM`  
**Doctor status:** `READY_WITH_WARNINGS`  
**Workflow ID:** `2026-07-07T204817Z_ifg_release_plan`  
**Duration:** 0 ms  

## Dependencies

- `ifg.doctor` → SUCCESS (2026-07-07T204817Z_ifg_doctor)

## Repository

- Branch: `production`
- HEAD: `b7ad331` (`b7ad331f8a0dea7e729bebc8c1ebcaf0f09003e0`)
- Dirty: True
- Ahead/behind: 0/0

## Build decisions

| Decision | Required | Confidence | Reason |
|----------|----------|------------|--------|
| Frontend Build | yes | MEDIUM | frontend-react/src changes detected |
| Backend Build | yes | HIGH | app/ or alembic/ changes detected |
| Worker Build | yes | HIGH | worker shares api image rebuild when backend changes |
| Compose Restart | yes | HIGH | services must restart after image/build/migration changes |
| Migration Required | no | HIGH | schema at head |
| Static Files | yes | MEDIUM | frontend dist must be rebuilt and synced to DS723+ |

## Artifacts

- **Git SHA:** `b7ad331f8a0dea7e729bebc8c1ebcaf0f09003e0` — target commit for deploy
- **Frontend bundle:** `25e1bf528f64` — planned dist/assets fingerprint
- **Docker image API:** `ifg-api:b7ad331` — planned tag — not built in plan mode
- **Docker image Worker:** `ifg-worker:b7ad331` — planned tag — not built in plan mode
- **Alembic revision:** `Traceback (most recent call last):
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
RuntimeError: Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic.` — target schema revision
- **Compose file:** `docker/docker-compose.prod.yml` — production compose definition
- **Compose service:** `api` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `worker` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `db` — service managed by docker/docker-compose.prod.yml

## Execution plan

1. **git pull** (required) — Synchronize DS723+ repository with origin/production
2. **frontend build** (required) — cd frontend-react && npm run build — frontend-react/src changes detected
3. **docker build api** (required) — Rebuild API image — app/ or alembic/ changes detected
4. **docker build worker** (required) — Rebuild worker image — worker shares api image rebuild when backend changes
5. **migration** (optional) — Skipped — schema at head
6. **restart** (required) — docker compose up -d — services must restart after image/build/migration changes
7. **health** (required) — Verify /health and container states on DS723+
8. **log verification** (required) — Review api/worker logs for startup errors

## Risk rationale

- Doctor status: READY_WITH_WARNINGS
