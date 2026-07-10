# GUARDIAN DEPLOY DIAGNOSTICS REPORT

## CEL

Poprawić wyłącznie diagnostykę istniejącego workflow deploy tak, aby awaria `simulate_execution: failed 1 step(s)` była jednoznacznie identyfikowalna.

## Przyczyna problemu

Dotychczas raport deploy nie zawierał pełnej diagnostyki per step:
- brak jawnego `exit code`,
- brak rozdzielenia `stdout` i `stderr`,
- brak sekcji wskazującej pojedynczy krok awarii (`FAILED STEP`),
- brak zsyntetyzowanego `ROOT CAUSE`.

Efekt: nie można było bezpiecznie zamknąć incydentu po awarii deploy.

## Zmienione miejsca (tylko diagnostyka)

- `scripts/ifg_guardian/core/workflow/executors/local_executor.py`
- `scripts/ifg_guardian/core/workflow/executors/ssh_executor.py`
- `scripts/ifg_guardian/core/workflow/executors/http_executor.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/models.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/stages.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/report.py`

## Co dokładnie dodano

### 1) Dane techniczne per step

Dla każdego kroku pipeline zapisywane są teraz:
- `step name` (action),
- `executed command`,
- `exit_code`,
- `stdout`,
- `stderr`,
- `execution time` (`duration_ms`),
- `failure_reason`.

### 2) Diagnostyka pierwszej awarii pipeline

W stanie deploy (`DeployRunState`) dodano `failed_step`, które zawiera:
- `step`,
- `command`,
- `exit_code`,
- `stdout`,
- `stderr`,
- `failure_reason`,
- `root_cause`,
- `duration_ms`.

### 3) Raport błędu w formacie incydentowym

W raporcie markdown/terminal pojawia się sekcja:

- `FAILED STEP:`
- `COMMAND:`
- `EXIT CODE:`
- `STDERR:`
- `ROOT CAUSE:`

gdy tylko któryś krok ma status `FAILED`.

## Weryfikacja

Uruchomiono:
- `pytest tests/unit/test_guardian_ifg_deploy_run_workflow.py -q` -> **13 passed**
- `python scripts/guardian.py ifg deploy run --plan --markdown` -> raport zawiera kolumnę `Exit` i komplet rozszerzonych danych step-level (dla dry-run bez failed step).

## Zakres zmian a ograniczenia

- Nie zmieniono logiki decyzji deploy.
- Nie zmieniono Policy Engine.
- Nie zmieniono Release Engine.
- Zmieniono tylko obserwowalność/diagnostykę awarii workflow deploy.
