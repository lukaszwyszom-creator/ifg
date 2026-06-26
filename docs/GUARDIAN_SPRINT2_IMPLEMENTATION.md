# Guardian Sprint 2 — Plugin Architecture Implementation

**Data:** 2026-06-26  
**Spec:** [`GUARDIAN_WORKFLOW_ENGINE.md`](GUARDIAN_WORKFLOW_ENGINE.md), [`GUARDIAN_V3_ARCHITECTURE_REVISED.md`](GUARDIAN_V3_ARCHITECTURE_REVISED.md)  
**Poprzednik:** [`GUARDIAN_SPRINT1_IMPLEMENTATION.md`](GUARDIAN_SPRINT1_IMPLEMENTATION.md)

---

## Architektura pluginów

```
CLI (guardian plugin list / workflow run)
        │
        ▼
create_runtime()  ──► GuardianRuntime (per invocation, not singleton)
        │
        ├── PluginLoader.load_static_plugins()
        │         ├── CorePlugin
        │         └── IFGPlugin
        │
        ├── PluginRegistry
        │         ├── register / unregister / get / list
        │         └── resolve_workflow() ──► WorkflowRegistry
        │
        └── ExecutionEngine.run(workflow)   # no plugin/domain knowledge
```

### Rozdział odpowiedzialności

| Warstwa | Zna IFG? | Rola |
|---------|----------|------|
| `core/workflow/engine.py` | **Nie** | Pętla Stage; intencje; persystencja |
| `core/plugins/*` | **Nie** | Plugin API, registry, loader, bootstrap |
| `core/workflow/workflow_registry.py` | **Nie** | Indeks workflow z pluginów |
| `plugins/core/` | **Nie** | `core.ping` — workflow generyczne |
| `plugins/ifg/` | Tak (domena) | Metadane IFG; workflows=[] (Sprint 3+) |

**Core nie importuje `plugins/ifg` poza `PluginLoader`** — loader jest jedynym punktem wiązania statycznego.

---

## Plugin API

```python
class GuardianPlugin(ABC):
    name: str
    version: str
    workflows() -> list[WorkflowDefinition]
    initialize(ctx: PluginContext) -> None
    shutdown() -> None
```

### PluginContext

- `config: GuardianConfig` (root path)
- `logger: GuardianLogger`
- `registry: PluginRegistry`
- `metadata: dict`

Plugin **nie dostaje executorów** — zgodnie ze specyfikacją.

---

## Rejestracja

1. `PluginLoader` tworzy instancje `CorePlugin`, `IFGPlugin`
2. `PluginRegistry.register(plugin)` — indeksuje workflow via `WorkflowRegistry.index_plugin()`
3. `plugin.initialize(PluginContext)` — po rejestracji wszystkich pluginów
4. `GuardianRuntime.shutdown()` — `unregister()` każdego pluginu → `shutdown()`

Brak globalnych singletonów — `create_runtime()` tworzy nową instancję per CLI/test.

---

## Odkrywanie workflow

```
guardian workflow run core.ping
        │
        ▼
create_runtime()
        │
        ▼
PluginRegistry.resolve_workflow("core.ping")
        │
        ▼
WorkflowRegistry.get("core.ping")  ← z CorePlugin.workflows()
        │
        ▼
ExecutionEngine.run(workflow)
```

`core.ping` przeniesiony z `core/workflow/workflows/` do `plugins/core/workflows/ping.py`.

Usunięto `core/workflow/registry.py` z ręcznym słownikiem workflow.

---

## CLI

```bash
python3 scripts/guardian.py plugin list
python3 scripts/guardian.py workflow run core.ping
```

Przykład `plugin list`:

```
Core
  version: 1.0.0
  workflows: 1

IFG
  version: 1.0.0
  workflows: 0
```

---

## Nowe moduły

| Moduł | Opis |
|-------|------|
| `core/plugins/base.py` | `GuardianPlugin` |
| `core/plugins/context.py` | `PluginContext`, `GuardianConfig`, `GuardianLogger` |
| `core/plugins/registry.py` | `PluginRegistry` |
| `core/plugins/loader.py` | `PluginLoader` (static) |
| `core/plugins/bootstrap.py` | `create_runtime()`, `GuardianRuntime` |
| `core/workflow/workflow_registry.py` | `WorkflowRegistry` |
| `plugins/core/plugin.py` | `CorePlugin` |
| `plugins/core/workflows/ping.py` | `core.ping` |
| `plugins/ifg/plugin.py` | `IFGPlugin` (empty workflows) |
| `modules/plugins.py` | `run_plugin_list()` |

---

## Świadomie niezaimplementowane

| Obszar | Sprint |
|--------|--------|
| Dynamic discovery (entry points, `.guardian/plugins/`) | 3+ |
| `ifg.deploy.run`, doctor, repo audit jako workflow | 3+ |
| Executors: SSH, Docker, HTTP | 3+ |
| Retry, rollback, recovery | 4+ |
| Plugin lifecycle hooks poza init/shutdown | — |
| `project.yaml` plugin activation | 3+ |
| Shared runtime / caching między komendami CLI | — |

---

## Testy

| Plik | Testy |
|------|-------|
| `test_guardian_workflow_engine.py` | 16 (Sprint 1, zaktualizowane importy) |
| `test_guardian_plugins_sprint2.py` | 14 (Sprint 2) |

**Łącznie:** 30 testów

---

## Gotowość do Sprintu 3

Plugin API i registry są stabilne. Sprint 3 może dodać `ifg.deploy.run` jako pierwszy workflow domenowy w `IFGPlugin` bez zmian w Execution Engine.

Wymagania Sprintu 3:
- Nowe intencje + executory (SSH, Docker, HTTP)
- `IFGPlugin.workflows()` → deploy definition
- Opcjonalnie: doctor/repo audit jako workflow w Core/IFG
