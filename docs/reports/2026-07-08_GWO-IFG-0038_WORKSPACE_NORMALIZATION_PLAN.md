# GWO-IFG-0038 — Workspace Normalization Plan

**Data:** 2026-07-08  
**Branch:** `production`  
**HEAD:** `a8410f3` — `GWO-IFG-0036: fix KSeF monitor and production integrity policy`  
**Stan:** 165 pozycji w `git status` (41 modified, 124 untracked)  
**Zakres:** analiza read-only — **bez commita, bez stash, bez usuwania, bez zmiany brancha**

---

## Kontekst

Commit `a8410f3` zawiera większość GWO-IFG-0036 (schema, TransmissionTable UX, dirty-tree policy, część Release Engine).  
Working tree nadal zawiera:

- **resztki 0036** (frontend Monitor KSeF nie w pełni w commicie),
- **całość 0037** (classification engine, duration, policy YAML — część jako untracked),
- **eksperymenty Guardian** (progress, dashboard, execution),
- **~85 plików dokumentacji** (raporty, audyty, artefakty workflow),
- **szum CRLF** w plikach magazynowych/fakturowych,
- **kilka pozycji do decyzji operatora**.

---

## Legenda rekomendacji

| Rekomendacja | Znaczenie |
|--------------|-----------|
| **COMMIT** | Włączyć do commita na `production` (Etap A) |
| **STASH** | Odłożyć na osobny branch / `git stash` (Etap B) |
| **ARCHIVE** | Zachować poza głównym commitem kodu (osobny commit docs, katalog archiwum, lub pozostawić untracked z gitignore) |
| **REVIEW** | Wymaga decyzji operatora przed jakąkolwiek akcją |
| ~~DELETE~~ | **Nie stosować** (zgodnie z zakresem GWO-IFG-0038) |

---

## Grupa 1 — GWO-IFG-0036 (resztki Monitor KSeF / production integrity)

**Liczba plików: 5** (wszystkie `modified`; główny commit już na HEAD)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `frontend-react/src/pages/advanced/AdvancedDashboard.jsx` | **COMMIT** | Zakładka nadal `Transmisje KSeF` w HEAD; working tree ma `Monitor KSeF` — brakujący fragment rename z 0036 |
| `frontend-react/src/api/transmissions.js` | **COMMIT** | Parametr `warnings_or_errors_only` dla filtra Monitor KSeF — funkcjonalność 0036, niezacommitowana |
| `frontend-react/src/components/dashboard/TransmissionTable.module.css` | **COMMIT** | Style liczników, filtra, metadanych tabeli Monitor KSeF — UI 0036 |
| `frontend-react/src/components/common/StatusBadge.jsx` | **COMMIT** | Mapowania severity KSeF (`info`, `warning`, `error`, `running`, `processing`) — UI 0036 |
| `app/persistence/repositories/transmission_repository.py` | **REVIEW** | Diff to wyłącznie puste linie / CRLF — **brak zmiany logiki**; rekomendacja: `git checkout --` (odrzucenie szumu) |

**Już w commicie `a8410f3` (nie wymaga ponownego commita):**  
`app/schemas/transmission.py`, `TransmissionTable.jsx`, `transmissionLoadError.js`, `invoiceOpenMode.js`, Guardian dirty-tree policy, `test_transmission_api.py`, raport `2026-07-08_GWO-IFG-0036_PRODUCTION_INTEGRITY_FIX.md`.

---

## Grupa 2 — GWO-IFG-0037 (Release Engine Quality)

