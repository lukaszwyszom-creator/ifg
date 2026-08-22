# Guardian Sprint 5B — IFG Deploy Run (Dry-Run)

## Cel

Workflow `ifg.deploy.run` — symulacja deploymentu bez mutacji. Odpowiada na pytanie:

> Co dokładnie zostałoby wykonane podczas deployu?

## Pipeline

```
InitStage
  → DependencyStage
  → ReleasePlanStage
  → BlockerStage
  → BuildPipelineStage
  → SimulateExecutionStage
  → SummaryStage
```

## Zależności

```python
depends_on=["ifg.release.plan"]
```

Workflow Engine uruchamia łańcuch: `ifg.doctor` → `ifg.release.plan` → `ifg.deploy.run`.

`ReleasePlanStage` czyta plan wyłącznie z `dependency_contexts["ifg.release.plan"]`.

## Pipeline deploy (8 kroków)

1. git pull
2. frontend build
3. dist sync *(nowy — z planu Static Files)*
4. docker build *(api + worker)*
5. alembic upgrade
6. compose up
7. health check
8. log verification

Kroki wymagane/pominięte zgodnie z release plan `execution_plan` + `build_decisions`.

## Symulacja

`SimulateExecutionStage` emituje `LocalExecIntent(mutating=True)` — w `ExecutionMode.DRY_RUN` executor **nie wykonuje** subprocess. Każdy krok: `status=SIMULATED`.

## Raport

`WorkflowTransaction.deploy_run` — terminal / JSON / markdown:

- co zostałoby wykonane,
- dlaczego (reason),
- kroki required vs skipped,
- deployment risk,
- blockers.

## CLI

```bash
guardian ifg deploy run --dry-run
guardian ifg deploy run --dry-run --json
guardian ifg deploy run --dry-run --markdown
```

Bez `--dry-run`:

```
LIVE deploy is not enabled yet — will be available in Sprint 5C.
Use: guardian ifg deploy run --dry-run
```

Exit code: `2`

## Transaction

Nowe pole: `deploy_run` (dict).

## Zgodność ze Sprintem 5A

- Pipeline deploy mapowany 1:1 z release plan
- dist sync dodany między frontend build a docker build

## Sprint 5C (następny)

- LIVE deploy z `--yes`
- realne SSH / Docker / alembic
- rollback hooks

## Nie zaimplementowano

Realny SSH, Docker build, restart, migration, git pull, rollback, backup.

## Nowe moduły

```
scripts/ifg_guardian/plugins/ifg/deploy_run/
scripts/ifg_guardian/modules/ifg_deploy_run.py
tests/unit/test_guardian_ifg_deploy_run_workflow.py
```
