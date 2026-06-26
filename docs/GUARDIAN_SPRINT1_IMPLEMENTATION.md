# Guardian Sprint 1 — Workflow Engine Implementation

**Data:** 2026-06-26  
**Spec:** [`GUARDIAN_WORKFLOW_ENGINE.md`](GUARDIAN_WORKFLOW_ENGINE.md)  
**Zakres:** minimalny Workflow Engine + `core.ping`

---

## Zaimplementowane

### Core (`scripts/ifg_guardian/core/workflow/`)

| Moduł | Opis |
|-------|------|
| `mode.py` | `ExecutionMode`: LIVE, DRY_RUN, PLAN |
| `state.py` | `WorkflowState` (8 stanów), `WorkflowStateMachine`, `InvalidStateTransition` |
| `transaction.py` | `WorkflowTransaction` schema v1 (`to_dict` / `from_dict`), `StageRecord`, `ArtifactRecord` |
| `context.py` | `WorkflowContext` |
| `definition.py` | `WorkflowDefinition` |
| `stage.py` | `Stage`, `StagePlan`, `StageResult`, `StageStatus`, `BuildReason`, `SkipReason` |
| `intents.py` | `NoOpIntent`, `LocalExecIntent`, `FsExistsIntent`, `GitRevParseIntent`, `GitStatusIntent` |
| `results.py` | `IntentResult`, `StageExecutionResults` |
| `executors.py` | `IntentExecutor`, `LocalExecutor`, `FilesystemExecutor`, `GitExecutor` |
| `engine.py` | `ExecutionEngine` — pętla build_plan → execute → interpret; persystencja `.guardian/workflows/` |
| `registry.py` | rejestr workflow |
| `workflows/ping.py` | `core.ping`: InitStage → NoOpStage → SummaryStage |

### CLI

```bash
python3 scripts/guardian.py workflow run core.ping
python3 scripts/guardian.py workflow run core.ping --dry-run
python3 scripts/guardian.py workflow run core.ping --plan
```

### Testy

Plik: `tests/unit/test_guardian_workflow_engine.py` — **16 testów**, wszystkie PASS.

| Grupa | Testy |
|-------|-------|
| State Machine | 5 |
| WorkflowTransaction | 2 |
| DRY_RUN | 3 |
| Execution Engine | 4 |
| NoOp workflow | 2 |

### DRY_RUN

- Ten sam pipeline co LIVE.
- Mutujące intencje (`LocalExecIntent`) są symulowane (`simulated=True`, output `[dry-run] would: ...`).
- Read-only intencje (git, fs, noop) wykonują się normalnie.

### Persystencja

```
.guardian/workflows/<workflow_id>/transaction.json
.guardian/latest/core_ping.json
```

---

## Świadomie niezaimplementowane (Sprint 1)

| Obszar | Status |
|--------|--------|
| Plugin API / plugin loader | — |
| IFG deploy workflow | — |
| Doctor jako workflow | — |
| Repo audit jako workflow | — |
| Rollback engine | — |
| Retry policy (per-stage backoff) | — |
| ABORTED / ROLLED_BACK w runtime Engine | stany w SM, bez triggerów |
| Executors: SSH, Docker, HTTP, Compose | — |
| Intents: fetch, pull, compose, ssh, http | — |
| `--yes` prompt dla mutating workflow | — |
| `history.json` indeks runów | — |
| SIGINT → ABORTED | — |
| Stage skip w `core.ping` | API gotowe, brak użycia |
| Markdown/JSON output writers dla workflow | tylko terminal + transaction.json |

---

## Wynik testów

```
tests/unit/test_guardian_workflow_engine.py — 16 passed in 0.40s
```

CLI smoke:

```
python3 scripts/guardian.py workflow run core.ping
→ Status: SUCCESS, exit 0
```

---

## Pliki dodane / zmienione

**Nowe:**
- `scripts/ifg_guardian/core/workflow/*`
- `scripts/ifg_guardian/modules/workflow.py`
- `tests/unit/test_guardian_workflow_engine.py`

**Zmienione:**
- `scripts/ifg_guardian/cli.py` — subcommand `workflow run`

---

## Następny sprint (propozycja)

1. Retry policy + abort (SIGINT)
2. Executors: SSH, Docker, Http
3. `ifg.deploy.run` jako drugi workflow (bez plugin loader — wbudowany w registry)
4. Doctor → workflow z fan-out checks
