# GWO-IFG-002A — Repo Clean State Prep (przed LIVE cutover)

**Data:** 2026-07-06  
**Branch:** `production`  
**HEAD:** `9505adc` — `prep(docker): pin compose project ifg to existing prod volume and network`  
**Status:** audyt — **LIVE cutover NIE uruchamiany**

---

## 1. Werdykt

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy można teraz uruchomić `ifg cutover run --yes`? | **NIE** |
| Dlaczego | Dirty working tree (17 zmodyfikowanych + ~90+ nieśledzonych); workflow cutover **nie jest w HEAD**; mieszanka WIP faktur/frontend z Guardianem |
| Co jest już na HEAD | Tylko `docker-compose.prod.yml` + `GWO_IFG_002A_COMPOSE_PROJECT_PREP.md` |
| Co brakuje w HEAD | Cały workflow `ifg.container.cutover`, Preflight Engine, CLI `ifg cutover`, runbook, raporty 002A/B |

---

## 2. Audyt `git status --short`

### 2.1 Zmodyfikowane (tracked) — 17 plików

| Plik | Kategoria | Akcja |
|------|-----------|-------|
| `scripts/ifg_guardian/cli.py` | **Cutover** | COMMIT |
| `scripts/ifg_guardian/plugins/ifg/plugin.py` | **Cutover** | COMMIT |
| `scripts/ifg_guardian/core/workflow/transaction.py` | **Cutover** | COMMIT |
| `scripts/ifg_guardian/core/workflow/executors/__init__.py` | GWO-G-003 execution | ODŁÓŻ (restore HEAD) |
| `scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py` | GWO-G-003 preflight w deploy_run | ODŁÓŻ (restore HEAD) |
| `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | GWO-G-003 | ODŁÓŻ (restore HEAD) |
| `app/api/deps.py` | WIP faktury | ODŁÓŻ (stash/restore) |
| `app/domain/enums.py` | WIP faktury | ODŁÓŻ |
| `app/persistence/mappers/invoice_mapper.py` | WIP faktury | ODŁÓŻ |
| `app/persistence/models/invoice.py` | WIP faktury | ODŁÓŻ |
| `app/persistence/repositories/transmission_repository.py` | WIP faktury | ODŁÓŻ |
| `app/services/invoice_number_policy.py` | WIP faktury | ODŁÓŻ |
| `app/services/payment_service.py` | WIP faktury | ODŁÓŻ |
| `frontend-react/dist/index.html` | WIP frontend (gitignored dist częściowo) | ODŁÓŻ |
| `frontend-react/src/api/invoices.js` | WIP frontend | ODŁÓŻ |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | WIP frontend | ODŁÓŻ |
| `frontend-react/vite.config.js` | WIP frontend | ODŁÓŻ |

**Statystyka diff tracked:** ~2028 insertions / 1851 deletions — dominuje WIP aplikacji, nie cutover.

### 2.2 Nieśledzone — grupy

#### A. Cutover / Guardian (COMMIT)

| Ścieżka |
|---------|
| `scripts/ifg_guardian/plugins/ifg/container_cutover/` (7 plików) |
| `scripts/ifg_guardian/modules/ifg_container_cutover.py` |
| `scripts/ifg_guardian/core/preflight/` (8 plików) |
| `scripts/ifg_guardian/plugins/ifg/deploy_run/preflight_stage.py` |
| `tests/unit/test_guardian_container_cutover_workflow.py` |
| `tests/unit/test_guardian_preflight.py` |
| `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` |
| `docs/reports/GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md` |
| `docs/reports/GWO_IFG_002A_RUNBOOK_FINAL.md` |
| `docs/reports/GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md` |
| `docs/reports/GWO_IFG_002A_PRODUCTION_MIGRATION.md` |
| `docs/reports/GWO_IFG_002_PROJECT_MIGRATION_PLAN.md` |
| `docs/reports/IFG_CONTAINER_MANAGER_MIGRATION.md` |
| `docs/reports/IFG_DS723_CONTAINER_MANAGER_PROJECT.md` |

**Uwaga:** `preflight_stage.py` i `deploy_run/workflow.py` są spójne jako GWO-G-003 — **nie** wchodzą do minimalnego commita cutover (cutover ma własny `PreflightStage` w `container_cutover/stages.py`). `preflight_stage.py` można commitować w osobnym commicie GWO-G-003 później.

#### B. GWO-G-003 execution layer (ODŁÓŻ — osobny commit później)

| Ścieżka |
|---------|
| `scripts/ifg_guardian/core/execution/` (10 plików) |
| Zmiany w `executors/__init__.py`, `deploy_run/workflow.py`, `test_guardian_ifg_deploy_run_workflow.py` |

#### C. WIP aplikacja / magazyn / KSeF (ODŁÓŻ — stash)

| Ścieżka |
|---------|
| `docs/FV_*.md`, `docs/PZ_*.md`, `docs/WZ_*.md`, `docs/WAREHOUSE_*.md` |
| `docs/KK_*.md`, `docs/KSEF_*.md`, `docs/UI_*.md` |
| `docs/IFG_PENDING_CHANGES_AUDIT.md`, `docs/REPO_*.md`, `docs/WIP_*.md` |
| `docs/IFG_LONG_RUNNING_OPERATIONS_STANDARD.md` |
| `frontend-react/src/components/invoice/invoiceCardListNumbering.test.js` |

#### D. Artefakty runtime / sekrety (NIE commitować)

| Ścieżka | Powód |
|---------|-------|
| `.guardian/` | Transakcje workflow lokalne |
| `.env.production.migration-test` | Plik testowy env |
| `docs/guardian/IFG_*_2026_*.md` | Raporty wygenerowane (runtime) |
| `docs/guardian/CUTOVER_PRECHECK_*.md`, `PRECHECK_*.md` | Runtime |
| `docs/reports/guardian_deploy_*.md`, `guardian_recover_*.md` | Historyczne logi |
| `docs/reports/repository_*.md` | Audyty repo |
| `docs/reports/GUARDIAN_CANON_REVIEW_*.md` | Osobny tor Guardian Core |
| `docs/reports/GWO_G003*.md` | Osobny GWO |

#### E. Dokumentacja architektury (opcjonalny osobny commit)

| Ścieżka |
|---------|
| `docs/guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md` |
| `docs/guardian/core/GUARDIAN_CORE_STATUS.md` |

Nie blokuje cutover; można commitować po cutover lub w GWO-G-003.

---

## 3. Lista zmian do commita (minimalny cutover)

**Proponowany commit 1** — tylko to, co jest wymagane do `ifg cutover run --yes`:

```
scripts/ifg_guardian/cli.py
scripts/ifg_guardian/plugins/ifg/plugin.py
scripts/ifg_guardian/core/workflow/transaction.py
scripts/ifg_guardian/plugins/ifg/container_cutover/
scripts/ifg_guardian/modules/ifg_container_cutover.py
scripts/ifg_guardian/core/preflight/
tests/unit/test_guardian_container_cutover_workflow.py
tests/unit/test_guardian_preflight.py
docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md
docs/reports/GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md
docs/reports/GWO_IFG_002A_RUNBOOK_FINAL.md
docs/reports/GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md
docs/reports/GWO_IFG_002A_PRODUCTION_MIGRATION.md
docs/reports/GWO_IFG_002_PROJECT_MIGRATION_PLAN.md
docs/reports/IFG_CONTAINER_MANAGER_MIGRATION.md
docs/reports/IFG_DS723_CONTAINER_MANAGER_PROJECT.md
docs/reports/GWO_IFG_002A_REPO_CLEAN_STATE_PREP.md
```

**Szacunkowo:** ~26 plików, bez dotykania `app/` i `frontend-react/`.

---

## 4. Lista zmian do odłożenia

### 4.1 Restore do HEAD (cofnij lokalne modyfikacje)

```bash
git restore \
  app/api/deps.py \
  app/domain/enums.py \
  app/persistence/mappers/invoice_mapper.py \
  app/persistence/models/invoice.py \
  app/persistence/repositories/transmission_repository.py \
  app/services/invoice_number_policy.py \
  app/services/payment_service.py \
  frontend-react/dist/index.html \
  frontend-react/src/api/invoices.js \
  frontend-react/src/components/invoice/InvoiceActions.jsx \
  frontend-react/vite.config.js \
  scripts/ifg_guardian/core/workflow/executors/__init__.py \
  scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py \
  tests/unit/test_guardian_ifg_deploy_run_workflow.py
