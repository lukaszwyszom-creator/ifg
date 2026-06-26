# Guardian Sprint 5A — IFG Release Plan

## Cel

Workflow `ifg.release.plan` — read-only plan wydania odpowiadający na pytanie:

> Co dokładnie zostanie wykonane, jeżeli uruchomię deploy?

Workflow **nie wykonuje** żadnych zmian.

## Pipeline

```
InitStage
  → DependencyStage
  → DoctorStage
  → RepositoryAnalysisStage
  → BuildDecisionStage
  → MigrationStage
  → ArtifactStage
  → ExecutionPlanStage
  → RiskStage
  → SummaryStage
```

## Zależności (Workflow Engine)

```python
IFG_RELEASE_PLAN_WORKFLOW = WorkflowDefinition(
    id="ifg.release.plan",
    depends_on=["ifg.doctor"],
    ...
)
```

`ExecutionEngine` uruchamia `ifg.doctor` automatycznie przed stage'ami planu. `DoctorStage` **nie** wywołuje doctor ręcznie — czyta wynik z `ctx.data["dependency_contexts"]["ifg.doctor"]`.

## Build decisions

Każda decyzja: `name`, `required`, `reason`, `confidence`.

- Frontend Build
- Backend Build
- Worker Build
- Compose Restart
- Migration Required
- Static Files

## Artifacts (planowane, nie budowane)

- Git SHA
- Frontend bundle fingerprint
- Docker image API / Worker (tagi planowane)
- Alembic revision
- Compose file + services

## Execution plan (symulowany)

1. git pull
2. frontend build
3. docker build api
4. docker build worker
5. migration
6. restart
7. health
8. log verification

Każdy krok: `simulated=True`, `required` zależny od build decisions.

## Deployment risk

`LOW` | `MEDIUM` | `HIGH` | `CRITICAL` + `risk_rationale[]`

## Raport

Wyłącznie z `WorkflowTransaction.release_plan` — terminal / JSON / markdown.

## CLI

```
guardian ifg release plan
guardian ifg release plan --json
guardian ifg release plan --markdown
guardian ifg release plan --fetch
```

## Zmiany w Core

- `WorkflowDefinition.depends_on`
- `WorkflowTransaction.dependencies`, `release_plan`
- `ExecutionEngine._run_dependencies()` — automatyczne uruchamianie zależności

## Zgodność ze Sprintem 4

- Reuse `ifg.doctor` jako dependency (pełna diagnoza przed planem)
- Ten sam wzorzec raportowania co repo audit / doctor

## Wpływ na Sprint 5B

- Plan gotowy jako input dla `ifg.deploy.run`
- Build decisions + execution plan + artifacts mapują się 1:1 na stage'y deploy

## Nie zaimplementowano

Docker build, SSH, restart, migration, git pull, rollback, recovery, backup.

## Nowe moduły

```
scripts/ifg_guardian/plugins/ifg/release_plan/
scripts/ifg_guardian/modules/ifg_release_plan.py
tests/unit/test_guardian_ifg_release_plan_workflow.py
```
