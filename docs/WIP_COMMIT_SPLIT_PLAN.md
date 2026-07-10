# WIP Commit Split Plan

**Data:** 2026-05-22  
**Cel:** uporządkowanie WIP po zamknięciu rozwoju Guardian Platform, przed cleanup repo IFG.  
**Stan źródłowy:** `git status --short` (83 wpisy top-level; ~300+ plików z rozwinięciem katalogów).

---

## Podsumowanie

| Metryka | Wartość |
|---------|---------|
| Proponowane commity | **7** |
| Pliki do pominięcia | **~200+** (`.guardian/`, `__pycache__`, raporty deploy/recover) |
| Pliki wymagające review | **14** (patrz sekcja Review) |
| Funkcjonalne zmiany IFG app | **brak** (tylko CRLF + 1 nowy test frontend) |

---

## Proponowane commity (kolejność)

| # | Commit (propozycja) | Zakres | Pliki (~) |
|---|---------------------|--------|-----------|
| **C1** | `feat(guardian): add Guardian Platform with IFG profile, repo graph, cleanup advisor` | Core platform + profil IFG | 113 |
| **C2** | `feat(guardian): extend legacy ifg_guardian with workflow engine and plugins` | Legacy entry point (`scripts/guardian.py` path) | ~80 |
| **C3** | `test(guardian): add Guardian Platform and legacy workflow tests` | Testy platformy + legacy | 27 |
| **C4** | `docs(guardian): add Guardian Platform implementation and operational docs` | Dokumentacja Guardiana | 33 |
| **C5** | `docs(ifg): add FV, PZ, warehouse and housekeeping audit notes` | Dokumentacja domenowa IFG | 22 |
| **C6** | `test(ifg): add invoice card list numbering regression test` | Test frontend IFG | 1 |
| **C7** | `chore: normalize CRLF to LF in app and frontend-react` *(opcjonalny)* | Line endings bez zmian logicznych | 10 |

**Opcjonalny C8** (niezalecany): `docs(reports): add guardian repo graph and cleanup snapshots` — tylko `docs/reports/repository_*.md` + `docs/guardian/REPO_*.md`. Reszty `docs/reports/guardian_deploy_*` **nie commitować**.

---

## C1 — Guardian Platform + profil IFG + Repo Graph + Cleanup Advisor

| Plik | Commit |
|------|--------|
| `scripts/guardian_platform/**` (111 plików `.py`, bez `__pycache__`) | C1 |
| `scripts/__init__.py` | C1 |
| `.guardian.yml` | C1 |

**Zakres:** CLI, core (config, git, workflow, registry), `core/repository/*` (Repo Graph v1/v1.1), profil IFG (doctor, deploy, recover, repo audit, **repo cleanup advisor**), scaffold PSAG/IFG.

**Wykluczyć ze stagingu:** `scripts/guardian_platform/**/__pycache__/**` (~110 plików `.pyc`).

---

## C2 — Legacy Guardian (`scripts/ifg_guardian`)

| Plik | Commit |
|------|--------|
| `scripts/ifg_guardian/cli.py` *(M)* | C2 |
| `scripts/ifg_guardian/modules/doctor.py` *(M)* | C2 |
| `scripts/ifg_guardian/modules/repo.py` *(M)* | C2 |
| `scripts/ifg_guardian/core/deploy_config.py` | C2 |
| `scripts/ifg_guardian/core/plugins/**` | C2 |
| `scripts/ifg_guardian/core/repo_audit/**` | C2 |
| `scripts/ifg_guardian/core/workflow/**` | C2 |
| `scripts/ifg_guardian/modules/ifg_deploy_run.py` | C2 |
| `scripts/ifg_guardian/modules/ifg_doctor.py` | C2 |
| `scripts/ifg_guardian/modules/ifg_release_plan.py` | C2 |
| `scripts/ifg_guardian/modules/plugins.py` | C2 |
| `scripts/ifg_guardian/modules/repo_audit.py` | C2 |
| `scripts/ifg_guardian/modules/workflow.py` | C2 |
| `scripts/ifg_guardian/plugins/**` | C2 |

**Uwaga:** większość drzewa `ifg_guardian` jest już śledzona w Git (21 plików tracked); nowe katalogi to głównie Sprint 1–5 (workflow engine, plugins, repo audit). `repo.py` ma duży diff (−382 linii) — wymaga review przed commitem.

---

## C3 — Testy Guardiana

