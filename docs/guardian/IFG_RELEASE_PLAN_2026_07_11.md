# IFG Guardian — Release Plan

**Generated:** 2026-07-11 21:25:35 UTC  
**Question:** Co dokładnie zostanie wykonane, jeżeli uruchomię deploy?  
**Deployment risk:** `CRITICAL`  
**Doctor status:** `BLOCKED`  
**Workflow ID:** `2026-07-11T212532Z_ifg_release_plan`  
**Duration:** 0 ms  

## Dependencies

- `ifg.doctor` → SUCCESS (2026-07-11T212532Z_ifg_doctor)

## Repository

- Branch: `production`
- HEAD: `4a71c14` (`4a71c1410d2fd3f10bd447f11015892d6a599181`)
- Dirty: True
- Ahead/behind: 0/0

## Build decisions

| Decision | Required | Confidence | Reason |
|----------|----------|------------|--------|
| Frontend Build | yes | HIGH | ❌ [lokalnie] Frontend dist wymaga przebudowy (npm run build). (dist starszy niż commit 4a71c14 w frontend-react/src) |
| Backend Build | no | MEDIUM | no backend changes |
| Worker Build | no | MEDIUM | no worker rebuild needed |
| Compose Restart | yes | HIGH | services must restart after image/build/migration changes |
| Migration Required | no | HIGH | schema at head |
| Static Files | yes | HIGH | frontend dist must be rebuilt and synced to DS723+ |

## Artifacts

- **Git SHA:** `4a71c1410d2fd3f10bd447f11015892d6a599181` — target commit for deploy
- **Frontend bundle:** `93b81c0f4488` — planned dist/assets fingerprint
- **Docker image API:** `ifg-api:4a71c14` — planned tag — not built in plan mode
- **Docker image Worker:** `ifg-worker:4a71c14` — planned tag — not built in plan mode
- **Alembic revision:** `Traceback (most recent call last):
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
RuntimeError: Brak DATABASE_URL w zmiennych srodowiskowych dla Alembic.` — target schema revision
- **Compose file:** `docker/docker-compose.prod.yml` — production compose definition
- **Compose service:** `api` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `worker` — service managed by docker/docker-compose.prod.yml
- **Compose service:** `db` — service managed by docker/docker-compose.prod.yml

## Execution plan

1. **git pull** (required) — Synchronize DS723+ repository with origin/production
2. **frontend build** (required) — cd frontend-react && npm run build — ❌ [lokalnie] Frontend dist wymaga przebudowy (npm run build). (dist starszy niż commit 4a71c14 w frontend-react/src)
3. **docker build api** (optional) — Skipped — brak zmian backend
4. **docker build worker** (optional) — Skipped — brak zmian worker
5. **migration** (optional) — Skipped — schema at head
6. **restart** (required) — docker compose up -d — services must restart after image/build/migration changes
7. **health** (required) — Verify /health and container states on DS723+
8. **log verification** (required) — Review api/worker logs for startup errors

## Risk rationale

- Doctor status: BLOCKED

## Decyzje dla ChatGPT

Brak.