**Liczba plików: 12** (6 modified + 6 untracked)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/classification.py` | **COMMIT** | Nowy silnik klasyfikacji BLOCKERS/WARNINGS/LOCAL ENVIRONMENT/INFORMATION |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/report.py` | **COMMIT** | Executive Summary, sekcje raportu, duration w output |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/service.py` | **COMMIT** | Score z konfiguracji polityki (bez hardcoded penalties) |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/workflow.py` | **COMMIT** | Definicja workflow evaluate (brak w repo przed 0037) |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/__init__.py` | **COMMIT** | Eksport pluginu release_evaluate |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/models.py` | **COMMIT** | `ClassifiedFinding`, `StatusSummary`, pola `local_environment`, `test_discovery_local_env` |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py` | **COMMIT** | Penalty z YAML, pomijanie blokady przy local env pytest |
| `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py` | **COMMIT** | `finalize_classification`, local env detection, duration w summary |
| `scripts/ifg_guardian/policies/ifg_production.yaml` | **COMMIT** | `score_config`, `policy_rules` ze scope/category/penalty |
| `scripts/ifg_guardian/core/workflow/transaction.py` | **COMMIT** | `elapsed_ms()` — naprawa `Duration: 0 ms` |
| `tests/unit/test_guardian_ifg_release_evaluate_workflow.py` | **COMMIT** | Testy klasyfikacji, duration, local env |
| `docs/reports/2026-07-08_GWO-IFG-0037_RELEASE_ENGINE_QUALITY.md` | **COMMIT** | Raport końcowy GWO-IFG-0037 |

---

## Grupa 3 — Guardian progress / dashboard / workflow (eksperymenty)

**Liczba plików: 54** (22 modified + 32 untracked)

### Modified (22)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `pyproject.toml` | **STASH** | Opcjonalna grupa `guardian` + `rich` — zależność pod live dashboard |
| `scripts/ifg_guardian/config.py` | **STASH** | Konfiguracja pod progress/dashboard |
| `scripts/ifg_guardian/core/deploy_config.py` | **STASH** | Rozszerzenia deploy config (rsync path itp.) |
| `scripts/ifg_guardian/core/frontend_artifacts.py` | **STASH** | Artifact gate / dist freshness |
| `scripts/ifg_guardian/core/workflow/engine.py` | **STASH** | Integracja `progress_tracker`, fazy deploy — poza 0037 |
| `scripts/ifg_guardian/core/workflow/executors/__init__.py` | **STASH** | Rozszerzenia executorów |
| `scripts/ifg_guardian/core/workflow/executors/http_executor.py` | **STASH** | HTTP executor enhancements |
| `scripts/ifg_guardian/core/workflow/executors/local_executor.py` | **STASH** | Local executor enhancements |
| `scripts/ifg_guardian/core/workflow/executors/router.py` | **STASH** | Routing komend deploy |
| `scripts/ifg_guardian/core/workflow/executors/ssh_executor.py` | **STASH** | SSH/rsync improvements |
| `scripts/ifg_guardian/modules/ifg_container_cutover.py` | **STASH** | Progress kwarg forwarding |
| `scripts/ifg_guardian/modules/ifg_doctor.py` | **STASH** | Progress kwarg forwarding |
| `scripts/ifg_guardian/modules/ifg_release_plan.py` | **STASH** | Progress kwarg forwarding |
| `scripts/ifg_guardian/modules/workflow.py` | **STASH** | CLI workflow + duration display |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/report.py` | **STASH** | Timeline w raporcie cutover |
| `scripts/ifg_guardian/plugins/ifg/deploy_run/service.py` | **STASH** | Deploy run service extensions |
| `scripts/ifg_guardian/plugins/ifg/doctor/report.py` | **STASH** | Timeline w raporcie doctor |
| `scripts/ifg_guardian/plugins/ifg/plugin.py` | **STASH** | Rejestracja nowych workflow |
| `scripts/ifg_guardian/plugins/ifg/release_plan/report.py` | **STASH** | Timeline w raporcie release plan |
| `tests/unit/test_guardian_deploy_executors.py` | **STASH** | Testy executorów (powiązane z G3) |
| `tests/unit/test_guardian_frontend_artifacts.py` | **STASH** | Testy artifact gate |
| `tests/unit/test_guardian_plugins_sprint2.py` | **STASH** | Aktualizacja rejestru pluginów |

