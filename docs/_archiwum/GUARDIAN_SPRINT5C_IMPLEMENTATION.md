# Guardian Sprint 5C — IFG Deploy Run (LIVE)

## Cel

Pierwszy workflow wykonujący **rzeczywiste operacje** deploymentu IFG:

```bash
guardian ifg deploy run --yes
guardian ifg deploy run --dry-run
```

Workflow `ifg.deploy.run` pozostaje identyczny jak Sprint 5B — ta sama sekwencja stage'ów i pipeline z release planu. Jedyna różnica: `ExecutionMode.LIVE` + potwierdzenie `--yes`.

## Architektura — weryfikacja

| Warstwa | Zmiana | Status |
|---------|--------|--------|
| Workflow Engine | `DeployExecutorContext` przekazywany do `IntentExecutor` w `_run_stages` | minimalna rozszerzalność, bez przebudowy |
| Plugin API | bez zmian | OK |
| Release Plan | bez zmian | OK |
| Dependency Engine | bez zmian — łańcuch doctor → release.plan → deploy.run | OK |
| Workflow stages | ten sam pipeline 7 stage'ów; Init/Blocker/Execution dostosowane do LIVE (wymagane przez 5C) | OK |

**Wniosek:** architektura Sprint 1–5B wystarczyła. LIVE deploy zrealizowany wyłącznie przez nowe Executory + routing komend z `LocalExecIntent`.

## Nowe Executory

```
scripts/ifg_guardian/core/workflow/executors/
  __init__.py          # IntentExecutor — dispatcher
  context.py           # DeployExecutorContext
  router.py            # classify_deploy_command()
  local_executor.py    # LocalExecutor (LIVE subprocess)
  ssh_executor.py      # SSHExecutor — rsync, remote git, alembic, backup
  docker_executor.py   # DockerExecutor — compose build via SSH
  compose_executor.py  # ComposeExecutor — up, logs, ps via SSH
  http_executor.py     # HTTPExecutor — /health via SSH curl
  git_executor.py      # GitExecutor (extracted)
  filesystem_executor.py
```

Routing z `LocalExecIntent` (workflow bez zmian intentów):

| Komenda z pipeline | Executor |
|--------------------|----------|
| `git pull` | LocalExecutor + SSHExecutor (local + remote pull) |
| `npm run build` | LocalExecutor |
| `rsync …` | SSHExecutor |
| `docker compose build` | DockerExecutor → SSH |
| `docker compose up` | ComposeExecutor → SSH |
| `alembic upgrade head` | SSHExecutor (backup pg_dump, potem migrate) |
| `curl /health` | HTTPExecutor → SSH |
| `docker compose logs` | ComposeExecutor → SSH |

## Safety

LIVE deploy dozwolony wyłącznie gdy:

- `--yes` podane
- `ifg.doctor` status: `READY` lub `READY_WITH_WARNINGS`
- brak blockerów (BLOCKED, CRITICAL risk)

`BlockerStage` w LIVE: `on_fail=halt` → workflow kończy się FAILED bez mutacji.

## RollbackPoint

Bez implementacji rollback — zapisany snapshot przed deployem:

- `commit_before` (local git)
- `images_before` (remote docker images)
- `alembic_before` (remote alembic current)

Pole w `DeployRunState.rollback_point` + `WorkflowTransaction.commit_before/image_before/alembic_before`.

## Wynik LIVE w WorkflowTransaction

- `duration_ms` (real)
- `deploy_run.executed_commands`
- `deploy_run.steps[].status` = EXECUTED | FAILED
- `deploy_run.health`, `deploy_run.containers`
- `deploy_run.warnings`
- `frontend_built`, `frontend_synced`, `containers_restarted`

## CLI

```bash
guardian ifg deploy run --yes              # LIVE
guardian ifg deploy run --yes --json
guardian ifg deploy run --dry-run          # symulacja (Sprint 5B)
```

Bez `--yes` w LIVE: exit code `2`, komunikat `LIVE deploy requires --yes.`

## Testy

| Plik | Zakres |
|------|--------|
| `test_guardian_deploy_executors.py` | router, mock SSH/Docker/Compose/HTTP, LIVE routing, backup przed alembic |
| `test_guardian_ifg_deploy_run_workflow.py` | DRY_RUN regression, LIVE blocked, LIVE executed (mock executors), raporty |

**104 testy PASS** (cały pakiet Guardian).

## Nie zaimplementowano

- Rollback execution
- Automatyczny rollback po failure
- SIGINT → ABORTED

## Gotowość produkcyjna

Guardian jest **architektonicznie gotowy** do pierwszego produkcyjnego deployu (`guardian ifg deploy run --yes`), pod warunkiem:

1. SSH alias `ds723` / `scripts/ds723.env` skonfigurowane
2. `ifg.doctor` → READY lub READY_WITH_WARNINGS
3. `ifg.release.plan` bez blockerów CRITICAL
4. Wykonanie z brancha `production` na Mac mini (zgodnie z WORKFLOW.md)

Zalecany pierwszy deploy: najpierw `--dry-run`, potem `--yes`.
