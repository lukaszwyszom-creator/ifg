# GWO-IFG-0037 — Release Engine Quality

**Data:** 2026-07-08  
**Branch:** `production`  
**Zakres:** jakość diagnostyki Release Engine (bez nowych funkcji deploy, bez zmian architektury Guardiana)

---

## 1. Opis zmian

### A. Classification Engine

Wprowadzono moduł `classification.py` z jednoznaczną kategoryzacją każdego znaleziska:

| Kategoria | Znaczenie |
|-----------|-----------|
| **BLOCKERS** | Blokuje release — problem projektu lub polityki |
| **WARNINGS** | Wymaga uwagi, nie blokuje samoistnie |
| **LOCAL ENVIRONMENT** | Ograniczenie lokalnej maszyny (interpreter, PATH, brak narzędzi) |
| **INFORMATION** | Sygnały pozytywne, wymagane akcje informacyjne |

Każde znalezisko ma też **scope**: `PROJECT`, `ENVIRONMENT`, `CONFIGURATION`, `POLICY`.

### B. Local Environment Detection

**Diagnoza problemu** (`No module named pytest`, `No module named psycopg`, brak `alembic`):

| Przyczyna | Werdykt |
|-----------|---------|
| `subprocess` używa `sys.executable` | Poprawne — dziedziczy aktywny interpreter |
| Guardian uruchomiony bez `.venv` | **Lokalne środowisko** — nie wina projektu |
| `alembic` wywoływany jako binarka w PATH | Brak w PATH lokalnie — **lokalne środowisko** |
| `psycopg` import w doctor | Brak pakietu w aktywnym venv — **lokalne środowisko** |

**Zmiana zachowania:**
- `test_discovery_local_env=True` gdy błąd pasuje do wzorca lokalnego → **nie blokuje** regułą `tests_must_pass`
- Checki doctor (alembic, psycopg) z błędami środowiskowymi → sekcja **LOCAL ENVIRONMENT**, nie BLOCKERS

### C. Duration

**Root cause `Duration: 0 ms`:** raport zapisywany w `SummaryStage` **przed** `transaction.mark_ended()`.

**Naprawa:**
- `WorkflowTransaction.elapsed_ms()` — liczy czas od `started_at` do `ended_at` lub „teraz”
- `SummaryStage` odświeża `duration_ms` przed renderem raportu
- `mark_ended()` używa `elapsed_ms()`

**Dowód:** live evaluate pokazuje `Duration: 20157 ms` (wcześniej `0 ms`).

### D. Policy Engine — klasyfikacja reguł

Wszystkie reguły w `ifg_production.yaml` → sekcja `policy_rules` z polami:

```json
"scope": "PROJECT|ENVIRONMENT|CONFIGURATION|POLICY",
"category": "BLOCKER|WARNING|INFORMATION",
"penalty": 0
```

### E. Release Score — konfiguracja z polityki

Usunięto twarde wartości z kodu. Konfiguracja w `score_config`:

```json
"rule_penalties": {
  "dirty_tree_build_with_override": 25,
  "tests_must_pass": 40
},
"status_penalties": { "WARN": 20, "FAIL": 45, "CRITICAL": 70 },
"component_scores": { "tests_failed": 35, ... }
```

`get_rule_penalty()` odczytuje kary z `policy_rules.penalty`, `score_config.rule_penalties` lub `dirty_tree_policy.score_penalty`.

### F. Executive Summary

Raport kończy się (i zaczyna w markdown) podsumowaniem:

```
Project status:           BLOCKED | READY | WARNING
Environment status:       WARNING | READY
Policy status:            PASS | WARN | BLOCK
Deployment recommendation: READY_WITH_WARNINGS | ...
```

Operator po ~10 s wie: problem projektu vs własnego środowiska.

---

## 2. Nowy model klasyfikacji

```
Doctor checks / Policy rules / Test discovery / Deploy check
        ↓
  classify_doctor_check() / finalize_classification()
        ↓
┌─────────────┬──────────────┬───────────────────┬───────────────┐
│  BLOCKERS   │  WARNINGS    │ LOCAL ENVIRONMENT │ INFORMATION   │
└─────────────┴──────────────┴───────────────────┴───────────────┘
        ↓
   StatusSummary (project / environment / policy)
```

---

## 3. Zmodyfikowane reguły Policy Engine

