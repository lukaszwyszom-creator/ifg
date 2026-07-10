# GWO-G-003 — Guardian Execution Layer Etap 1

**Date:** 2026-07-05  
**Architecture:** [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md](../guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md) §7 Etap 1  
**Status:** Complete  
**Scope:** Introduce Execution Backend + Operation Engine without behavior change

---

## Summary

Etap 1 introduces the `ifg_guardian.core.execution` package as the first architectural layer from Guardian v3 roadmap. Existing deploy workflows behave identically; compose operations now route through `DeploymentEngine` → `OperationEngine` → `ComposeBackend` → `ComposeExecutor`.

---

## Changes

### New module: `ifg_guardian/core/execution/`

| File | Purpose |
|------|---------|
| `__init__.py` | Public exports |
| `backend.py` | `ExecutionBackend` protocol; `DeploymentBackend` alias |
| `models.py` | `Operation` enum, `DeployContext`, `OperationResult`, `DeploymentResult` alias |
| `compose_backend.py` | `ComposeBackend` — wraps `ComposeExecutor` |
| `operation_engine.py` | `OperationEngine` — `Operation.Deploy` only |
| `deployment_engine.py` | `DeploymentEngine.deploy()` facade |
| `discovery.py` | Stub — Etap 3 |
| `capability.py` | Stub — Etap 4 |
| `event_bus.py` | Stub — Etap 3+ |
| `synology_project_backend.py` | Stub — Etap 2 |

### Wiring change (single integration point)

**File:** `scripts/ifg_guardian/core/workflow/executors/__init__.py`

- `COMPOSE_UP` → `DeploymentEngine.deploy()` → `OperationEngine.execute(Operation.Deploy)` → `ComposeBackend.deploy()`
- `COMPOSE_LOGS` → `ComposeBackend.logs()` (direct, not via OperationEngine — logs operation TODO)

All other intent routing unchanged.

### Documentation

- Architecture doc §24 **Implementation status** table added

---

## Module structure

```
scripts/ifg_guardian/core/execution/
├── __init__.py
├── backend.py              # ExecutionBackend, DeploymentBackend alias
├── models.py               # Operation, DeployContext, OperationResult
├── compose_backend.py      # ComposeBackend (Etap 1 deliverable)
├── operation_engine.py     # OperationEngine (Deploy only)
├── deployment_engine.py    # deploy() facade
├── discovery.py            # Planned
├── capability.py           # Planned
├── event_bus.py            # Planned
└── synology_project_backend.py  # Planned
```

**Call chain (compose up):**

```
IntentExecutor
  └── DeploymentEngine.deploy()
        └── OperationEngine.execute(Operation.Deploy)
              └── ComposeBackend.deploy()
                    └── ComposeExecutor.execute_up()
```

---

## Files touched

| Path | Change |
|------|--------|
| `scripts/ifg_guardian/core/execution/*` | **Added** (10 files) |
| `scripts/ifg_guardian/core/workflow/executors/__init__.py` | **Modified** — route compose via execution layer |
| `docs/guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md` | **Modified** — §24 Implementation status |

**Not modified:** deploy pipeline, stages, guardian2, guardian_platform, IFG plugin logic, production config.

---

## Backward compatibility

| Aspect | Status |
|--------|--------|
| `DeploymentBackend` name | Preserved as alias to `ExecutionBackend` |
| `ComposeExecutor` | Unchanged; used internally by `ComposeBackend` |
| `IntentExecutor` public API | Unchanged |
| Deploy workflow stages | Unchanged |
| CLI / guardian2 | Unchanged |
| User-visible behavior | Unchanged |

---

## Test results

**Command:**

```bash
python3.11 -m pytest tests/unit/test_guardian_*.py --confcutdir=tests/unit -q
python3.11 -m pytest tests/guardian_platform/ --confcutdir=tests/guardian_platform -q
```

| Suite | Result |
|-------|--------|
| `ifg_guardian` unit tests | **104 passed** |
| `guardian_platform` tests | **301 passed** |
| Deploy executors + deploy run | **27 passed** (subset) |

**Regression:** None observed in Guardian test suites.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Double indirection makes debugging harder | `DeploymentEngine` → `OperationEngine` chain is shallow; same SSH/compose output |
| `ComposeBackend` + `ComposeExecutor` duplication | Single `ComposeExecutor` instance inside `ComposeBackend`; no duplicate SSH |
| Partial `OperationEngine` may confuse callers | Non-Deploy operations return explicit `NotImplemented` error |
| Etap 1 only covers compose_up path | Other runtime ops (restart, stop) still via legacy executors until Etap 4 |

---

## Recommendation — start Etap 2

**Ready to proceed** with Etap 2 (`SynologyProjectBackend`) when:

1. IFG DSM Project registered per [IFG_CONTAINER_MANAGER_MIGRATION.md](IFG_CONTAINER_MANAGER_MIGRATION.md)
2. Compose `name: ifg` + external volume pin applied on DS723+
3. GWO-G-004 approved for synowebapi spike (list/status dry-run on NAS)

Etap 2 should implement `SynologyProjectBackend` behind `--backend=synology_project` flag without changing default production backend (`compose`).

---

**End of report.**
