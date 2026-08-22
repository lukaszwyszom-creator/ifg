# Guardian Sprint 3 — Repo Audit Workflow

## Cel

Pierwszy produkcyjny workflow na Workflow Engine: `core.repo.audit`, zastępujący monolityczną implementację w `modules/repo.py`.

## Co przeniesiono

| Obszar | Stare (`modules/repo.py`) | Nowe |
|--------|---------------------------|------|
| Klasyfikacja plików | `_classify_*`, `_should_ignore` | `core/repo_audit/classifier.py` |
| Line endings + BuildReason | `_classify_line_endings` | `classifier.classify_line_endings` + `LineEndingAnalysisStage` |
| Agregacja ryzyka | `collect_audit` (risk block) | `core/repo_audit/service.aggregate_risk` + `RiskAnalysisStage` |
| Rekomendacje | `_build_recommended_actions` | `core/repo_audit/actions.py` + `RecommendedActionsStage` |
| Raportowanie | `_format_audit_report` | `core/repo_audit/report.py` (terminal / json / markdown) |
| Orkiestracja | `collect_audit` / `run_repo_audit` | workflow 9 stage'ów + `modules/repo_audit.py` |

### Workflow `core.repo.audit` (CorePlugin)

```
InitStage
  → CollectGitStatusStage
  → CollectRepositoryMetadataStage
  → ClassifyFilesStage
  → LineEndingAnalysisStage
  → RiskAnalysisStage
  → RecommendedActionsStage
  → ReportStage
  → SummaryStage
```

### BuildReason

Każda decyzja EOL w `LineEndingAnalysisStage` emituje `BuildReason` z polami `decision`, `because`, `confidence`, `source_stage`.

Przykład: `UNKNOWN_LINE_ENDINGS` / `because: [app/api/deps.py]` / `confidence: LOW`.

### WorkflowTransaction

Pole `audit` (dict) + `recommended_actions` + `duration_ms` + pełny snapshot stage'ów. Raporty renderowane wyłącznie z transakcji — brak drugiej ścieżki raportowania.

### Pluginy

- `core.repo.audit` — CorePlugin
- IFGPlugin: hook `repo_audit_extensions()` (puste); może rozszerzać klasyfikację i ryzyko, nie własny audit

### CLI

```
guardian repo audit
guardian repo audit --dry-run
guardian repo audit --json
guardian repo audit --markdown
guardian repo audit --fetch
```

Wszystkie warianty używają Workflow Engine.

## Co usunięto

Z `modules/repo.py` usunięto ~350 linii zduplikowanej logiki audit (klasyfikacja, raport, rekomendacje). Pozostały: `run_repo_sync`, `run_repo_clean_dry_run` (adapter na `collect_audit` → workflow).

## Zgodność ze Sprintem 2

- Workflow rejestrowany wyłącznie przez PluginRegistry (CorePlugin)
- `ExecutionEngine.run()` rozszerzony o `initial_data` i `plugin_registry`
- Nowy intent: `GitFetchIntent` (fetch w `CollectGitStatusStage`, respektuje DRY_RUN)
- Testy Sprint 1/2 nadal przechodzą (Core: 2 workflow)

## Wpływ na kolejne sprinty

| Sprint | Wpływ |
|--------|-------|
| Deploy | Wzorzec stage'ów + transakcja gotowe; repo audit nie blokuje |
| Doctor | `doctor` wywołuje `run_repo_audit` — automatycznie przez workflow |
| Rollback / Recovery | Nie implementowano (zgodnie z zakresem Sprint 3) |

## Nowe moduły

```
scripts/ifg_guardian/core/repo_audit/
scripts/ifg_guardian/plugins/core/workflows/repo_audit/
scripts/ifg_guardian/modules/repo_audit.py
tests/unit/test_guardian_repo_audit_workflow.py
```

## Testy

- Repo workflow (registry, clean repo, dry-run fetch)
- Risk aggregation
- CRLF / deps.py regression (`UNKNOWN_LINE_ENDINGS`, nie `CRLF_ONLY`)
- WorkflowTransaction.audit
- Markdown / JSON / Terminal report
- Integracja line-ending stage w git repo

## Nie zaimplementowano (zgodnie z zakresem)

Deploy, Doctor (nowy), SSH, Docker, Compose, Rollback, Recovery, Backup.