| Reguła | Scope | Category | Penalty |
|--------|-------|----------|---------|
| `dirty_working_tree_blocks_production` | POLICY | BLOCKER | 0 |
| `dirty_tree_build_with_override` | POLICY | WARNING | 25 |
| `tests_must_pass` | PROJECT | BLOCKER | 40 |
| `frontend_change_requires_passing_build` | PROJECT | BLOCKER | 0 |
| `suspicious_untracked_files_block` | POLICY | BLOCKER | 0 |
| `doctor_hard_block_check` | CONFIGURATION | BLOCKER | 0 |
| `alembic_changes_require_staging` | PROJECT | WARNING | 0 |
| `backend_change_requires_api_worker_rebuild` | PROJECT | INFORMATION | 0 |
| … | … | … | … |

Pełna lista: `scripts/ifg_guardian/policies/ifg_production.yaml`

---

## 4. Zmodyfikowane pliki

- `scripts/ifg_guardian/plugins/ifg/release_evaluate/classification.py` *(nowy)*
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/models.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/service.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/policy_engine.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/stages.py`
- `scripts/ifg_guardian/plugins/ifg/release_evaluate/report.py`
- `scripts/ifg_guardian/core/workflow/transaction.py`
- `scripts/ifg_guardian/policies/ifg_production.yaml`
- `tests/unit/test_guardian_ifg_release_evaluate_workflow.py`

---

## 5. Wyniki testów

```text
pytest tests/unit/test_guardian_ifg_release_evaluate_workflow.py -q
13 passed in 0.14s
```

Nowe testy:
- `TestClassificationEngine` — wykrywanie lokalnego środowiska, brak blokady przy braku pytest
- `TestWorkflowDuration` — `elapsed_ms()` ≥ 10 ms
- Raport — sekcje BLOCKERS / LOCAL ENVIRONMENT / Executive Summary

---

## 6. Przykładowy raport PRZED

```text
Duration: 0 ms
Decision: PRODUCTION_BLOCKED

Blockers:
  • Production deployment blocked. Working tree contains uncommitted changes.

Warnings:
  • [environment] git status: working tree dirty
  • [alembic] current: [Errno 2] No such file or directory: 'alembic'
  • [alembic] head: [Errno 2] No such file or directory: 'alembic'
  • Test discovery warning: No module named pytest
  (mieszane: projekt + środowisko + polityka w jednej liście)
```

---

## 7. Przykładowy raport PO

```text
Duration: 20157 ms
Decision: PRODUCTION_BLOCKED

Executive Summary:
  Project status:           BLOCKED
  Environment status:       WARNING
  Policy status:            BLOCK
  Deployment recommendation: Deploy zablokowany

BLOCKERS:
  • [frontend] dist freshness: Frontend dist wymaga przebudowy
  • Production deployment blocked. Working tree contains uncommitted changes.

WARNINGS:
  • [repository] dirty repo: working tree has tracked/untracked changes
  • Policy rule triggered: critical_db_change_requires_verified_backup

LOCAL ENVIRONMENT:
  • [alembic] current: [Errno 2] No such file or directory: 'alembic'
  • [alembic] head: [Errno 2] No such file or directory: 'alembic'

INFORMATION:
  • [environment] branch: on production (a8410f3)
  • [environment] python: Python 3.13.13
```

---

## 8. Wykonane analizy

- Przepływ zbierania blockers/warnings w stages vs policy_engine
- Ścieżka subprocess: `sys.executable`, `alembic` w PATH, import `psycopg`
- Timing workflow: `mark_started` / `mark_ended` vs `SummaryStage`
- Hardcoded penalties w `service.py` i `policy_engine.py`
- Live run `release evaluate` przed i po zmianach

---

## 9. Decyzja

### READY

Ulepszenia jakości diagnostyki Release Engine są kompletne i przetestowane.  
Deploy produkcyjny projektu pozostaje **NOT READY** z przyczyn projektowych (dirty tree, dist freshness) — to poprawnie widoczne w sekcji **BLOCKERS**, oddzielone od **LOCAL ENVIRONMENT**.

---

🩷 STATUS KOŃCOWY

✅ Co działa
- Klasyfikacja BLOCKERS / WARNINGS / LOCAL ENVIRONMENT / INFORMATION
- Lokalne błędy pytest/psycopg/alembic nie blokują release
- Duration mierzony poprawnie (np. 20157 ms)
- Penalty ze `ifg_production.yaml`
- Executive Summary w raporcie

⚠️ Znane problemy
- Deploy projektu nadal NOT READY (dirty tree, frontend dist) — zamierzone

❌ Co nie działa
- Brak regresji w Release Engine (13/13 testów)

**A. Root cause duration** — raport przed `mark_ended()`  
**B. Root cause mieszania** — brak warstwy klasyfikacji  
**C. Testy** — 13 passed  
**D. Następny krok** — commit GWO-IFG-0037, deploy po GWO-IFG-0036