```

**Ryzyko restore:** utrata niezacommitowanej pracy WIP — przed restore **stash** (patrz §5).

### 4.2 Zostaw untracked (nie dodawaj do commita)

- Cała grupa WIP docs (`FV_*`, `PZ_*`, `WAREHOUSE_*`, …)
- `.guardian/`, `.env.production.migration-test`
- `scripts/ifg_guardian/core/execution/` (do osobnego GWO-G-003)
- `scripts/ifg_guardian/plugins/ifg/deploy_run/preflight_stage.py` (do GWO-G-003)
- Wygenerowane raporty w `docs/guardian/`

---

## 5. Rekomendowana strategia (kolejność)

### Krok 0 — zabezpieczenie WIP (obowiązkowe przed restore)

```bash
cd /Users/lukasz/projekty/ifg_standalone

git stash push -u -m "wip: invoice numbering frontend guardian-g003 docs" -- \
  app/ \
  frontend-react/ \
  scripts/ifg_guardian/core/execution/ \
  scripts/ifg_guardian/plugins/ifg/deploy_run/preflight_stage.py \
  scripts/ifg_guardian/core/workflow/executors/__init__.py \
  scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py \
  tests/unit/test_guardian_ifg_deploy_run_workflow.py
```

Jeśli `git stash push -u` z wieloma ścieżkami jest zbyt szerokie, alternatywa:

```bash
# Stash tylko tracked WIP
git stash push -m "wip: invoice and frontend tracked" -- app/ frontend-react/