| Plik | Commit |
|------|--------|
| `tests/guardian_platform/conftest.py` | C3 |
| `tests/guardian_platform/test_cli.py` | C3 |
| `tests/guardian_platform/test_config.py` | C3 |
| `tests/guardian_platform/test_core_ping.py` | C3 |
| `tests/guardian_platform/test_deploy_run.py` | C3 |
| `tests/guardian_platform/test_ifg_mutating.py` | C3 |
| `tests/guardian_platform/test_ifg_profile.py` | C3 |
| `tests/guardian_platform/test_loader.py` | C3 |
| `tests/guardian_platform/test_m3_coverage.py` | C3 |
| `tests/guardian_platform/test_prod_recover.py` | C3 |
| `tests/guardian_platform/test_profiles.py` | C3 |
| `tests/guardian_platform/test_psag_profile.py` | C3 |
| `tests/guardian_platform/test_registry.py` | C3 |
| `tests/guardian_platform/test_regression.py` | C3 |
| `tests/guardian_platform/test_repo_cleanup_advisor.py` | C3 |
| `tests/guardian_platform/test_reporting.py` | C3 |
| `tests/guardian_platform/test_repository_graph.py` | C3 |
| `tests/guardian_platform/test_repository_protected.py` | C3 |
| `tests/guardian_platform/test_runtime.py` | C3 |
| `tests/guardian_platform/test_workflow.py` | C3 |
| `tests/unit/test_guardian_deploy_executors.py` | C3 |
| `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | C3 |
| `tests/unit/test_guardian_ifg_doctor_workflow.py` | C3 |
| `tests/unit/test_guardian_ifg_release_plan_workflow.py` | C3 |
| `tests/unit/test_guardian_plugins_sprint2.py` | C3 |
| `tests/unit/test_guardian_repo_audit_workflow.py` | C3 |
| `tests/unit/test_guardian_workflow_engine.py` | C3 |

**Baseline:** 301 testów platformy (`pytest tests/guardian_platform/`).

---

## C4 — Dokumentacja Guardiana

| Plik | Commit |
|------|--------|
| `docs/GUARDIAN_CORE_PROFILE_SPLIT.md` | C4 |
| `docs/GUARDIAN_DEPLOY_ORCHESTRATOR.md` | C4 |
| `docs/GUARDIAN_IFG_PROFILE_M1_READONLY.md` | C4 |
| `docs/GUARDIAN_IFG_PROFILE_M2_NATIVE.md` | C4 |
| `docs/GUARDIAN_IFG_PROFILE_M3_MUTATING.md` | C4 |
| `docs/GUARDIAN_IFG_REPOSITORY_CLEANUP_ADVISOR.md` | C4 |
| `docs/GUARDIAN_PLATFORM_ARCHITECTURE.md` | C4 |
| `docs/GUARDIAN_PLATFORM_CORE_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_PLATFORM_TESTS.md` | C4 |
| `docs/GUARDIAN_PZ_DRAFT_DEPLOY_DIAG.md` | C4 |
| `docs/GUARDIAN_REPOSITORY_CLEANUP_FINAL.md` | C4 |
| `docs/GUARDIAN_REPOSITORY_GRAPH_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_REPOSITORY_GRAPH_V1_1.md` | C4 |
| `docs/GUARDIAN_SPRINT1_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_SPRINT2_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_SPRINT3_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_SPRINT4_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_SPRINT5A_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_SPRINT5B_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_SPRINT5C_IMPLEMENTATION.md` | C4 |
| `docs/GUARDIAN_V1_RELEASE.md` | C4 |
| `docs/GUARDIAN_WORKFLOW_ENGINE.md` | C4 |
| `docs/REPO_CLEANUP_PLAN.md` | C4 |
| `docs/WORKFLOW.md` *(M — sekcja Guardian V1)* | C4 |

**Uwaga:** `docs/WORKFLOW.md` łączy workflow IFG i Guardiana — review przed commitem (patrz Review).

---

## C5 — Dokumentacja domenowa IFG (FV / PZ / magazyn / audyty)

| Plik | Commit |
|------|--------|
| `docs/FV_AUTO_WZ_IMPLEMENTATION_PLAN.md` | C5 |
| `docs/FV_DRAFT_LOCKED_NUMBERING_MODEL.md` | C5 |
| `docs/FV_NUMBERING_RENUMBERING_BUG.md` | C5 |
| `docs/FV_STATUS_NUMBERING_POLICY_REVIEW.md` | C5 |
| `docs/FV_WZ_AUTO_SYNC_ANALYSIS.md` | C5 |
| `docs/KK_CREATION_FIX.md` | C5 |
| `docs/PZ_DRAFT_AS_REAL_STOCK_ANALYSIS.md` | C5 |
| `docs/PZ_DRAFT_DEPLOY_STAGE2_DIAG.md` | C5 |
| `docs/PZ_DRAFT_E1_E5_EXECUTION_PLAN.md` | C5 |
| `docs/PZ_DRAFT_EDIT_FIX_DEPLOY_REPORT.md` | C5 |
| `docs/PZ_DRAFT_IMPLEMENTATION_AUDIT_2026_06.md` | C5 |
| `docs/PZ_DRAFT_REAL_STOCK_IMPLEMENTATION_PLAN.md` | C5 |
| `docs/REPO_HOUSEKEEPING_AUDIT_2026_06.md` | C5 |
| `docs/UI_DEPLOY_DIAG_2026_06_19.md` | C5 |
| `docs/WAREHOUSE_BALANCE_COST_PENDING_FIX.md` | C5 |
| `docs/WAREHOUSE_BALANCE_DEPLOY_STATE_DIAG.md` | C5 |
| `docs/WAREHOUSE_DOCUMENT_LIST_QTY_FIX.md` | C5 |
| `docs/WAREHOUSE_READY_AUDIT_2026_06.md` | C5 |
| `docs/WAREHOUSE_STOCK_AGGREGATION_UI_FIX.md` | C5 |
| `docs/WZ_CREATION_BUG.md` | C5 |

---

## C6 — Test IFG (frontend)

| Plik | Commit |
|------|--------|
| `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` | C6 |

Test regresji numeracji faktur (`ui:temporary_sequence` / `backend:number_local`).

---

## C7 — Line endings (opcjonalny, alternatywa: revert)

| Plik | Commit |
|------|--------|
| `app/api/deps.py` *(M)* | C7 lub **POMIŃ** |
| `app/domain/enums.py` *(M)* | C7 lub **POMIŃ** |
| `app/persistence/mappers/invoice_mapper.py` *(M)* | C7 lub **POMIŃ** |
| `app/persistence/models/invoice.py` *(M)* | C7 lub **POMIŃ** |
| `app/persistence/repositories/transmission_repository.py` *(M)* | C7 lub **POMIŃ** |
| `app/services/invoice_number_policy.py` *(M)* | C7 lub **POMIŃ** |
| `app/services/payment_service.py` *(M)* | C7 lub **POMIŃ** |
| `frontend-react/src/api/invoices.js` *(M)* | C7 lub **POMIŃ** |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` *(M)* | C7 lub **POMIŃ** |
| `frontend-react/vite.config.js` *(M)* | C7 lub **POMIŃ** |

