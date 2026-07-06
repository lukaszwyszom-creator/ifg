# IFG Container Manager Cutover — Ready Check

**Data:** 2026-07-06  
**Cel:** gotowość operacyjna do dopięcia IFG w Synology Container Manager (project `ifg`)  
**Zakres:** analiza stanu repo + werdykt GO/NO-GO — **bez commitów, deployu, cutovera**  
**Runbook:** [RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md](../runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md) (APPROVED)

---

## Werdykt

# NO-GO

LIVE cutover (`python3 scripts/guardian.py ifg cutover run --yes`) **nie może być uruchomiony** w obecnym stanie repozytorium.

**GO** możliwe po wykonaniu minimalnej ścieżki z §5 (commity cutover + izolacja WIP + push + `git pull` na DS723+ + ponowny dry-run).

---

## 1. Aktualny stan repozytorium

| Parametr | Wartość |
|----------|---------|
| **Branch** | `production` |
| **HEAD** | `9505adc` — `prep(docker): pin compose project ifg to existing prod volume and network` |
| **Wpisy `git status --short`** | **102** |
| **Tracked modified** | **17** |
| **Untracked (top-level)** | **~85** (+ rozwinięcie `.guardian/`) |

### 1.1 Tracked modified (17)

| Plik | Typ zmiany | Cutover |
|------|------------|---------|
| `scripts/ifg_guardian/cli.py` | Cutover CLI | **Wymagany commit** |
| `scripts/ifg_guardian/plugins/ifg/plugin.py` | Rejestracja workflow | **Wymagany commit** |
| `scripts/ifg_guardian/core/workflow/transaction.py` | `cutover_run` | **Wymagany commit** |
| `scripts/ifg_guardian/core/workflow/executors/__init__.py` | GWO-G-003 execution | Poza minimalnym cutover |
| `scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py` | GWO-G-003 preflight | Poza minimalnym cutover |
| `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | GWO-G-003 | Poza minimalnym cutover |
| `app/api/deps.py` | CRLF-only | Poza production |
| `app/domain/enums.py` | CRLF-only | Poza production |
| `app/persistence/mappers/invoice_mapper.py` | CRLF-only | Poza production |
| `app/persistence/models/invoice.py` | CRLF-only | Poza production |
| `app/persistence/repositories/transmission_repository.py` | **WIP funkcjonalny** | Poza production |
| `app/services/invoice_number_policy.py` | CRLF-only | Poza production |
| `app/services/payment_service.py` | CRLF-only | Poza production |
| `frontend-react/src/api/invoices.js` | CRLF-only | Poza production |
| `frontend-react/src/components/invoice/InvoiceActions.jsx` | CRLF-only | Poza production |
| `frontend-react/vite.config.js` | CRLF-only | Poza production |
| `frontend-react/dist/index.html` | Artefakt buildu (hash assetów) | Poza production |

### 1.2 Untracked — istotne dla cutover

| Ścieżka | Status |
|---------|--------|
| `scripts/ifg_guardian/core/preflight/` (8 plików) | **Nie w HEAD** — wymagane |
| `scripts/ifg_guardian/plugins/ifg/container_cutover/` (7 plików) | **Nie w HEAD** — wymagane |
| `scripts/ifg_guardian/modules/ifg_container_cutover.py` | **Nie w HEAD** — wymagane |
| `tests/unit/test_guardian_container_cutover_workflow.py` | **Nie w HEAD** — wymagane |
| `tests/unit/test_guardian_preflight.py` | **Nie w HEAD** — wymagane |
| `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` | **Nie w HEAD** — zalecane |
| `docs/reports/GWO_IFG_002*.md`, `IFG_CONTAINER_MANAGER_MIGRATION.md`, … | **Nie w HEAD** — zalecane |
| `scripts/ifg_guardian/core/execution/` | Poza minimalnym cutover |
| `.guardian/` (~287 JSON) | Runtime — nie commitować |
| `.env.production.migration-test` | Sekret/test — nie commitować |

### 1.3 CRLF-only (10 plików)

Potwierdzone `git diff HEAD --ignore-cr-at-eol` pusty dla:

- `app/api/deps.py`, `app/domain/enums.py`, `app/persistence/mappers/invoice_mapper.py`, `app/persistence/models/invoice.py`, `app/services/invoice_number_policy.py`, `app/services/payment_service.py`
- `frontend-react/src/api/invoices.js`, `frontend-react/src/components/invoice/InvoiceActions.jsx`, `frontend-react/vite.config.js`

**Wyjątek:** `transmission_repository.py` — **REAL** (nowe metody: `list_all_paginated`, `add`, `get_latest_ksef_errors_for_invoices`).

### 1.4 `transmission_repository.py` — WIP

| Metryka | Wartość |
|---------|---------|
| HEAD | ~106 linii |
| Working tree | ~211 linii |
| Zmiana logiczna | Tak — rozszerzenie repozytorium KSeF/transmission |
| Związek z cutover | **Brak** |
| Rekomendacja | Branch `feature/ksef-transmission-wip` — poza `production` |

### 1.5 Frontend `dist/`

| Metryka | Wartość |
|---------|---------|
| Pliki tracked w `frontend-react/dist/` | **10** |
| `.gitignore` | `frontend-react/dist/` — **jest**, ale pliki historycznie w indeksie |
| Szum | `frontend-react/dist/index.html` — `M` (zmiana hashów Vite) |
| Wpływ na cutover | Brak bezpośredni; psuje `git status` |

### 1.6 `.guardian/`

| Metryka | Wartość |
|---------|---------|
| W `.gitignore` | **NIE** |
| Pliki untracked | ~287 (`workflows/`, `latest/`) |
| Wpływ na cutover | Brak operacyjny; blokuje „clean tree" |

---

## 2. Co blokuje cutover

| # | Bloker | Priorytet | Uwagi |
|---|--------|-----------|-------|
| **B1** | **Dirty working tree** (102 wpisy) | 🔴 | Operator wymaga clean tree przed LIVE; preflight `git.clean` = WARNING (nie FAIL) — dry-run przechodzi mimo brudu |
| **B2** | **Workflow cutover nie w HEAD** | 🔴 | `git show HEAD:scripts/ifg_guardian/cli.py` — **0** odniesień do `cutover`; cały pakiet tylko w working tree |
| **B3** | **Preflight Engine nie w HEAD** | 🔴 | `core/preflight/` untracked; stage `PreflightStage` w cutover od niego zależy |
| **B4** | **Brak commitów + push** | 🔴 | Po commicie lokalnym: `git push origin production`; DS723+ `git pull` przed `git_pull` stage |
| **B5** | **WIP `transmission_repository.py`** | 🟠 | Mieszanie torów; izolować na feature branch |
| **B6** | **10 plików CRLF + dist** | 🟡 | Fałszywy szum; nie blokuje funkcjonalnie, utrudnia audyt |
| **B7** | **`.guardian/` nie ignorowane** | 🟡 | Szum untracked |

**Nie blokuje:**

- Compose prep — **już w HEAD** (`9505adc`)
- Runbook — istnieje lokalnie (APPROVED), brak w HEAD
- Testy cutover — **10 passed** lokalnie (kod WT)
- Dry-run — **SUCCESS** lokalnie (kod WT)

---

## 3. Co jest gotowe

| Element | Stan | Lokalizacja |
|---------|------|-------------|
| **Compose `name: ifg`** | ✅ HEAD | `docker/docker-compose.prod.yml:30` |
| **External volume `docker_postgres_data`** | ✅ HEAD | `volumes.postgres_data.external: true` |
| **External network `docker_ifg_prod`** | ✅ HEAD | `networks.ifg_prod.external: true` |
| **Workflow `ifg.container.cutover`** | ✅ Working tree (12 stages) | `plugins/ifg/container_cutover/workflow.py` |
| **CLI `ifg cutover run/rollback`** | ✅ Working tree | `python3 scripts/guardian.py ifg cutover --help` |
| **Preflight Engine** | ✅ Working tree (8 modułów) | `core/preflight/` |
| **Safety Gate w cutover** | ✅ Working tree | `PreflightStage` → GO/NO_GO przed `cutover_up` |
| **Runbook APPROVED** | ✅ Working tree | `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` |
| **Raporty GWO-IFG-002A/B** | ✅ Working tree | `docs/reports/GWO_IFG_002*.md` |
| **Unit testy cutover + preflight** | ✅ **10 passed** | `test_guardian_container_cutover_workflow.py`, `test_guardian_preflight.py` |
| **Dry-run cutover** | ✅ **SUCCESS** | Safety Gate GO; raport `docs/guardian/IFG_CONTAINER_CUTOVER_2026_07_06.md` |
| **Scenario B (recreate containers)** | ✅ Udokumentowane | GWO-IFG-002B |
| **Rollback CLI** | ✅ Working tree | `ifg cutover rollback --yes` |

### 3.1 Weryfikacja HEAD — compose pins

```yaml
name: ifg
volumes:
  postgres_data:
    name: docker_postgres_data
    external: true