### Untracked (32)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `scripts/ifg_guardian/core/progress/__init__.py` | **STASH** | Moduł `[GWO_PROGRESS]` protocol |
| `scripts/ifg_guardian/core/progress/mapping.py` | **STASH** | Mapowanie faz → stage |
| `scripts/ifg_guardian/core/progress/protocol.py` | **STASH** | Protokół progress |
| `scripts/ifg_guardian/core/progress/report.py` | **STASH** | Timeline section renderer |
| `scripts/ifg_guardian/core/progress/timeline.py` | **STASH** | Model timeline |
| `scripts/ifg_guardian/core/progress/tracker.py` | **STASH** | Progress tracker |
| `scripts/ifg_guardian/core/dashboard/__init__.py` | **STASH** | Live terminal dashboard |
| `scripts/ifg_guardian/core/dashboard/eta.py` | **STASH** | ETA renderer |
| `scripts/ifg_guardian/core/dashboard/model.py` | **STASH** | Dashboard state model |
| `scripts/ifg_guardian/core/dashboard/parser.py` | **STASH** | Parser GWO_PROGRESS |
| `scripts/ifg_guardian/core/dashboard/renderer.py` | **STASH** | Rich renderer |
| `scripts/ifg_guardian/core/dashboard/session.py` | **STASH** | Live session orchestration |
| `scripts/ifg_guardian/core/dashboard/stderr_sink.py` | **STASH** | Stderr sink |
| `scripts/ifg_guardian/core/execution/__init__.py` | **STASH** | Execution engine v2 (eksperyment) |
| `scripts/ifg_guardian/core/execution/backend.py` | **STASH** | Deployment backend abstraction |
| `scripts/ifg_guardian/core/execution/capability.py` | **STASH** | Capability detection |
| `scripts/ifg_guardian/core/execution/compose_backend.py` | **STASH** | Compose backend |
| `scripts/ifg_guardian/core/execution/deployment_engine.py` | **STASH** | Deployment engine |
| `scripts/ifg_guardian/core/execution/discovery.py` | **STASH** | Operation discovery |
| `scripts/ifg_guardian/core/execution/event_bus.py` | **STASH** | Event bus |
| `scripts/ifg_guardian/core/execution/models.py` | **STASH** | Execution models |
| `scripts/ifg_guardian/core/execution/operation_engine.py` | **STASH** | Operation engine |
| `scripts/ifg_guardian/core/execution/synology_project_backend.py` | **STASH** | Synology project backend |
| `scripts/ifg_guardian/modules/ds723_pull_unblock.py` | **STASH** | DS723 pull unblock helper |
| `scripts/ifg_guardian_frontend_artifact_gate.py` | **STASH** | Standalone artifact gate script |
| `tests/unit/test_guardian_progress_protocol.py` | **STASH** | Testy progress protocol |
| `tests/unit/test_guardian_live_dashboard.py` | **STASH** | Testy live dashboard |
| `tests/unit/test_guardian_dashboard_stderr_sink.py` | **STASH** | Testy stderr sink |
| `docs/architecture/GUARDIAN_LIVE_DASHBOARD.md` | **ARCHIVE** | Dokumentacja eksperymentu dashboard |
| `docs/architecture/GUARDIAN_PROGRESS_PROTOCOL.md` | **ARCHIVE** | Dokumentacja progress protocol |
| `docs/reports/2026-07-07_GUARDIAN_LIVE_DASHBOARD.md` | **ARCHIVE** | Raport implementacji dashboard |
| `docs/reports/2026-07-07_GUARDIAN_PROGRESS_PROTOCOL.md` | **ARCHIVE** | Raport implementacji progress |

**Uwaga:** `transaction.py` należy do **Grupy 2**, nie 3 — jest w commicie 0037.

---

## Grupa 4 — Stare raporty i artefakty dokumentacyjne

**Liczba plików: 85** (wszystkie untracked)

