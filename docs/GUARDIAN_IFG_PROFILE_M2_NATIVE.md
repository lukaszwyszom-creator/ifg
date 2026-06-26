# Guardian IFG Profile — M2 Native

**Status:** M2 complete  
**Date:** 2026-06-26  
**Profile version:** `0.3.0-m2`

---

## Cel M2

Usunięcie zależności profilu IFG od starego `ifg_guardian`. Wszystkie komendy read-only działają natywnie w `scripts/guardian_platform/profiles/ifg/`.

---

## Bridge usunięte (M1 → M2)

| Bridge M1 | Zastąpione przez |
|-----------|------------------|
| `ifg_guardian.modules.ifg_doctor.run_ifg_doctor` | `profiles/ifg/doctor/runner.py` + workflow `ifg.doctor` |
| `ifg_guardian.modules.repo_audit.run_repo_audit` | `profiles/ifg/repo_audit/runner.py` + workflow `ifg.repo.audit` |
| `ensure_scripts_path()` + import starego Guardiana | usunięte z `commands/doctor.py` |

---

## Moduły przeniesione / utworzone natywnie

### Doctor (`profiles/ifg/doctor/`)

| Plik | Źródło (stary Guardian) |
|------|-------------------------|
| `models.py` | `plugins/ifg/doctor/models.py` |
| `aggregation.py` | `plugins/ifg/doctor/aggregation.py` |
| `checks.py` | `plugins/ifg/doctor/checks.py` |
| `report.py` | `plugins/ifg/doctor/report.py` |
| `service.py` | `plugins/ifg/doctor/service.py` |
| `stages.py` | `plugins/ifg/doctor/stages.py` |
| `runner.py` | `modules/ifg_doctor.py` (logika uruchomienia) |
| `workflows/doctor.py` | `plugins/ifg/doctor/workflow.py` |

### Repo audit (`profiles/ifg/repo_audit/`)

| Plik | Źródło (stary Guardian) |
|------|-------------------------|
| `models.py` | `core/repo_audit/models.py` |
| `classifier.py` | `core/repo_audit/classifier.py` |
| `actions.py` | `core/repo_audit/actions.py` |
| `extensions.py` | `core/repo_audit/extensions.py` |
| `service.py` | `core/repo_audit/service.py` |
| `report.py` | `core/repo_audit/report.py` |
| `stages.py` | `plugins/core/workflows/repo_audit/stages.py` |
| `runner.py` | `modules/repo_audit.py` |
| `workflows/repo_audit.py` | `plugins/core/workflows/repo_audit/workflow.py` |

### Wspólne (`profiles/ifg/lib/`)

| Plik | Źródło |
|------|--------|
| `risk.py` | `ifg_guardian/core/risk.py` |
| `line_endings.py` | `ifg_guardian/core/line_endings.py` |
| `reporting.py` | `ifg_guardian/reporting.py` |

### Już natywne z M1 (bez zmian architektury)

- `commands/deploy_check.py`, `frontend_check.py`, `ksef_check.py`, `prod_health.py`
- `checks/frontend.py`, `infra/*`, `config/defaults.py`

---

## Zależności pozostałe

Profil IFG **nie importuje** `ifg_guardian.*`.

| Zależność | Użycie |
|-----------|--------|
| `guardian_platform.core.workflow.*` | silnik workflow (neutralny core) |
| `guardian_platform.core.runtime.*` | CommandContext, ExecutionMode |
| stdlib + subprocess | git, docker, ssh, curl |
| Lokalne repo IFG | `frontend-react/`, `app/`, `docker/` |

Stary Guardian (`scripts/guardian.py`, `scripts/ifg_guardian/`) pozostaje nietknięty i niezależny.

---

## Zmiany w core

**Brak zmian w M2.** Core platformy wykorzystywany jest wyłącznie przez istniejące hooki:

- `ExecutionEngine`, `WorkflowDefinition`, `Stage`
- `IntentExecutor` (NoOp, FsExists, GitRevParse, GitStatus)
- `CommandContext`, `CommandSpec`

Core neutrality (grep):

```
KSeF / ds723 / frontend-react w core/ → 0
ifg_guardian.modules w profiles/ifg/ → 0
```

---

## Wyniki testów (2026-06-26)

| Test | Wynik |
|------|-------|
| `plugin list` | ✅ ifg 0.3.0-m2 |
| `ifg doctor` | ✅ działa (exit 1 — BLOCKED, środowisko) |
| `ifg deploy check` | ✅ działa (exit 1 — commit/dist) |
| `ifg frontend check` | ✅ działa (exit 1 — dist stale) |
| `ifg ksef check` | ✅ działa (exit 1 — dist stale) |
| `ifg prod health` | ✅ OK (exit 0) |
| `ifg repo audit` | ✅ działa (exit 1 — WARNING) |
| `psag ping` | ✅ OK |
| `python3 scripts/guardian.py doctor` | ✅ działa (legacy) |
| `pytest tests/unit/test_guardian_*.py` | ✅ **104 passed** |
| `grep -R ifg_guardian.modules profiles/ifg/` | ✅ **0** |

---

## Ryzyka

1. **Duplikacja kodu** — logika doctor/repo audit istnieje równolegle w `ifg_guardian/` i profilu IFG; zmiany w starym Guardianie nie propagują się automatycznie.
2. **Brak testów jednostkowych profilu** — testy `test_guardian_*.py` nadal celują w stary `ifg_guardian`; regresje profilu platformy wymagają osobnych testów (M3+).
3. **Doctor → nested repo audit** — `RepositoryStage` wywołuje pełny workflow repo audit; koszt czasu przy dużym worktree.
4. **Git fetch w repo audit** — fetch wykonywany synchronicznie w `collect_git_status` (bez GitFetchIntent w core); wystarczające dla M2.

---

## Następny etap: M3 (mutating commands)

Poza zakresem M2 — dopiero później:

- `ifg deploy run` (dry-run + LIVE)
- `ifg prod recover`
- executory SSH/Docker/Compose w profilu IFG
- mutating guards + rollback

**Werdykt: GUARDIAN_IFG_PROFILE_M2_NATIVE — ACCEPTED**