# Osobno zabezpiecz untracked execution (kopia katalogu)
cp -a scripts/ifg_guardian/core/execution /tmp/ifg_execution_backup
```

### Krok 1 — restore pozostałych tracked WIP (jeśli nie w stashu)

```bash
git restore app/ frontend-react/ \
  scripts/ifg_guardian/core/workflow/executors/__init__.py \
  scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py \
  tests/unit/test_guardian_ifg_deploy_run_workflow.py
```

### Krok 2 — commit cutover bundle

```bash
git add \
  scripts/ifg_guardian/cli.py \
  scripts/ifg_guardian/plugins/ifg/plugin.py \
  scripts/ifg_guardian/core/workflow/transaction.py \
  scripts/ifg_guardian/plugins/ifg/container_cutover/ \
  scripts/ifg_guardian/modules/ifg_container_cutover.py \
  scripts/ifg_guardian/core/preflight/ \
  tests/unit/test_guardian_container_cutover_workflow.py \
  tests/unit/test_guardian_preflight.py \
  docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md \
  docs/reports/GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md \
  docs/reports/GWO_IFG_002A_RUNBOOK_FINAL.md \
  docs/reports/GWO_IFG_002B_CONTAINER_MANAGER_BEHAVIOUR.md \
  docs/reports/GWO_IFG_002A_PRODUCTION_MIGRATION.md \
  docs/reports/GWO_IFG_002_PROJECT_MIGRATION_PLAN.md \
  docs/reports/IFG_CONTAINER_MANAGER_MIGRATION.md \
  docs/reports/IFG_DS723_CONTAINER_MANAGER_PROJECT.md \
  docs/reports/GWO_IFG_002A_REPO_CLEAN_STATE_PREP.md