### `docs/` — analizy i plany operacyjne (26)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md` | **ARCHIVE** | Plan FV/WZ — poza deployem KSeF |
| `docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md` | **ARCHIVE** | Analiza numeracji faktur |
| `docs/FV_NUMBERING_RENUMBERING_BUG.md` | **ARCHIVE** | Diagnoza buga numeracji |
| `docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md` | **ARCHIVE** | Review polityki numeracji |
| `docs/FV_WZ_AUTO_SYNC_ANALYSIS.md` | **ARCHIVE** | Analiza sync FV→WZ |
| `docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md` | **ARCHIVE** | Standard operacji długich — docs, nie kod |
| `docs/IFG_PENDING_CHANGES_AUDIT.md` | **REVIEW** | Audyt pending changes — może kolidować z tym planem |
| `docs/KK_CREATION_FIX.md` | **ARCHIVE** | Korekta korekty (KK) |
| `docs/KSEF_PURCHASE_SYNC_429_RESUME_DEPLOY.md` | **ARCHIVE** | Deploy diag purchase sync |
| `docs/KSEF_PURCHASE_SYNC_DIAGNOSTICS_EXTENDED.md` | **ARCHIVE** | Diagnostyka KSeF purchase |
| `docs/KSEF_PURCHASE_SYNC_GAP_ANALYSIS.md` | **ARCHIVE** | Gap analysis purchase sync |
| `docs/PZ_DRAFT_AS_REAL_STOCK_ANALYSIS.md` | **ARCHIVE** | Magazyn PZ draft |
| `docs/PZ_DRAFT_DEPLOY_STAGE2_DIAG.md` | **ARCHIVE** | Deploy diag PZ |
| `docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md` | **ARCHIVE** | Plan wykonania PZ |
| `docs/PZ_DRAFT_EDIT_FIX_DEPLOY_REPORT.md` | **ARCHIVE** | Raport deploy PZ edit |
| `docs/PZ_DRAFT_IMPLEMENTATION_AUDIT_2026_06.md` | **ARCHIVE** | Audyt implementacji PZ |
| `docs/PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md` | **ARCHIVE** | Plan real stock PZ |
| `docs/REPO_CLEANUP_PLAN.md` | **ARCHIVE** | Plan cleanup repo |
| `docs/REPO_HOUSEKEEPING_AUDIT_2026_06.md` | **ARCHIVE** | Audyt housekeeping |
| `docs/UI_DEPLOY_DIAG_2026_06_19.md` | **ARCHIVE** | Diag deploy UI |
| `docs/WAREHOUSE_BALANCE_COST_PENDING_FIX.md` | **ARCHIVE** | Fix salda magazynu |
| `docs/WAREHOUSE_BALANCE_DEPLOY_STATE_DIAG.md` | **ARCHIVE** | Diag deploy magazynu |
| `docs/WAREHOUSE_DOCUMENT_LIST_QTY_FIX.md` | **ARCHIVE** | Fix listy dokumentów |
| `docs/WAREHOUSE_READY_AUDIT_2026_06.md` | **ARCHIVE** | Audyt gotowości magazynu |
| `docs/WAREHOUSE_STOCK_AGGREGATION_UI_FIX.md` | **ARCHIVE** | Fix UI agregacji stanów |
| `docs/WIP_COMMIT_SPLIT_PLAN.md` | **REVIEW** | Plan split commitów — użyć jako input do Etapu A/B |
| `docs/WZ_CREATION_BUG.md` | **ARCHIVE** | Bug tworzenia WZ |

### `docs/guardian/` — artefakty workflow (24)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `docs/guardian/CUTOVER_PRECHECK_2026_07_06.md` | **ARCHIVE** | Output Guardian cutover |
| `docs/guardian/CUTOVER_PRECHECK_2026_07_07.md` | **ARCHIVE** | j.w. |
| `docs/guardian/EOL_CHECK_2026_07_06.md` | **ARCHIVE** | Output EOL check |
| `docs/guardian/IFG_CONTAINER_CUTOVER_2026_07_06.md` | **ARCHIVE** | Output cutover |
| `docs/guardian/IFG_CONTAINER_CUTOVER_2026_07_07.md` | **ARCHIVE** | j.w. |
| `docs/guardian/IFG_DEPLOY_RUN_2026_06_26.md` | **ARCHIVE** | Output deploy run |
| `docs/guardian/IFG_DEPLOY_RUN_2026_07_05.md` | **ARCHIVE** | j.w. |
| `docs/guardian/IFG_DEPLOY_RUN_2026_07_07.md` | **ARCHIVE** | j.w. |
| `docs/guardian/IFG_DOCTOR_2026_06_26.md` | **ARCHIVE** | Output doctor |
| `docs/guardian/IFG_DOCTOR_2026_07_05.md` | **ARCHIVE** | j.w. |
| `docs/guardian/IFG_DOCTOR_2026_07_07.md` | **ARCHIVE** | j.w. |
| `docs/guardian/IFG_RELEASE_EVALUATE_2026_07_07.md` | **ARCHIVE** | Output release evaluate |
| `docs/guardian/IFG_RELEASE_PLAN_2026_06_26.md` | **ARCHIVE** | Output release plan |
| `docs/guardian/IFG_RELEASE_PLAN_2026_07_05.md` | **ARCHIVE** | j.w. |
| `docs/guardian/IFG_RELEASE_PLAN_2026_07_07.md` | **ARCHIVE** | j.w. |
| `docs/guardian/PRECHECK_REPORT_2026_07_05.md` | **ARCHIVE** | Output preflight |
| `docs/guardian/PRECHECK_REPORT_2026_07_07.md` | **ARCHIVE** | j.w. |
| `docs/guardian/REPO_AUDIT_2026_06_26.md` | **ARCHIVE** | Output repo audit |
| `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md` | **ARCHIVE** | Output cleanup plan |
| `docs/guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md` | **ARCHIVE** | Architektura deploy backend |
| `docs/guardian/core/GUARDIAN_CORE_STATUS.md` | **ARCHIVE** | Status core |
| `docs/guardian/core/GUARDIAN_RELEASE_WORKFLOW.md` | **ARCHIVE** | Design release workflow |
| `docs/guardian/core/GUARDIAN_VISION.md` | **ARCHIVE** | Vision doc |
| `docs/guardian/core/REPOSITORY_TARGET_STATE.md` | **ARCHIVE** | Target state repo |

