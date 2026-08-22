# IFG Repository Cleanup Advisor

**Data:** 2026-06-26  
**Status:** IMPLEMENTED  
**Profil:** `scripts/guardian_platform/profiles/ifg/`  
**Platform core:** bez nowych funkcji (poza poprawką parsowania flag CLI w `builder.py`)

---

## 1. Cel

Warstwa decyzyjna profilu IFG łącząca:

1. **Repo Graph** (fakty — `core/repository/`)
2. **REPO_CLEANUP_PLAN** (reguły archiwizacji / faz)
3. **IFG Policy** (zakazy DELETE na kodzie produkcyjnym)

Platforma dostarcza analizę; profil IFG podejmuje decyzje i (opcjonalnie) wykonuje cleanup.

---

## 2. Komendy

```bash
python3 -m scripts.guardian_platform ifg repo cleanup --dry-run
python3 -m scripts.guardian_platform ifg repo cleanup --yes
python3 -m scripts.guardian_platform ifg repo cleanup --phase 0
python3 -m scripts.guardian_platform ifg repo cleanup --phase 1
python3 -m scripts.guardian_platform ifg repo cleanup --phase 2
python3 -m scripts.guardian_platform ifg repo cleanup --phase 3
python3 -m scripts.guardian_platform --dry-run ifg repo cleanup --report
```

| Flaga | Działanie |
|-------|-----------|
| `--dry-run` | Domyślny tryb bezpieczny — plan bez zmian |
| `--yes` | Wykonanie LIVE (wymagane poza dry-run) |
| `--phase N` | Tylko faza 0–3 (domyślnie wszystkie) |
| `--report` | Zapis raportu (zawsze przy cleanup) |

**Mutating:** `mutating=True`, `supports_dry_run=True` — jak `deploy run`.

---

## 3. Moduły profilu IFG

```
profiles/ifg/repo_cleanup/
  models.py      # AdvisorDecision, CleanupOperation, CleanupPlan
  policy.py      # IFG policy, archive targets, NEVER_DELETE
  history.py     # HistoryKind (closed incident, sprint, …)
  advisor.py     # Graph → History → Policy → Decision + Confidence
  planner.py     # Fazy 0–3 → lista operacji
  executor.py    # local rm / git mv
  report.py      # markdown reports
  runner.py      # orchestracja CLI
commands/repo_cleanup.py
```

---

## 4. Advisor pipeline

```
Repository Graph  →  History  →  IFG Policy  →  Decision + Confidence
```

| Decision | Kiedy |
|----------|-------|
| **KEEP** | Canonical docs, production code, protected paths |
| **ARCHIVE** | Closed incidents, sprint reports, runtime reports |
| **REVIEW** | Ambiguous docs, Repo Graph DELETE override |
| **DELETE** | Tylko lokalne artefakty (faza 0) |

**Confidence:** 0–100 (np. closed incident → 97%, canonical → 98%).

### Przykład

`docs/KSEF_SYNC_FIX.md`

| Warstwa | Wynik |
|---------|-------|
| Graph | PROTECTED / KEEP |
| History | closed_incident |
| Policy | archive finished incidents |
| **Decision** | **ARCHIVE** (97%) |

---

## 5. Fazy

### Faza 0 — artefakty lokalne

Usuwa lokalnie (bez `git rm`):

- `__pycache__`, `.pytest_cache`, `.DS_Store`
- `.logs`, `tmp`, `frontend-react/dist`, `node_modules`
- `*.pyc`, `ksef_backend.egg-info`

### Faza 1 — dokumentacja ARCHIVE

`git mv` → `docs/archive/2026-06/{incidents,ksef,guardian,warehouse,…}/`

Bez usuwania plików.

### Faza 2 — reorganizacja KEEP

`git mv` do `docs/architecture/`, `docs/guardian/`, `docs/operations/`, …

Zero DELETE. README/link updates — plan operacji (manual follow-up).

### Faza 3 — REVIEW

Lista kandydatów REVIEW — **bez automatycznych zmian**.

---

## 6. Zabezpieczenia

**DELETE** wyłącznie dla artefaktów lokalnych (faza 0).

Nigdy auto-DELETE:

- `docs/`, `app/`, `scripts/`, `tests/`
- `guardian_platform/`, legacy guardian scripts
- `frontend-react/src/`, `alembic/`, `mobile-expo/`

---

## 7. Raporty

| Plik | Kiedy |
|------|-------|
| `docs/reports/repository_cleanup_plan.md` | Każde uruchomienie (dry-run / plan) |
| `docs/reports/repository_cleanup_execution.md` | Po `--yes` LIVE |

Zawartość planu: operacje, uzasadnienie, impact, confidence, rollback plan.

---

## 8. Testy

Plik: `tests/guardian_platform/test_repo_cleanup_advisor.py`

| Obszar | Testy |
|--------|-------|
| Advisor scoring | ARCHIVE incident, KEEP canonical |
| Phase selection | 0–3, full plan |
| Archive policy | destination paths |
| Dry-run | brak zmian na dysku |
| Rollback plan | 1 krok / operacja |
| Confidence | ≥97% dla incydentów |
| CLI | `--dry-run`, `--phase 1`, guard `--yes` |
| Regression IFG | alembic, architecture doc, `__init__.py` |

**Nowe testy:** 24  
**Guardian Platform łącznie:** 292 passed

---

## 9. Gotowość

| Etap | Status |
|------|--------|
| Dry-run cleanup (pełny plan) | **TAK** |
| Faza 0 (`--yes`) | **TAK** — tylko artefakty lokalne |
| Faza 1 (`--dry-run`) | **TAK** — lista `git mv` |
| Faza 1 LIVE | **TAK** — wymaga `--yes`; bez DELETE |

**Profil IFG v0.5.1-cleanup-boundary** — v1.1.1: whitelist katalogów repo (`boundaries.py`); faza 0 nie skanuje `.venv`/`.git`/`site-packages`.