**Analiza:** `git diff -w` dla wszystkich powyższych plików = **0 zmian logicznych** (wyłącznie CRLF→LF).  
**Rekomendacja:** `git checkout -- app/ frontend-react/` przed stagingiem **albo** osobny commit `chore:` — nie mieszać z C6.

---

## Pliki do pominięcia (nie commitować)

| Plik / katalog | Powód |
|----------------|-------|
| `.guardian/` | Runtime workflow state; już w `.gitignore` (linia 45) |
| `scripts/guardian_platform/**/__pycache__/**` | Cache Pythona |
| `docs/reports/guardian_deploy_20260626_*.md` (14 plików) | Raporty LIVE deploy — artefakty sesji |
| `docs/reports/guardian_recover_20260626_*.md` (12 plików) | Raporty recover — artefakty sesji |
| `docs/reports/repository_cleanup_execution.md` | Generowany przez `ifg repo cleanup` |
| `docs/reports/repository_cleanup_plan.md` | Generowany przez `ifg repo cleanup` |
| `docs/reports/repository_dead_code.md` | Generowany przez `ifg repo graph` |
| `docs/reports/repository_graph.md` | Generowany przez `ifg repo graph` |
| `docs/reports/repository_orphans.md` | Generowany przez `ifg repo graph` |
| `docs/guardian/IFG_DEPLOY_RUN_2026_06_26.md` | Snapshot sesji *(opcjonalnie C8)* |
| `docs/guardian/IFG_DOCTOR_2026_06_26.md` | Snapshot sesji *(opcjonalnie C8)* |
| `docs/guardian/IFG_RELEASE_PLAN_2026_06_26.md` | Snapshot sesji *(opcjonalnie C8)* |
| `docs/guardian/REPO_AUDIT_2026_06_26.md` | Snapshot sesji *(opcjonalnie C8)* |
| `docs/guardian/REPO_CLEANUP_PLAN_2026_06_26.md` | Duplikat/stare wyjście advisor |