### `docs/reports/` — raporty historyczne (37)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `docs/reports/2026-07-06_EOL_VERIFICATION_BEFORE_PUSH.md` | **ARCHIVE** | Raport historyczny |
| `docs/reports/2026-07-06_GUARDIAN_ARCHITECTURE_REVIEW_V1.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_GUARDIAN_LOCAL_REMOTE_EXECUTION.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_GUARDIAN_PYTHON38_COMPATIBILITY.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_GUARDIAN_RELEASE_WORKFLOW_DESIGN.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_GUARDIAN_VISION_DESIGN.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_IFG_502_AFTER_PULL_DIAG.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_IFG_DS723_PULL_UNBLOCK_AND_DRY_RUN.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_IFG_INDEX_HTML_CUTOVER_DEPLOY_VERIFY.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_IFG_PROJECT_CONTAINER_FINAL_PRE_PUSH.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-06_REPOSITORY_TARGET_STATE_DESIGN.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-07_CONTAINER_MANAGER_PROJECT_UI_ADOPTION.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-07_GWO-IFG-0034_POST_DEPLOY_VERIFICATION.md` | **ARCHIVE** | Weryfikacja deploy — wartościowy archiwum |
| `docs/reports/2026-07-07_GWO_IFG_002A_CONTAINER_CUTOVER_CLOSED.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-07_KSEF_SCHEDULER_PRODUCTION_DEPLOY.md` | **ARCHIVE** | j.w. |
| `docs/reports/2026-07-07_KSEF_TRANSMISSIONS_UI_REGRESSION.md` | **ARCHIVE** | Diagnoza regresji — kontekst 0036 |
| `docs/reports/GUARDIAN_ARTIFACT_GATE_FIX.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_CANON_REVIEW_2026-07-06.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE_UPDATE.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_DEPLOY_DIAGNOSTICS_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_DEPLOY_GATE_UNIFICATION_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_POLICY_ENGINE_V1_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_POLICY_SEMANTICS_FIX.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_RELEASE_ENGINE_V1_DESIGN.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_RELEASE_UNBLOCK_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_RSYNC_ROOT_CAUSE.md` | **ARCHIVE** | j.w. |
| `docs/reports/GUARDIAN_SINGLE_PRODUCTION_PROFILE_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/GWO_G003B_STATUS_SEMANTICS.md` | **ARCHIVE** | j.w. |
| `docs/reports/GWO_G003_IMPLEMENTATION_STAGE1.md` | **ARCHIVE** | j.w. |
| `docs/reports/IFG_DEPLOY_LIVE_FAILED_STEP_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/IFG_KSEF_MONITOR_DS723_DEPLOY_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/IFG_KSEF_MONITOR_FINAL_DEPLOY_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/IFG_KSEF_MONITOR_GO_LIVE_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/IFG_PRODUCTION_STABILIZATION_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/IFG_TEST_DISCOVERY_FIX.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_MONITOR_AND_AUTOSYNC_DEPLOY_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_MONITOR_GUARDIAN_PRE_DEPLOY_AUDIT.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_MONITOR_GUARDIAN_PRE_DEPLOY_AUDIT_DOCTOR.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_MONITOR_IMPLEMENTATION_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_MONITOR_PRODUCTION_DEPLOY_REPORT.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_STABILIZATION_SPRINT.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_TRANSMISSIONS_FULL_LOG_AUDIT.md` | **ARCHIVE** | j.w. |
| `docs/reports/KSEF_TRANSMISSIONS_UNIFIED_JOURNAL_PLAN.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2026.md` | **ARCHIVE** | Log deploy (26 wpisów guardian_deploy/recover — generated) |
| `docs/reports/guardian_deploy_20260626_2027.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2044.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2106.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2113.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2114.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2115.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2116.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2118.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2132.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260626_2143.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260705_2043.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260707_1036.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_deploy_20260707_1038.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2026.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2027.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2028.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2044.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2106.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2114.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2115.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2116.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2117.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2118.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2132.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260626_2143.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260705_2043.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260707_1037.md` | **ARCHIVE** | j.w. |
| `docs/reports/guardian_recover_20260707_1038.md` | **ARCHIVE** | j.w. |
| `docs/reports/repository_cleanup_execution.md` | **ARCHIVE** | j.w. |
| `docs/reports/repository_cleanup_plan.md` | **ARCHIVE** | j.w. |
| `docs/reports/repository_dead_code.md` | **ARCHIVE** | j.w. |
| `docs/reports/repository_graph.md` | **ARCHIVE** | j.w. |
| `docs/reports/repository_orphans.md` | **ARCHIVE** | j.w. |