git commit -m "$(cat <<'EOF'
feat(guardian): add IFG Container Manager cutover workflow

Wire ifg.container.cutover with Preflight Engine, Safety Gate, runbook,
and GWO-IFG-002A/B docs so production cutover can run via Guardian CLI.
EOF
)"
```

### Krok 3 — weryfikacja clean state

```bash
git status --short
# Oczekiwane: tylko untracked WIP docs / .guardian / execution (jeśli nie stashowane)

.venv/bin/pytest tests/unit/test_guardian_container_cutover_workflow.py \
  tests/unit/test_guardian_preflight.py -q -p no:cov

python3 scripts/guardian.py ifg cutover run --dry-run
```

### Krok 4 — push (operator, przed DS723+ git pull)

```bash
git push origin production
```

### Krok 5 — dopiero potem LIVE cutover

```bash
python3 scripts/guardian.py ifg cutover run --dry-run   # jeszcze raz po clean
python3 scripts/guardian.py ifg cutover run --yes       # LIVE — operator
```

---

## 6. Czy po planie można uruchomić LIVE cutover?

| Warunek | Po wykonaniu planu |
|---------|-------------------|
| `git status` clean (tracked) | ✅ |
| Workflow cutover w HEAD | ✅ |
| Preflight w HEAD | ✅ |
| Compose prep na HEAD (`9505adc`) | ✅ już jest |
| `pytest` cutover | ✅ (lokalnie) |
| `dry-run` SUCCESS | ✅ (lokalnie) |
| `git push` + `git pull` na DS723+ | ⏳ operator |
| Okno maintenance + backup | ⏳ operator |

**Werdykt:** Po **krokach 0–4** — **TAK**, można uruchomić `ifg cutover run --yes`.

**Teraz (bez commita):** **NIE**.

---

## 7. Ryzyka

| # | Ryzyko | Poważność | Mitygacja |
|---|--------|-----------|-----------|
| R1 | `git restore` bez stash → utrata WIP faktur | **Krytyczne** | Najpierw `git stash push` |
| R2 | Commit z `app/` przez pomyłkę | Wysokie | `git add` tylko ścieżki z §3 |
| R3 | LIVE cutover z dirty tree | Wysokie | Preflight: `git.clean` = WARNING; deploy check mylący | 
| R4 | Cutover bez push → DS723 `git pull` bez runbooka | Średnie | Runbook/docs opcjonalne na DS723; **compose już w 9505adc** |
| R5 | `execution/` untracked ale `executors` zmodyfikowany | Średnie | **Restore** `executors/__init__.py` do HEAD |
| R6 | `.guardian/` commitowane | Niskie | Nie dodawać; rozważyć `.gitignore` entry |
| R7 | Stash z `-u` chwyta cutover pliki | Średnie | Commit cutover **przed** stash reszty lub stash tylko `app/` `frontend-react/` |

---

## 8. Stan HEAD vs wymagania cutover

```
9505adc  prep(docker): compose name ifg + external pins     ← DS723+ git pull (minimum)
         ???          feat(guardian): cutover workflow       ← Mac mini (wymagane)
```

Cutover **wykonuje się z Mac mini** (SSH → DS723+). Kod Guardiana musi być spójny lokalnie; na DS723+ wystarczy compose z `9505adc` (już jest po pull). Dokumentacja na DS723+ jest opcjonalna dla samego `compose up`.

---

## 9. Podsumowanie

| Akcja | Liczba plików (szac.) |
|-------|----------------------|
| Do commita (cutover) | ~25 |
| Do restore/stash (WIP app/frontend) | 11 tracked |
| Do odłożenia (GWO-G-003 execution) | ~14 untracked + 3 tracked restore |
| Nie commitować (runtime/WIP docs) | ~60+ untracked |

**Nie wykonano:** commit, push, cutover, połączenie DS723+.

---

*Raport przygotowany wyłącznie do doprowadzenia repo do clean state przed GWO-IFG-002A LIVE.*