**Sugestia:** dodać do `.gitignore`: `docs/reports/guardian_*.md`, `docs/reports/repository_*.md` (opcjonalnie całe `docs/reports/` poza `.gitkeep`).

---

## Pliki wymagające review

| Plik | Powód | Rekomendacja |
|------|-------|--------------|
| `app/api/deps.py` | Duży diff stat, 0 logiczny (`-w`) | Revert lub C7 |
| `app/domain/enums.py` | j.w. | Revert lub C7 |
| `app/persistence/mappers/invoice_mapper.py` | j.w. | Revert lub C7 |
| `app/persistence/models/invoice.py` | j.w. | Revert lub C7 |
| `app/persistence/repositories/transmission_repository.py` | j.w. | Revert lub C7 |
| `app/services/invoice_number_policy.py` | j.w. | Revert lub C7 |
| `app/services/payment_service.py` | 626 linii diff stat, 0 logiczny | Revert lub C7 |
| `frontend-react/src/api/invoices.js` | j.w. | Revert lub C7 |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | j.w. | Revert lub C7 |
| `frontend-react/vite.config.js` | j.w. | Revert lub C7 |
| `docs/WORKFLOW.md` | +136 linii — sekcja Guardian V1 w dokumencie IFG | Review treści; commit w C4 |
| `scripts/ifg_guardian/modules/repo.py` | −382 linii — delegacja do repo audit? | Review przed C2 |
| `.guardian.yml` | Nowa konfiguracja platformy | Commit w C1; sprawdź `reports_dir` |
| `docs/REPO_CLEANUP_PLAN.md` | Duży artefakt audytu (205 kandydatów) | Commit w C4; upewnij się, że nie zawiera sekretów |

---

## Ryzyka

| Ryzyko | Wpływ | Mitigacja |
|--------|-------|-----------|
| **CRLF noise w app/frontend** | Sztucznie powiększone diffy, konflikty merge | Revert przed commitem lub izolowany C7 |
| **Mieszanie legacy + platform** | Trudny rollback, nieczytelna historia | Trzymać C1 i C2 osobno (jak w planie) |
| **Commit testów bez kodu** | C3 przed C1/C2 zepsuje CI | Kolejność: C1 → C2 → C3 |
| **Generated reports w repo** | Zaśmiecanie, stale snapshots | Pominąć; dodać gitignore |
| **`repo.py` legacy refactor** | Możliwa regresja `scripts/guardian.py` | Review + `pytest tests/unit/test_guardian_*` przed pushem |
| **`WORKFLOW.md` dual-purpose** | Dokumentacja IFG vs Guardian | Akceptowalne jeśli sekcje wyraźnie oddzielone |
| **Brak funkcjonalnych zmian IFG app** | Commit C6 samotny (1 plik test) | OK — mały, czytelny commit |
| **Duży C1 (~113 plików)** | Duży review | Akceptowalne — spójna jednostka „Guardian Platform v1” |

---

## Procedura staging (gdy zatwierdzony plan)

```bash
# 0. Opcjonalnie: wyczyść szum CRLF
git checkout -- app/ frontend-react/

# 1. Guardian Platform
git add scripts/guardian_platform/ scripts/__init__.py .guardian.yml
git add scripts/guardian_platform -u  # tylko jeśli tracked
# upewnij się: git diff --cached --name-only | grep __pycache__  → pusto

# 2. Legacy guardian
git add scripts/ifg_guardian/

# 3. Testy
git add tests/guardian_platform/ tests/unit/test_guardian_*.py

# 4–6. Dokumentacja i test IFG — osobno per commit
```

**Po każdym commicie:** `pytest tests/guardian_platform/` (C1–C3), pełny suite przed pushem.

---

## Decyzja: czy można przejść do staging/commit?

| Warunek | Status |
|---------|--------|
| Plan podziału gotowy | ✔ |
| Pliki sklasyfikowane | ✔ |
| Ryzyka zidentyfikowane | ✔ |
| Review CRLF-only plików | **⏳ wymagane** |
| Review `repo.py` + `WORKFLOW.md` | **⏳ wymagane** |
| `.guardian/` / `__pycache__` wykluczone | ✔ (gitignore / ręcznie) |

**Werdykt:** można przejść do **stagingu commitów C1–C6** po krótkim review (CRLF revert + `repo.py`). **Nie commitować** raportów deploy/recover ani `docs/reports/repository_*` bez świadomej decyzji.

---

*Ten dokument (WIP_COMMIT_SPLIT_PLAN.md) commitować na końcu jako C4 lub osobny commit meta po wykonaniu podziału.*