**Rekomendacja zbiorcza dla Grupy 4:** jeden commit `docs: archive guardian and warehouse reports` **lub** dodanie `docs/guardian/` i części `docs/reports/guardian_*` do `.gitignore` (artefakty generowane).

---

## Grupa 5 — Zmiany magazynowe / fakturowe (niezwiązane z deployem KSeF)

**Liczba plików: 7** (6 modified + 1 untracked)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `app/persistence/mappers/invoice_mapper.py` | **STASH** | Po `--ignore-cr-at-eol` brak diffu merytorycznego — szum CRLF |
| `app/persistence/models/invoice.py` | **STASH** | j.w. |
| `app/services/invoice_number_policy.py` | **STASH** | j.w. |
| `app/services/payment_service.py` | **STASH** | j.w. |
| `frontend-react/src/api/invoices.js` | **STASH** | j.w. |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | **STASH** | j.w. |
| `frontend-react/vite.config.js` | **STASH** | j.w. |
| `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | **STASH** | Test numeracji na liście faktur — temat FV/PZ, nie KSeF deploy |

**Rekomendacja operacyjna:** `git checkout --` na 6 plikach CRLF **przed** przejściem na `feature/gos-foundation`, chyba że operator potwierdzi ukryte zmiany.

---

## Grupa 6 — Pliki niepewne / wymagające decyzji operatora

**Liczba plików: 3** (+ `transmission_repository` z Grupy 1)

| Plik | Rekomendacja | Uzasadnienie |
|------|--------------|--------------|
| `scripts/ds723.env` | **REVIEW** | Dodany `DS723_REMOTE_RSYNC_PATH=/bin/rsync` — wpływa na deploy DS723; commitować z G3 czy osobno? |
| `app/persistence/repositories/transmission_repository.py` | **REVIEW** | Tylko whitespace — odrzucić czy normalizować EOL? |
| `docs/IFG_PENDING_CHANGES_AUDIT.md` | **REVIEW** | Może być nieaktualny względem tego planu |
| `docs/WIP_COMMIT_SPLIT_PLAN.md` | **REVIEW** | Wcześniejszy plan split — zweryfikować vs GWO-IFG-0038 |

---

## Podsumowanie liczbowe

| Grupa | Opis | Plików |
|-------|------|--------|
| **1** | GWO-IFG-0036 resztki | **5** |
| **2** | GWO-IFG-0037 Release Engine Quality | **12** |
| **3** | Guardian progress/dashboard/workflow | **54** |
| **4** | Raporty i artefakty docs | **85** |
| **5** | Magazyn / faktury (CRLF + test) | **7** |
| **6** | Niepewne / REVIEW | **4** |
| | **Razem** | **165** |

*(Grupa 6 zawiera `transmission_repository` liczony też w kontekście Grupy 1 — w sumie 165 unikalnych pozycji w `git status`)*

---

## Plan dojścia do clean working tree

### Etap A — Commitować teraz na `production`

**Kolejność commitów (rekomendowana):**

1. **`fix(ksef): GWO-IFG-0036 monitor UI remnants`**
   - `frontend-react/src/pages/advanced/AdvancedDashboard.jsx`
   - `frontend-react/src/api/transmissions.js`
   - `frontend-react/src/components/dashboard/TransmissionTable.module.css`
   - `frontend-react/src/components/common/StatusBadge.jsx`
   - *(opcjonalnie odrzucić `transmission_repository.py` przed commitem)*

2. **`feat(guardian): GWO-IFG-0037 release engine quality`**
   - Cała Grupa 2 (12 plików)
   - Uruchomić: `pytest tests/unit/test_guardian_ifg_release_evaluate_workflow.py`

**Efekt Etapu A:** ~17 plików kodu + 1 raport zcommitowanych; HEAD gotowy do deploy evaluate.

### Etap B — Odłożyć do stash / osobny branch

**Branch proponowany:** `feature/guardian-progress-dashboard` (z `production` po Etapie A)

- Cała **Grupa 3** (54 pliki) — progress, dashboard, execution engine, rich, executors
- **Grupa 5** (7 plików) — jeśli po review CRLF nie ma merytoryki → `git checkout --` zamiast stash

**Komenda (propozycja, nie wykonywana):**
```bash
git stash push -u -m "G3 guardian progress dashboard" -- scripts/ifg_guardian/core/progress scripts/ifg_guardian/core/dashboard ...
# lub
git checkout -b feature/guardian-progress-dashboard
git add scripts/ifg_guardian/core/{progress,dashboard,execution} ...
```

### Etap C — Osobny audyt / archiwum

- **Grupa 4** (85 plików docs) — commit archiwizacyjny `docs:` **lub** `.gitignore` dla generowanych `docs/guardian/IFG_*`
- **Grupa 6** — decyzja operatora dla `ds723.env` i planów WIP
- Artefakty `.guardian/` (poza tym `git status`) — już ignorowane; nie blokują clean tree

**Efekt końcowy clean tree:**
```
git status → clean (po A + B + checkout CRLF + opcjonalnie gitignore docs)
```

---

## Czy można bezpiecznie przejść na `feature/gos-foundation`?

| Warunek | Status |
|---------|--------|
| Po Etapie A (0036 remnants + 0037) | ✅ Kod produkcyjny KSeF/Guardian policy domknięty |
| Po Etapie B (stash G3) | ✅ Brak mieszania eksperymentów z GOS |
| Po odrzuceniu CRLF (Grupa 5) | ✅ Brak fałszywych diffów magazynowych |
| Grupa 4 (docs) | ⚠️ Nie blokuje checkout brancha, ale zaśmieca `git status` — rozwiązać przez ARCHIVE lub gitignore |
| `ds723.env` (Grupa 6) | ⚠️ Zdecydować przed deployem |

### Werdykt

**NIE TERAZ** — przy 165 dirty plikach checkout `feature/gos-foundation` jest ryzykowny (konflikty, przypadkowe przeniesienie zmian).

**TAK, BEZPIECZNIE PO:**
1. Etap A (2 commity),
2. Etap B (stash/branch G3),
3. `git checkout --` na plikach CRLF Grupy 5,
4. Etap C (docs — commit archiwum lub gitignore).

Szacowany czas do clean tree: **~30–45 min** pracy operatora (bez deployu).

---

## Wykonane analizy

- `git status --porcelain` (165 pozycji)
- `git show a8410f3 --stat` — zakres już zcommitowanego GWO-IFG-0036
- `git diff HEAD --ignore-cr-at-eol` — odróżnienie CRLF od zmian merytorycznych
- Przegląd untracked `scripts/ifg_guardian/core/{progress,dashboard,execution}/`
- Mapowanie plików docs → kategorie operacyjne

## Decyzja GWO-IFG-0038

### READY (jako plan normalizacji)

Plan jest kompletny i gotowy do wykonania przez operatora.  
**Nie wykonano żadnej mutacji repo** zgodnie z zakresem zadania.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Pełna klasyfikacja 165 plików w 6 grupach
- Plan Etap A / B / C z kolejnością commitów
- Rozróżnienie CRLF vs zmiany merytoryczne

⚠️ Znane problemy
- GWO-IFG-0036 częściowo na HEAD, resztki UI w working tree
- GWO-IFG-0037 w dużej części untracked mimo related commit na HEAD
- 85 plików docs zaśmieca status

❌ Co nie działa
- Clean working tree — **nieosiągalny bez wykonania planu**

**Następny krok:** operator wykonuje Etap A (2 commity), potem Etap B (branch `feature/guardian-progress-dashboard`).
