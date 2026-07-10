# Raport implementacji: Guardian Progress Protocol

**Data:** 2026-07-07  
**Zakres:** Warstwa observability `[GWO_PROGRESS]` dla długich workflow Guardian  
**Deploy IFG:** nie wykonywany

---

## 🩷 STATUS KOŃCOWY

### ✅ Co działa

- Standardowy format logu `[GWO_PROGRESS] step=X/Y phase=… status=… elapsed=… message=…`
- `ProgressTracker` z heartbeat co 30 s (`status=running`, `alive; last_action=…`)
- Integracja w `ExecutionEngine` (start/koniec workflow i stage)
- Integracja w `IntentExecutor` dla kroków deploy w `simulate_execution`
- 10 kanonicznych faz deployu w `DEPLOY_PHASES`
- `--progress` / `--no-progress` w CLI długich workflow
- Domyślnie włączone dla `LONG_WORKFLOW_IDS`
- Sekcja **Timeline wykonania** w raportach markdown (deploy, doctor, release plan/evaluate, cutover)
- `progress_timeline` w `transaction.audit` (persist w `.guardian/workflows/`)
- Testy jednostkowe formatowania i trackera
- Dokumentacja architektury

### ⚠️ Znane problemy

- `prod recover` (`guardian2.py recover-prod`) nie emituje jeszcze `[GWO_PROGRESS]`
- Fazy `commit` / `push` mapowane heurystycznie z komend shell — deploy pipeline IFG ich nie wykonuje bezpośrednio (commit/push poza Guardianem)
- Dependency workflows z `output_format=none` nadal zbierają timeline, ale nie drukują raportu

### ❌ Co nie działa

- Brak — w zakresie tego zadania

---

## A. Root cause

Brak jawnego protokołu postępu utrudniał obserwację długich operacji (deploy 5–15 min, cutover, evaluate). Rozwiązanie: cienka warstwa observability bez dotykania logiki pipeline.

## B. Zmienione / nowe pliki

**Nowe:**

- `scripts/ifg_guardian/core/progress/protocol.py`
- `scripts/ifg_guardian/core/progress/timeline.py`
- `scripts/ifg_guardian/core/progress/mapping.py`
- `scripts/ifg_guardian/core/progress/tracker.py`
- `scripts/ifg_guardian/core/progress/report.py`
- `scripts/ifg_guardian/core/progress/__init__.py`
- `tests/unit/test_guardian_progress_protocol.py`
- `docs/architecture/GUARDIAN_PROGRESS_PROTOCOL.md`

**Zmodyfikowane:**

- `scripts/ifg_guardian/core/workflow/engine.py`
- `scripts/ifg_guardian/core/workflow/executors/__init__.py`
- `scripts/ifg_guardian/cli.py`
- `scripts/ifg_guardian/modules/ifg_deploy_run.py`
- `scripts/ifg_guardian/modules/ifg_doctor.py`
- `scripts/ifg_guardian/modules/ifg_release_plan.py`
- `scripts/ifg_guardian/modules/ifg_release_evaluate.py`
- `scripts/ifg_guardian/modules/ifg_container_cutover.py`
- `scripts/ifg_guardian/modules/workflow.py`
- `scripts/ifg_guardian/plugins/ifg/deploy_run/report.py`
- `scripts/ifg_guardian/plugins/ifg/doctor/report.py`
- `scripts/ifg_guardian/plugins/ifg/release_plan/report.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/report.py`
- `scripts/ifg_guardian/plugins/ifg/container_cutover/report.py`

## C. Deploy

Nie wykonywano (zgodnie z wymaganiem).

## D. Testy

```bash
pytest tests/unit/test_guardian_progress_protocol.py -q
pytest tests/unit/test_guardian_*.py -q
```

## E. Następny krok

1. Opcjonalnie: rozszerzyć `guardian2.py recover-prod` o ten sam protokół
2. Przy następnym deployu IFG obserwować stderr pod `[GWO_PROGRESS]` i sekcję Timeline w raporcie

---

## Przykład użycia

```bash
python scripts/guardian.py ifg deploy run --dry-run 2>&1 | grep GWO_PROGRESS
python scripts/guardian.py ifg deploy run --dry-run --no-progress
```
