# Guardian Platform — Test Suite (M2.5)

**Status:** M2.5 complete  
**Date:** 2026-06-26

---

## Podsumowanie

| Metryka | Wartość |
|---------|---------|
| **Nowe testy platformy** | **138** |
| Stare testy Guardiana (bez zmian) | 104 |
| **Łącznie testów Guardiana po M2.5** | **242** |
| Wynik nowych testów | 138 passed |
| Wynik starych testów | 104 passed |

Uruchomienie:

```bash
.venv/bin/python -m pytest tests/guardian_platform/ -q
.venv/bin/python -m pytest tests/unit/ -k guardian -q
```

---

## Struktura

```
tests/guardian_platform/
  conftest.py           # fixtures, run_main helper
  test_cli.py           # CLI integration (plugin list, workflow, guards, profiles)
  test_registry.py      # CommandRegistry
  test_profiles.py      # Core/IFG/PSAG profile registration
  test_loader.py        # load_platform, dedupe, aliases
  test_runtime.py       # guards, ExecutionMode, CommandContext
  test_config.py        # .guardian.yml loader
  test_reporting.py     # terminal/json/markdown writers
  test_workflow.py      # ExecutionEngine, intents, core.ping stages
  test_core_ping.py     # workflow run core.ping via CLI
  test_ifg_profile.py   # IFG models, repo audit, doctor, CLI commands
  test_psag_profile.py  # PSAG scaffold
  test_regression.py    # legacy guardian.py + stary pakiet testów
```

---

## Pokryte moduły (core)

| Moduł | Testy |
|-------|-------|
| `core/registry/commands.py` | test_registry.py |
| `core/registry/workflows.py` | test_workflow.py |
| `core/registry/profiles.py` | test_profiles.py |
| `core/profiles/loader.py` | test_loader.py |
| `core/config/loader.py` | test_config.py |
| `core/runtime/guards.py` | test_runtime.py |
| `core/runtime/context.py` | test_runtime.py |
| `core/runtime/mode.py` | test_runtime.py |
| `core/reporting/writers.py` | test_reporting.py |
| `core/workflow/engine.py` | test_workflow.py |
| `core/workflow/executors.py` | test_workflow.py |
| `core/workflow/workflows/ping.py` | test_workflow.py, test_core_ping.py |
| `core/cli/app.py` | test_cli.py |
| `core/cli/builder.py` | test_registry.py (resolve) |
| `core/profiles/builtin.py` | test_cli.py, test_profiles.py |

---

## Pokryte profile

### IFG (`test_ifg_profile.py`)

- Profile loading + 7 komend read-only
- Workflow definitions (`ifg.doctor`, `ifg.repo.audit`)
- Doctor models/aggregation
- Repo audit classifier/service
- CLI: doctor, repo audit (mock), deploy/frontend/ksef/prod health (integration)
- Repo audit workflow w tmp git repo
- Brak importów `ifg_guardian`

### PSAG (`test_psag_profile.py`)

- Profile loading
- `psag ping` (registry + CLI)

---

## Pokryte scenariusze CLI

| Komenda | Plik testowy |
|---------|--------------|
| `plugin list` | test_cli.py |
| `workflow list` | test_cli.py |
| `workflow run core.ping` | test_core_ping.py |
| `repo status` | test_cli.py |
| `repo audit` (core generic) | test_cli.py |
| `ifg doctor` | test_cli.py, test_ifg_profile.py |
| `ifg deploy/frontend/ksef/prod health` | test_ifg_profile.py |
| `ifg repo audit` | test_ifg_profile.py |
| `psag ping` | test_cli.py, test_psag_profile.py |
| `--dry-run` / `--yes` guard | test_cli.py, test_runtime.py |
| `platform mutate-test` blocked | test_cli.py |

---

## Luki (świadome)

1. **Brak dedykowanych testów jednostkowych** dla każdego pliku w `profiles/ifg/doctor/checks.py` (pokrycie pośrednie przez doctor runner + CLI).
2. **SSH/Docker/Compose** — testy integracyjne akceptują exit 0/1 bez mockowania DS723 (zależność środowiska).
3. **IntentExecutor** — brak GitFetchIntent (fetch w profilu IFG synchroniczny w service).
4. **test_config.py** — poza preferowaną listą, ale uzupełnia pokrycie loadera `.guardian.yml`.
5. **Mutating commands** — celowo nie testowane (M3).

---

## Regression

- `scripts/guardian.py doctor` — test_regression.py
- `tests/unit/test_guardian_*.py` — 104 passed, **bez modyfikacji**
- Platforma i stary Guardian — osobne pakiety testów

---

## Wyniki uruchomienia (2026-06-26)

```
tests/guardian_platform/     138 passed
tests/unit/ -k guardian      104 passed
```

**Werdykt: GUARDIAN_PLATFORM_M2_5_TESTS — ACCEPTED**
