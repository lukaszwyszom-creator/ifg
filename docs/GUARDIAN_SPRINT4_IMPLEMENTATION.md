# Guardian Sprint 4 — IFG Doctor Workflow

## Cel

Pierwszy workflow domenowy IFG: `ifg.doctor` — diagnoza gotowości środowiska do pracy i deployu. Wyłącznie read-only, bez napraw.

## Pytanie

> Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?

## Pipeline `ifg.doctor` (IFGPlugin)

```
InitStage
  → EnvironmentStage
  → RepositoryStage
  → FrontendStage
  → BackendStage
  → DockerStage
  → DatabaseStage
  → AlembicStage
  → ConfigurationStage
  → HealthStage
  → RiskAggregationStage
  → SummaryStage
```

## Check status

Każdy check: `PASS` | `WARN` | `FAIL` | `CRITICAL`

## Overall status

| Warunek | Status |
|---------|--------|
| brak FAIL/CRITICAL | wszystkie PASS → `READY` |
| tylko WARN | `READY_WITH_WARNINGS` |
| FAIL lub CRITICAL | `BLOCKED` |

## WorkflowTransaction

Pole `doctor` (dict) — pełny snapshot checków, overall status, summary. Raporty terminal/json/markdown wyłącznie z transakcji.

## Integracja z Core

- `RepositoryStage` wywołuje `collect_audit()` → workflow `core.repo.audit` (bez duplikacji logiki)
- CorePlugin **nie** rejestruje `ifg.doctor`

## CLI

```
guardian ifg doctor
guardian ifg doctor --json
guardian ifg doctor --markdown
guardian ifg doctor --dry-run
guardian ifg doctor --fetch
```

Legacy `guardian doctor` → adapter `run_ifg_doctor()`.

## Co usunięto

Monolityczny `run_doctor()` z sekwencji `run_repo_audit`, `run_frontend_check`, … — zastąpiony jednym workflow.

## Zgodność ze Sprintem 3

- Ten sam wzorzec: `execute_*` + `ExecutionEngine.run(initial_data, plugin_registry)`
- Raport w `SummaryStage`, zapis markdown do `docs/guardian/IFG_DOCTOR_*.md`
- `on_fail="continue"` — pełna diagnoza mimo FAIL w stage'ach

## Wpływ na Sprint 5 (Deploy)

- Doctor gotowy jako preflight; deploy workflow może reuse check helpers z `plugins/ifg/doctor/checks.py`
- Brak deploy / rollback / recovery (zgodnie z zakresem)

## Nowe moduły

```
scripts/ifg_guardian/plugins/ifg/doctor/
scripts/ifg_guardian/modules/ifg_doctor.py
tests/unit/test_guardian_ifg_doctor_workflow.py
```

## Nie zaimplementowano

Deploy, rollback, recovery, docker restart, git pull, build, naprawy automatyczne.