networks:
  ifg_prod:
    name: docker_ifg_prod
    external: true
```

Zgodne z wymaganiami Container Manager cutover (zachowanie istniejącego volume i sieci projektu `docker`).

### 3.2 Weryfikacja lokalna (wykonana dziś, nie LIVE)

```bash
.venv/bin/pytest tests/unit/test_guardian_container_cutover_workflow.py \
  tests/unit/test_guardian_preflight.py -q -p no:cov
# → 10 passed in 0.10s

python3 scripts/guardian.py ifg cutover run --dry-run
# → SUCCESS, Safety Gate GO, Cutover executed: False
```

---

## 4. Minimalna ścieżka do GO

Operacyjna sekwencja (wg `IFG_REPOSITORY_COMMIT_STRATEGY.md` — ścieżka minimalna **B → E → F → G**):

```
┌─────────────────────────────────────────────────────────────┐
│ Faza 0 — Izolacja WIP (bez restore, bez dużego stash)      │
│   git switch -c feature/ksef-transmission-wip               │
│   git add app/persistence/repositories/transmission_*.py    │
│   git commit -m "wip: transmission repository expansion"    │
│   git switch production                                     │
├─────────────────────────────────────────────────────────────┤
│ Faza 1 — Commit B: Preflight Engine                         │
│   surgical git add: core/preflight/, test_guardian_preflight│
├─────────────────────────────────────────────────────────────┤
│ Faza 2 — Commit E: Cutover workflow                         │
│   surgical git add: container_cutover/, ifg_container_cutover│
│   cli.py, plugin.py, transaction.py, test cutover         │
├─────────────────────────────────────────────────────────────┤
│ Faza 3 — Commit F: Runbook + raporty GWO                    │
│   docs/runbooks/, docs/reports/GWO_IFG_002*, migration docs │
├─────────────────────────────────────────────────────────────┤
│ Faza 4 — Commit G: Housekeeping                             │
│   .gitignore += .guardian/                                  │
│   git rm --cached -r frontend-react/dist/                   │
├─────────────────────────────────────────────────────────────┤
│ Faza 5 — Weryfikacja                                        │
│   git status → clean (tracked)                              │
│   pytest cutover + preflight                                │
│   ifg cutover run --dry-run                                 │
├─────────────────────────────────────────────────────────────┤
│ Faza 6 — Push + remote sync                                 │
│   git push origin production                                │
│   DS723+: git pull (compose już w 9505adc; nowe commity)    │
├─────────────────────────────────────────────────────────────┤
│ Faza 7 — LIVE cutover (operator, okno maintenance)          │
│   ifg cutover run --dry-run   # ponownie                    │
│   ifg cutover run --yes                                     │
│   … walidacja funkcjonalna …                                │
│   ifg cutover run --yes --confirm-functional --cleanup      │
└─────────────────────────────────────────────────────────────┘
```

**Nie wchodzi do minimalnej ścieżki:** `core/execution/`, `deploy_run/preflight_stage.py`, zmiany G003 w `executors/__init__.py` — cutover ich nie wymaga.

---

## 5. Kolejność commitów (minimalna)

| # | Commit message (propozycja) | Pliki (~) | Zależności |
|---|----------------------------|-----------|------------|
| **0** | `wip: transmission repository expansion` | 1 | Na branchu `feature/*`, nie `production` |
| **1** | `feat(guardian): add Preflight Engine and Safety Gate` | ~10 | — |
| **2** | `feat(guardian): add IFG Container Manager cutover workflow` | ~12 | **1** |
| **3** | `docs(ifg): add Container Manager cutover runbook and GWO reports` | ~10 | **2** |
| **4** | `chore: ignore guardian runtime and untrack frontend dist` | 2–12 | — |

Po commitach **1–4** na `production`: `git status` bez tracked `M`; untracked tylko WIP docs / execution (opcjonalnie).

---

## 6. Testy do wykonania (przed LIVE)

| # | Komenda | Oczekiwany wynik | Kiedy |
|---|---------|------------------|-------|
| T1 | `pytest tests/unit/test_guardian_preflight.py -q` | PASS | Po commicie **1** |
| T2 | `pytest tests/unit/test_guardian_container_cutover_workflow.py -q` | PASS | Po commicie **2** |
| T3 | `pytest tests/unit/test_guardian_preflight.py tests/unit/test_guardian_container_cutover_workflow.py -q` | PASS | Po **1+2** |
| T4 | `python3 scripts/guardian.py ifg doctor` | Brak CRITICAL | Przed LIVE |
| T5 | `python3 scripts/guardian.py deploy check` | Local + remote clean, branch production | Po push + DS723 pull |
| T6 | Smoke API po cutover | `/health` 200 | Po `cutover_up` |
| T7 | Checklist funkcjonalna (runbook §) | Operator | Przed `--cleanup` |

---

## 7. Dry-run do wykonania

| # | Komenda | Kiedy | Wynik dziś |
|---|---------|-------|------------|
| D1 | `python3 scripts/guardian.py ifg cutover run --dry-run` | Po każdej fazie commitów | ✅ SUCCESS (WT) |
| D2 | `python3 scripts/guardian.py ifg cutover rollback --dry-run` | Po D1 | Do wykonania po commitach |
| D3 | `python3 scripts/guardian.py ifg cutover run --dry-run` | **Po push + DS723 git pull** | Wymagane przed LIVE |
| D4 | `python3 scripts/guardian.py ifg cutover run --dry-run` | Bezpośrednio przed `--yes` | Obowiązkowe |

**Uwaga:** Dry-run z dirty tree daje GO — to **nie zwalnia** z wymogu clean tree przed LIVE (runbook + dobra praktyka).

---

## 8. Co ma zostać poza `production`

| Grupa | Pliki / obszar |
|-------|----------------|
| WIP KSeF | `transmission_repository.py` → `feature/ksef-transmission-wip` |
| CRLF noise | 9 plików app/frontend (opcjonalny chore osobno) |
| G003 execution | `core/execution/`, `executors/__init__.py`, `deploy_run/workflow.py` |
| Docs domenowe | `docs/FV_*`, `PZ_*`, `WZ_*`, `WAREHOUSE_*`, `KSEF_*` (diagnozy) |
| Vision / repo strategy | `GUARDIAN_VISION.md`, `REPOSITORY_TARGET_STATE.md` — nie blokują cutover |
| Runtime | `.guardian/`, `.env.production.migration-test` |
| Historyczne logi | `docs/reports/guardian_deploy_*`, `guardian_recover_*` |
| Test frontend | `invoiceCardListNumbering.test.js` |

---

## 9. Ryzyka

| # | Ryzyko | P | W | Mitygacja |
|---|--------|---|---|-----------|
| R1 | LIVE z dirty tree | W | W | Commity B→E→F→G; `git status` clean |
| R2 | Cutover bez push — DS723 bez nowego kodu w git | W | Ś | Push przed LIVE; stage `git_pull` |
| R3 | Guardian na Mac mini ≠ HEAD | W | W | Commit + upewnij się, że używasz tego samego WT/HEAD |
| R4 | `docker rm docker-*` przed walidacją | Ś | K | Runbook: cleanup tylko `--confirm-functional --cleanup` |
| R5 | Utrata danych Postgres | N | K | External volume `docker_postgres_data`; zakaz `down -v` |
| R6 | Commit WIP przez pomyłkę | Ś | W | Surgical `git add` tylko ścieżki z §5 |
| R7 | Preflight git.clean WARNING przy brudnym drzewie | W | Ś | Nie traktować dry-run GO jako zgody na dirty LIVE |
| R8 | Stare kontenery `docker-*` równolegle z `ifg-*` | Oczekiwane | N | Scenario B; cleanup po walidacji |

---

## 10. Werdykt końcowy

| Pytanie | Odpowiedź |
|---------|-----------|
| Czy można teraz `ifg cutover run --yes`? | **NIE** |
| Czy compose prep jest gotowy? | **TAK** (HEAD `9505adc`) |
| Czy workflow cutover jest gotowy w kodzie? | **TAK** (working tree) |
| Czy workflow cutover jest w HEAD / na remote? | **NIE** |
| Czy testy i dry-run przechodzą lokalnie? | **TAK** |
| Czy ścieżka do GO jest znana? | **TAK** (§4–§5) |

### Jednoznaczny werdykt

# NO-GO

**GO** po: izolacja WIP → commity **1–4** → clean `git status` → push → DS723+ `git pull` → dry-run D3 → okno maintenance → `ifg cutover run --yes`.

---

## 11. Pliki `.md` — utworzone lub zaktualizowane

| Plik | Akcja |
|------|-------|
| `docs/reports/2026-07-06_IFG_CONTAINER_CUTOVER_READY_CHECK.md` | **Utworzony** (niniejszy raport) |

**Nie zaktualizowano** żadnych istniejących dokumentów.

---

## Załącznik — mapowanie na dokumenty źródłowe

| Dokument | Rola w tym checku |
|----------|-------------------|
| `IFG_REPOSITORY_COMMIT_STRATEGY.md` | Kolejność commitów B→E→F→G |
| `REPOSITORY_TARGET_STATE.md` | Release flow, clean tree policy |
| `2026-07-06_REPOSITORY_TARGET_STATE_DESIGN.md` | Audyt stanu repo |
| `GUARDIAN_VISION.md` | Kontekst długoterminowy — **poza zakresem cutover** |
| `RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` | Procedura LIVE |
| `GWO_IFG_002A_GUARDIAN_CUTOVER_PREP.md` | Mapowanie runbook → workflow |

---

*Raport operacyjny. Nie wykonano commitów, push, deployu ani LIVE cutover.*
