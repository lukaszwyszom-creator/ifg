# Guardian Python 3.8 — implementacja poprawki

**Data:** 2026-07-06  
**Źródło analizy:** `docs/reports/2026-07-06_GUARDIAN_PYTHON38_COMPATIBILITY.md`  
**Commit:** `fix(guardian): restore Python 3.8 compatibility`

---

## 1. Problem

Na DS723+ (Python 3.8) Guardian kończył się błędem przy imporcie:

```
ImportError: cannot import name 'UTC' from 'datetime'
```

Przyczyna: `datetime.UTC` dostępne od Python 3.11.

---

## 2. Zmiany

### Nowy moduł

`scripts/ifg_guardian/core/time_compat.py`:

```python
UTC = timezone.utc  # ≡ datetime.UTC na 3.11+
```

### Zaktualizowane importy (10 plików)

| Plik |
|------|
| `core/preflight/engine.py` |
| `core/preflight/models.py` |
| `core/preflight/report.py` |
| `core/workflow/engine.py` |
| `core/workflow/transaction.py` |
| `core/repo_audit/report.py` |
| `reporting.py` |
| `plugins/ifg/doctor/report.py` |
| `plugins/ifg/release_plan/report.py` |
| `plugins/ifg/deploy_run/report.py` |

Wzorzec:

```python
from datetime import datetime
from ifg_guardian.core.time_compat import UTC
```

Wywołania `datetime.now(UTC)` — **bez zmian**.

### Test

`tests/unit/test_guardian_time_compat.py` — weryfikuje `UTC is timezone.utc` oraz `datetime.now(UTC).tzinfo`.

---

## 3. Wynik testów

```bash
PYTHONPATH=scripts python3 -m pytest tests/unit/test_guardian_*.py --no-cov -q
```

| Wynik | Liczba |
|-------|--------|
| **PASS** | 147 |
| **FAIL** | 3 |
| Czas | ~10 s |

### Niepowodzenia (niezwiązane z poprawką 3.8)

Wszystkie 3 w `test_guardian_plugins_sprint2.py` — przestarzałe asercje liczby workflow IFG (`3` vs faktyczne `4` po dodaniu `ifg.container.cutover`):

- `TestPluginLoader.test_load_static_plugins`
- `TestIFGPlugin.test_workflows_contains_all_ifg_workflows`
- `TestPluginListCLI.test_guardian_plugin_list_output`

Test `test_guardian_time_compat.py`: **PASS**.

---

## 4. Weryfikacja DS723+ (do wykonania przez operatora)

```bash
cd /volume1/docker/ifg_v2/ifg_standalone
PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --dry-run
```

Oczekiwane: brak `ImportError: UTC`, workflow dry-run startuje.

---

## 5. Zakres wykluczony

- `scripts/guardian2.py`, `guardian_platform/**` — nadal używają `datetime.UTC` (poza zakresem tego commitu)
- push, deploy, LIVE cutover — nie wykonano

---

*Poprawka minimalna zgodnie z raportem kompatybilności.*
