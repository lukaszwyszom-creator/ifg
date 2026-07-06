# Guardian Execution Guard — Mac-only LIVE orchestration

**Data:** 2026-07-06  
**Incydent:** `ifg cutover run --yes` uruchomione na DS723+ → `backup failed: ssh exit 255`  
**Rozwiązanie:** Execution Guard blokujący mutujące workflow LIVE na hoście docelowym DS723+

---

## 1. Cel

Wymusić model operacyjny:

| Host | Rola |
|------|------|
| Mac mini | Orchestration host — uruchamia Guardian |
| DS723+ | Execution target — mutacje przez SSH |

Guardian **nie wykonuje** mutujących workflow produkcyjnych LIVE, gdy wykryje uruchomienie na DS723+.

---

## 2. Implementacja

### Moduł

`scripts/ifg_guardian/core/execution_guard.py`

| Element | Opis |
|---------|------|
| `detect_ds723_target_signals()` | Wykrywa hostname (`ds723`), ścieżkę prod repo, `/volume1/` |
| `check_execution_guard()` | Decyzja GO / NO_GO / WARN |
| `enforce_execution_guard()` | Blokuje LIVE (raise `ExecutionGuardError`) lub ostrzega przy dry-run |
| `enforce_mutating_live_orchestration()` | Guard dla ścieżek poza `WorkflowDefinition` |

### Integracja

| Punkt | Zachowanie |
|-------|------------|
| `ExecutionEngine.run()` / `_run_single()` | Guard przed startem etapów dla `workflow.mutating` |
| `run_ifg_container_cutover_rollback()` | Guard LIVE |
| `run_prod_recover()` | Guard LIVE |

### Objęte workflow (przez `mutating=True`)

- `ifg.container.cutover`
- `ifg.deploy.run`

### Komunikaty

**LIVE blocked (NO_GO):**

```
This workflow must be executed from the orchestration host (Mac mini). DS723+ is an execution target only. Run this command from Mac mini.
```

**Dry-run warning:**

```
Dry-run on DS723+ is diagnostic only. LIVE execution must be started from Mac mini.
```

---

## 3. Czego nie zmieniono

- Brak local executor
- Brak zmian architektury SSH
- Brak deploy / LIVE cutover w ramach tej zmiany

---

## 4. Testy

`tests/unit/test_guardian_execution_guard.py`:

| Test | Oczekiwanie |
|------|-------------|
| LIVE mutating + hostname DS723+ | NO_GO |
| LIVE mutating + prod repo path | NO_GO |
| Dry-run + DS723+ | dozwolone + warning na stderr |
| Mac mini path + LIVE | GO |
| `execute_ifg_container_cutover --yes` na DS723+ | `ExecutionGuardError` |
| Dry-run cutover na DS723+ | SUCCESS + warning |

---

## 5. Runbook

Zaktualizowano `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` — sekcja Guardian workflow: LIVE wyłącznie z Mac mini.

---

## 5. Operacja po `git pull` na DS723+

Po wdrożeniu commitu na DS723+:

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
git pull
```

LIVE cutover nadal uruchamiać z Mac mini.

---

*Raport implementacji Execution Guard. Bez deploy i LIVE cutover.*
