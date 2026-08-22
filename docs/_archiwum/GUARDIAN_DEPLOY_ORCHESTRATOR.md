# Guardian Deploy Orchestrator — specyfikacja

**Data:** 2026-06-26  
**Status:** Specyfikacja — **bez implementacji**  
**Cel:** Jedno polecenie `guardian ifg deploy run` wykonuje kompletny, bezpieczny deployment IFG  
**Powiązane:** [`GUARDIAN_V3_ARCHITECTURE_REVISED.md`](GUARDIAN_V3_ARCHITECTURE_REVISED.md), [`WORKFLOW.md`](WORKFLOW.md), [`GUARDIAN2_DEPLOY.md`](GUARDIAN2_DEPLOY.md)

---

## 0. Werdykt analizy stanu obecnego

Dziś IFG ma **trzy nakładające się ścieżki deploy**, żadna nie jest kompletna:

| Ścieżka | Plik | Zakres | Luki |
|---------|------|--------|------|
| **Canonical bash** | `scripts/deploy-ds723.sh` | Pełny deploy: test → build FE na Mac → rsync dist → pull → docker build/up → alembic → health | Brak inteligentnego build decision; dirty repo tylko prompt; brak raportu MD |
| **Guardian deploy check** | `ifg_guardian/modules/deploy.py` | Read-only: git sync, dist freshness, kontenery | Brak `/health`, brak alembic, brak disk space |
| **Guardian2 deploy-ksef** | `scripts/guardian2.py` | Mutating: KSeF allowlist, push, pull, npm build **na DS723+**, docker recreate | **Sprzeczność z WORKFLOW** (NAS nie buduje FE); brak alembic; wąski allowlist; nie ogólny deploy |

**Docelowe źródło prawdy:** orchestrator w pluginie IFG, zastępujący `deploy-ds723.sh` i `guardian2 deploy-ksef`, zachowując reguły z `WORKFLOW.md` (frontend budowany na Mac mini, rsync dist, alembic po deploy).

---

## ETAP 1 — Analiza obecnego procesu

### 1.1 Diagram stanu obecnego (as-is)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  PRZED DEPLOY (ręcznie / rozproszone)                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  • merge main → production, git push                                    │
│  • git checkout production && git pull                                    │
│  • opcjonalnie: guardian repo audit / doctor                              │
│  • opcjonalnie: preflight-ds723.sh (branch, REGON, dist, health)        │
│  • weryfikacja .env.production na NAS (ręcznie / preflight)             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  deploy-ds723.sh (Mac mini)                                             │
├─────────────────────────────────────────────────────────────────────────┤
│  1. branch == production          [FAIL jeśli nie]                      │
│  2. dirty repo → prompt [y/N]     [WARN, kontynuacja możliwa]          │
│  3. test-ifg.sh                   [FAIL jeśli pytest/build fail]        │
│  4. npm run build (frontend)       [ZAWSZE — brak detekcji zmian]        │
│  5. tar/rsync dist → DS723+       [mutating]                             │
│  6. SSH: git fetch/pull production                                       │
│  7. SSH: docker compose build api                                        │
│  8. SSH: docker compose up api worker                                    │
│  9. SSH: alembic upgrade head                                            │
│ 10. healthcheck.sh (ps + /health)  [FAIL jeśli curl fail]               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PO DEPLOY (ręcznie)                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  • preflight-ds723.sh                                                   │
│  • logs-api.sh / logs-worker.sh                                         │
│  • guardian deploy check (opcjonalnie)                                  │
│  • test manualny UI / REGON / KSeF                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Kroki wykonywane dziś — szczegółowo

| # | Krok | Gdzie | Narzędzie | Kryterium sukcesu |
|---|------|-------|-----------|-------------------|
| 1 | Git branch | Mac | `deploy-ds723.sh`, `preflight` | `production` |
| 2 | Git status (dirty) | Mac | `deploy-ds723.sh` | prompt; Guardian audit → WARN |
| 3 | Git pull origin | Mac (przed) + NAS (w deploy) | ręcznie + SSH | HEAD zsynchronizowany |
| 4 | Ahead/behind vs origin | Mac | `guardian repo status --fetch` | opcjonalnie; nie blokuje bash |
| 5 | Unit testy | Mac | `test-ifg.sh` → pytest | exit 0 |
| 6 | Frontend build detection | Mac | `frontend.py` (tylko w deploy check) | dist mtime vs src commit |
| 7 | Frontend build | Mac | `npm run build` | dist/assets/*.js |
| 8 | Backend build detection | — | **brak** — zawsze `docker build api` | — |
| 9 | Rsync dist | Mac → NAS | tar/SSH | index.html na NAS |
| 10 | Git pull | NAS | SSH | branch production |
| 11 | Docker compose config | — | **brak weryfikacji** | — |
| 12 | Docker build | NAS | `compose build api` | exit 0 |
| 13 | Docker up | NAS | `up -d api worker` | kontenery running |
| 14 | Alembic migrate | NAS | `exec api alembic upgrade head` | exit 0 |
| 15 | Health `/health` | NAS | `healthcheck.sh`, `prod health` | JSON status ok |
| 16 | Docker ps | NAS | compose ps | api/worker/db up |
| 17 | Log analysis | — | **ręcznie** `logs-api.sh` | brak automatu |
| 18 | Końcowy raport | — | **brak** (stdout only) | — |

### 1.3 Konfiguracja produkcyjna

| Element | Wartość |
|---------|---------|
| Host | `ds723` (alias SSH) / `zdalny_admin@ds723:32122` (`ds723.env`) |
| Repo path | `/volume1/docker/ifg_v2/ifg_standalone` |
| Branch | `production` |
| Compose | `docker/docker-compose.prod.yml` |
| Env | `.env.production` (gitignored, na NAS) |
| Frontend | `frontend-react/dist/` — mount RO w kontenerze API |
| Serwisy | `api`, `worker`, `db` |
| Health endpoint | `GET http://127.0.0.1:8000/health` |

### 1.4 Luki krytyczne (motywacja orchestratora)

1. **Brak jednego entry point** — bash vs guardian2 vs ręczne kroki.
2. **Build zawsze / nigdy** — bash buduje FE zawsze; guardian2 buduje na NAS (sprzeczność z WORKFLOW).
3. **Brak alembic** w guardian2 — migracje pomijane przy deploy-ksef.
4. **Deploy check ≠ gotowość** — brak HTTP health, alembic head, wolnego miejsca.
5. **guardian2 allowlist** — nie obsługuje pełnego repo (warehouse, invoices, PZ…).
6. **SSH/d Docker niespójność** — Guardian: `sudo docker`; bash: Synology PATH bez sudo.
7. **Brak raportu deploy** — brak artefaktu MD/JSON z czasem, commitem, decyzjami build.
8. **Rollback niezautomatyzowany** — opisany w WORKFLOW, nie w orchestratorze.

---

## ETAP 2 — Docelowy pipeline

### 2.1 Przepływ główny

```
guardian ifg deploy run [--yes] [--dry-run] [--skip-tests] [--force-build]
        │
        ▼
   PRECHECK ──FAIL(CRITICAL)──► STOP + raport
        │
        ▼
    FETCH ──FAIL──► STOP
        │
        ▼
     PULL ──FAIL──► STOP (lokalny + zdalny w fazie REMOTE)
        │
        ▼
 BUILD DECISION (read-only analiza diff)
        │
        ├── docs-only ──► skip FE + skip docker build
        ├── frontend ──► OPTIONAL FE BUILD
        ├── backend ──► DOCKER BUILD (api; worker shares image)
        └── full ──► FE BUILD + DOCKER BUILD
        │
        ▼
 OPTIONAL FRONTEND BUILD (Mac mini) ──FAIL──► STOP
        │
        ▼
 SYNC DIST (rsync/tar → NAS) ──FAIL──► STOP + rollback dist (opcjonalny)
        │
        ▼
 DOCKER BUILD (NAS) ──FAIL──► STOP (poprzednie kontenery nadal działają)
        │
        ▼
    DEPLOY (compose up + alembic) ──FAIL──► STOP + rollback policy
        │
        ▼
 HEALTH CHECK ──FAIL──► WARN/FAIL + rollback recommendation
        │
        ▼
 LOG ANALYSIS ──WARN──► kontynuuj z ostrzeżeniami
        │
        ▼
    SUMMARY (raport MD + JSON + exit code)
```

### 2.2 Fazy szczegółowo

#### PRECHECK

| | |
|---|---|
| **Wejście** | `DeployContext`: cwd, config (`ds723.env` / `project.yaml`), flagi CLI |
| **Wywołania** | Patrz § ETAP 4 — Safety |
| **Wyjście** | `PrecheckResult`: lista `CheckResult`, `overall_risk`, `blockers[]` |
| **PASS** | Wszystkie checki CRITICAL = pass; brak blockers |
| **WARN** | MEDIUM risk (np. dirty repo z wyjaśnieniem, behind origin o N<3) |
| **FAIL** | Jakikolwiek CRITICAL fail → **deploy zablokowany** |
| **Rollback** | N/A (nic nie mutowano) |

#### FETCH

| | |
|---|---|
| **Wejście** | `PrecheckResult` = PASS/WARN |
| **Akcje** | `git fetch origin` (Mac); opcjonalnie `git fetch` na NAS (read-only) |
| **Wyjście** | `ahead`, `behind`, `origin/production` SHA |
| **PASS** | fetch exit 0 |
| **WARN** | behind > 0 → „pull wymagany w następnej fazie” |
| **FAIL** | brak sieci / brak origin |
| **Rollback** | N/A |

#### PULL (lokalny — przed build)

| | |
|---|---|
| **Wejście** | FETCH result, branch = production |
| **Akcje** | `git pull origin production` na Mac (jeśli behind > 0) |
| **Wyjście** | `local_head` SHA |
| **PASS** | fast-forward lub already up to date |
| **WARN** | merge commit (non-FF) — wymaga `--yes` |
| **FAIL** | konflikt merge, dirty blocking files |
| **Rollback** | `git merge --abort` jeśli konflikt |

#### BUILD DECISION

| | |
|---|---|
| **Wejście** | `local_head`, `remote_head` (przed pull NAS), `git diff` zakres |
| **Akcje** | `BuildDetector.analyze()` — patrz § ETAP 3 |
| **Wyjście** | `BuildPlan`: `{frontend: bool, backend: bool, docker_services: [], reason}` |
| **PASS** | plan wygenerowany |
| **WARN** | `--force-build` nadpisuje plan |
| **FAIL** | nie można określić diff (np. brak poprzedniego deploy SHA) → conservative: full build |
| **Rollback** | N/A |

#### OPTIONAL FRONTEND BUILD

| | |
|---|---|
| **Wejście** | `BuildPlan.frontend == true` |
| **Akcje** | opcjonalnie `test-ifg.sh` (pytest); `cd frontend-react && npm ci && npm run build`; walidacja dist markers |
| **Wyjście** | `dist_built: bool`, `dist_sha`, czas build |
| **PASS** | dist/assets/*.js istnieje, build exit 0 |
| **WARN** | pominięto (--skip-tests) z logiem |
| **FAIL** | npm/build error |
| **Rollback** | N/A (dist lokalny) |

#### SYNC DIST

| | |
|---|---|
| **Wejście** | `BuildPlan.frontend` lub poprzedni dist do wysłania |
| **Akcje** | tar/stream dist → NAS (`deploy-ds723.sh` pattern); backup poprzedniego dist na NAS |
| **Wyjście** | `dist_synced`, `remote_dist_mtime` |
| **PASS** | `index.html` na NAS |
| **WARN** | dist unchanged (skip sync) |
| **FAIL** | SSH/rsync error |
| **Rollback** | restore NAS dist z backup tarball (jeśli utworzono) |

#### PULL (zdalny — na NAS)

| | |
|---|---|
| **Wejście** | SYNC complete |
| **Akcje** | SSH: `git fetch && git checkout production && git pull origin production` |
| **Wyjście** | `remote_head` SHA |
| **PASS** | remote HEAD == local HEAD (po deploy) |
| **FAIL** | konflikt / dirty na NAS |
| **Rollback** | N/A do tej pory |

#### DOCKER BUILD

| | |
|---|---|
| **Wejście** | `BuildPlan.backend`, compose file, env file |
| **Akcje** | `docker compose -f ... --env-file .env.production build api` (worker = ten sam image) |
| **Wyjście** | `image_id`, build duration |
| **PASS** | exit 0 |
| **WARN** | skip (docs-only plan) |
| **FAIL** | build error |
| **Rollback** | poprzedni image tag (`ifg-api:previous`) — patrz § Rollback |

#### DEPLOY

| | |
|---|---|
| **Wejście** | image built or skipped |
| **Akcje** | 1) zapisz `previous_head`, `previous_image` 2) `compose up -d --remove-orphans api worker` 3) `alembic upgrade head` |
| **Wyjście** | `containers_restarted[]`, `alembic_revision` |
| **PASS** | up exit 0, alembic exit 0 |
| **WARN** | alembic „already at head” |
| **FAIL** | up/alembic error, kontener restart loop |
| **Rollback** | `compose up` z poprzednim image + opcjonalnie `alembic downgrade` (tylko jeśli testowane) |

#### HEALTH CHECK

| | |
|---|---|
| **Wejście** | deploy complete |
| **Akcje** | Patrz § ETAP 5 |
| **Wyjście** | `HealthReport` |
| **PASS** | wszystkie checki pass |
| **WARN** | health ok, worker warnings w logach |
| **FAIL** | /health fail, api restarting, db unreachable |
| **Rollback** | rekomendacja auto-rollback jeśli FAIL w ciągu `start_period` (60s) |

#### LOG ANALYSIS

| | |
|---|---|
| **Wejście** | HEALTH w toku / po |
| **Akcje** | tail `docker logs api --since 5m`, tail worker; grep ERROR/Exception/Traceback |
| **Wyjście** | `log_findings[]`, severity |
| **PASS** | brak ERROR w oknie |
| **WARN** | znane benign patterns (KSeF 409, idle worker) |
| **FAIL** | ImportError, DB connection refused, crash loop |
| **Rollback** | N/A (informacyjne); FAIL podnosi overall status |

#### SUMMARY

| | |
|---|---|
| **Wejście** | wszystkie fazy |
| **Akcje** | generuj raport MD + JSON; zapisz `.guardian/deploy/<timestamp>.json` |
| **Wyjście** | exit code 0/1/2 |
| **PASS** | deploy OK, health OK |
| **WARN** | deploy OK, warnings |
| **FAIL** | deploy lub health fail |

### 2.3 Rollback policy (globalna)

| Faza po której FAIL | Automatyczny rollback | Rekomendacja w raporcie |
|---------------------|----------------------|-------------------------|
| PRECHECK–BUILD | N/A | Napraw warunki, uruchom ponownie |
| SYNC DIST | Przywróć dist backup na NAS | `guardian ifg deploy rollback --dist` |
| DOCKER BUILD | N/A (stary image intact) | Napraw Dockerfile, rebuild |
| DEPLOY (up) | **Opcjonalny** `--rollback-on-fail`: poprzedni image + compose up | `guardian ifg deploy rollback --yes` |
| HEALTH FAIL | Nie auto bez `--rollback-on-fail` | Ręczny rollback z WORKFLOW § rollback |
| ALEMBIC FAIL | **Nigdy auto downgrade** | Ręczna analiza; baza wymaga interwencji |

**Zasada:** rollback mutujący wymaga `--yes`. Domyślnie orchestrator **tylko rekomenduje**.

---

## ETAP 3 — Build Detector

### 3.1 Cel

Guardian sam decyduje co budować na podstawie **zakresu zmian między ostatnim udanym deploy a HEAD**, bez ręcznego pamiętania.

### 3.2 Źródła sygnału

| Sygnał | Priorytet | Opis |
|--------|-----------|------|
| `last_deploy_sha` | 1 | SHA z `.guardian/deploy/latest.json` lub remote HEAD jeśli brak historii |
| `git diff --name-only last..HEAD` | 1 | Lista plików |
| `git diff --name-only origin/production..HEAD` | 2 | gdy brak last_deploy |
| Frontend freshness (`frontend.py`) | 3 | dist vs src commit / worktree |
| `--force-build` | override | wymusza full build |

### 3.3 Reguły klasyfikacji plików

```
FRONTEND_PATHS = [
  "frontend-react/src/**",
  "frontend-react/package.json",
  "frontend-react/package-lock.json",
  "frontend-react/vite.config.js",
]

BACKEND_PATHS = [
  "app/**",
  "docker/Dockerfile",
  "docker/docker-compose.prod.yml",
  "alembic/**",
  "pyproject.toml",
  "requirements*.txt",
]

DOCS_ONLY_PATHS = [
  "docs/**",
  "*.md",
  ".cursor/**",
]

IGNORE_FOR_BUILD = [
  "docs/guardian/**",
  "tests/**",
  "scripts/ifg_guardian/**",  # zmiany Guardiana nie wymagają rebuild IFG
]
```

### 3.4 Macierz decyzji

| Zmienione pliki | Frontend build | Backend docker build | Dist sync | Alembic | Uwagi |
|-----------------|----------------|---------------------|-----------|---------|-------|
| tylko `docs/**`, `*.md` | ❌ | ❌ | ❌ | ❌ | **docs-only deploy** — opcjonalnie tylko git pull na NAS |
| tylko `frontend-react/src/**` | ✅ Mac | ❌* | ✅ rsync | ❌ | *backend image bez zmian |
| `app/**`, `alembic/**` | ❌ | ✅ api | ❌ | ✅ | worker używa tego samego image |
| FE + BE | ✅ | ✅ | ✅ | ✅ | full deploy |
| tylko `frontend-react/dist/**` | ❌ | ❌ | ✅ rsync | ❌ | ktoś zbudował lokalnie — sync only |
| `docker-compose.prod.yml` | ❌ | ✅ | ❌ | ❌ | recreate może wystarczyć |
| `.env.production` (NAS only) | ❌ | ❌ | ❌ | ❌ | **restart** api/worker, nie build |

### 3.5 Algorytm (pseudokod)

```python
def analyze_build_plan(changed_files: list[str], *, force: bool) -> BuildPlan:
    if force:
        return BuildPlan(frontend=True, backend=True, alembic=True, sync_dist=True)

    fe = any(matches(p, FRONTEND_PATHS) for p in changed_files)
    be = any(matches(p, BACKEND_PATHS) for p in changed_files)
    docs = all(matches(p, DOCS_ONLY_PATHS | IGNORE_FOR_BUILD) for p in changed_files)

    if not changed_files:
        return BuildPlan.none(reason="no changes since last deploy")

    if docs and not fe and not be:
        return BuildPlan.none(reason="docs-only")

    return BuildPlan(
        frontend=fe or check_frontend_worktree_requires_build(),
        backend=be,
        sync_dist=fe or dist_needs_sync(),
        alembic=any(p.startswith("alembic/") for p in changed_files) or be,
        docker_services=["api", "worker"] if be else [],
    )
```

### 3.6 Integracja z istniejącym `frontend.py`

| Funkcja | Rola w Build Detector |
|---------|----------------------|
| `check_frontend_dist_freshness()` | Sygnał: dist starszy niż src commit → `frontend=True` |
| `check_frontend_worktree_requires_build()` | Sygnał: uncommitted src → `frontend=True` przed deploy |
| `check_ksef_connect_button_fix()` | **Post-build gate** — nie decyzja build, ale FAIL jeśli markery brak |

---

## ETAP 4 — Safety (PRECHECK)

### 4.1 Checki obowiązkowe przed deploy

| ID | Check | CRITICAL fail gdy | WARN gdy |
|----|-------|-------------------|----------|
| `precheck.branch` | lokalny branch | ≠ `production` | — |
| `precheck.dirty` | `git status --porcelain` | pliki `DEPLOY_BLOCKER` (.env*) | inne dirty (CRLF unknown, substantive) |
| `precheck.ahead_behind` | vs `origin/production` | behind > 0 bez pull | ahead > 0 (unpushed) |
| `precheck.ssh` | SSH connectivity | timeout / auth fail | — |
| `precheck.remote_branch` | NAS branch | ≠ production | — |
| `precheck.env_production` | plik istnieje na NAS | brak pliku | REGON/JWT puste (preflight pattern) |
| `precheck.compose_config` | `docker compose config` | invalid YAML / missing env | — |
| `precheck.disk_space` | `df -h` na NAS | < 2 GB wolne na volume | < 5 GB |
| `precheck.containers` | compose ps | db not running | api restarting |
| `precheck.tests` | pytest (unless `--skip-tests`) | failures | — |

### 4.2 Blokada przy CRITICAL

```
if any(check.risk == CRITICAL and check.status == FAIL for check in prechecks):
    abort_deploy(reason="PRECHECK CRITICAL")
    write_report(status="BLOCKED")
    exit 2
```

### 4.3 Zachowanie WARN

- WARN **nie blokuje** domyślnie.
- Wymaga `--yes` do kontynuacji (interactive prompt lub explicit flag).
- `--dry-run` pokazuje wszystkie WARN bez mutacji.

### 4.4 Unified SSH config

Orchestrator **normalizuje** konfigurację:

```yaml
# .guardian/project.yaml (plugin IFG)
deploy:
  host: ds723
  user: zdalny_admin
  port: 32122
  repo_path: /volume1/docker/ifg_v2/ifg_standalone
  branch: production
  compose_file: docker/docker-compose.prod.yml
  env_file: .env.production
  docker_path: /var/packages/ContainerManager/target/usr/bin
  use_sudo: false          # Synology: false; inne hosty: true
  frontend_build_host: local   # IFG: Mac mini ONLY
  dist_sync: rsync_tar         # nie npm build na NAS
```

---

## ETAP 5 — Health (post-deploy)

### 5.1 Checki

| ID | Metoda | PASS | WARN | FAIL |
|----|--------|------|------|------|
| `health.compose_ps` | `docker compose ps` | api/worker/db Up | api health: starting | Exit/Restarting |
| `health.http` | `curl -fsS http://127.0.0.1:8000/health` | `"status":"ok"` | timeout 1 retry | connection refused |
| `health.db_timezone` | JSON field `db_timezone` | present | — | missing + 500 |
| `health.regon` | JSON field `regon.configured` | true | false (degraded) | — |
| `health.ui` | `curl -fsS http://127.0.0.1:8000/ui/` | HTTP 200 | — | 404/502 |
| `health.worker_logs` | `docker logs worker --since 3m` | brak Traceback | benign errors | crash loop |
| `health.api_logs` | `docker logs api --since 3m` | brak ImportError | KSeF warnings | startup exception |
| `health.alembic` | `alembic current` vs head | match | — | mismatch |

### 5.2 Timing

- Poll `/health` co 5s, max 12 prób (60s) — zgodnie z `start_period` w compose.
- Worker logs analizowane po pierwszym successful `/health`.

### 5.3 Agregacja

```
overall_health = FAIL if any FAIL
                 else WARN if any WARN
                 else PASS
```

---

## ETAP 6 — Raport końcowy

### 6.1 Lokalizacja

```
.guardian/deploy/
  2026-06-26T143022Z_deploy.json
  latest.json              # symlink/copy
docs/guardian/
  DEPLOY_REPORT_2026_06_26.md   # opcjonalny eksport --format markdown
```

### 6.2 Szablon Markdown

```markdown
# IFG Deploy Report

## Deployment Result
**Status:** SUCCESS | SUCCESS_WITH_WARNINGS | FAILED | BLOCKED

## Duration
Total: 4m 32s
- Precheck: 12s
- Frontend build: 1m 45s
- Docker build: 1m 20s
- Deploy: 45s
- Health: 30s

## Commit deployed
- Local:  ac7b339
- Remote: ac7b339
- Previous: b4e1f2a

## Build plan
| Component | Action | Reason |
|-----------|--------|--------|
| Frontend | built + synced | frontend-react/src changed |
| Backend | docker build api | app/services/*.py changed |
| Alembic | upgrade head | alembic/versions/*.py changed |

## Containers restarted
- api (recreated)
- worker (recreated)
- db (unchanged)

## Health
| Check | Status |
|-------|--------|
| /health | PASS |
| worker logs | WARN — KSeF session idle |

## Warnings
- Local repo: 2 unknown_line_endings files (not blocking)

## Recommended Action
1. Manual UI smoke test: login, REGON, KSeF session
2. Monitor worker logs for 10 min: `guardian ifg prod logs worker`
```

### 6.3 JSON schema (fragment)

```json
{
  "schema": "guardian_deploy_report_v1",
  "plugin": "ifg",
  "result": "SUCCESS_WITH_WARNINGS",
  "duration_ms": 272000,
  "commit": { "deployed": "ac7b339", "previous": "b4e1f2a" },
  "build_plan": { "frontend": true, "backend": true, "alembic": true },
  "containers_restarted": ["api", "worker"],
  "health": { "overall": "WARN", "checks": [] },
  "warnings": [],
  "recommended_actions": []
}
```

---

## ETAP 7 — Architektura pluginowa (przyszłość)

### 7.1 Podział Core vs Plugin

```
guardian/core/
  orchestrator/
    pipeline.py       # generic stage runner, timing, abort
    stage_result.py   # CheckResult, StageStatus
    rollback.py       # policy engine (no domain knowledge)
  ssh.py, git.py, docker.py, reporting.py

guardian/plugins/ifg/
  deploy/
    plugin.py         # IFGDeployPlugin implements DeployPlugin
    precheck.py       # IFG-specific checks
    build_detector.py
    dist_sync.py
    health.py
    config.yaml       # paths, branch, compose

guardian/plugins/ifgm/
  deploy/
    plugin.py         # inny build (Expo?), inny host

guardian/plugins/psag/
  deploy/
    plugin.py         # watchers restart, brak docker compose IFG
```

### 7.2 Interfejs DeployPlugin

```python
class DeployPlugin(ABC):
    name: str  # "ifg"

    def precheck(self, ctx: DeployContext) -> StageResult: ...
    def fetch(self, ctx: DeployContext) -> StageResult: ...
    def build_plan(self, ctx: DeployContext) -> BuildPlan: ...
    def build_frontend(self, ctx: DeployContext, plan: BuildPlan) -> StageResult: ...
    def build_backend(self, ctx: DeployContext, plan: BuildPlan) -> StageResult: ...
    def deploy(self, ctx: DeployContext, plan: BuildPlan) -> StageResult: ...
    def health_check(self, ctx: DeployContext) -> StageResult: ...
    def analyze_logs(self, ctx: DeployContext) -> StageResult: ...
    def rollback(self, ctx: DeployContext, target: RollbackTarget) -> StageResult: ...
```

Core uruchamia pipeline:

```python
# guardian/core/orchestrator/pipeline.py
def run_deploy(plugin: DeployPlugin, ctx: DeployContext) -> DeployReport:
    for stage in plugin.stages():
        result = stage.run(ctx)
        ctx.record(result)
        if result.blocking:
            break
    return ctx.build_report()
```

### 7.3 Komendy CLI (docelowe)

```bash
guardian ifg deploy run [--yes] [--dry-run]
guardian ifg deploy check          # read-only = obecny deploy check + precheck
guardian ifg deploy plan           # tylko BUILD DECISION, bez mutacji
guardian ifg deploy rollback [--yes]

guardian ifgm deploy run           # inny plugin, ten sam core orchestrator
guardian psag deploy run
```

### 7.4 Kompatybilność wsteczna

| Legacy | Docelowe |
|--------|----------|
| `guardian deploy check` | `guardian ifg deploy check` |
| `guardian deploy run --yes` | `guardian ifg deploy run --yes` |
| `guardian2 deploy-ksef` | **deprecated** → pełny `ifg deploy run` |
| `bash scripts/deploy-ds723.sh` | **deprecated** → wrapper wywołujący orchestrator |

---

## ETAP 8 — Plan implementacji (bez kodu teraz)

Patrz sekcja końcowa dokumentu i odpowiedź agenta.

---

## Appendix A — Mapowanie obecnych plików → orchestrator

| Obecny plik | Przeniesienie |
|-------------|---------------|
| `deploy-ds723.sh` | Logika → `plugins/ifg/deploy/dist_sync.py`, `deploy_remote.py`; skrypt → cienki shim |
| `guardian2.py deploy-ksef` | **Wycofanie** po feature parity |
| `ifg_guardian/modules/deploy.py` | → `plugins/ifg/deploy/check.py` (read-only) |
| `ifg_guardian/modules/frontend.py` | → `plugins/ifg/deploy/build_detector.py` + post-build gates |
| `ifg_guardian/modules/production.py` | → `plugins/ifg/deploy/health.py` |
| `healthcheck.sh` | → health stage |
| `preflight-ds723.sh` | → precheck stage (merge) |
| `test-ifg.sh` | → precheck lub frontend build pre-step |
| `ds723.env` | → `.guardian/project.yaml` |

---

## Appendix B — Decyzje projektowe (ADR)

| # | Decyzja | Uzasadnienie |
|---|---------|--------------|
| ADR-1 | Frontend build **tylko na Mac mini** | WORKFLOW.md, NAS bez npm toolchain |
| ADR-2 | Alembic **zawsze** po `compose up` gdy backend changed | guardian2 gap, PZ draft diag |
| ADR-3 | Brak auto-rollback alembic | ryzyko utraty danych |
| ADR-4 | `last_deploy_sha` w `.guardian/` | build detector bez zgadywania |
| ADR-5 | Plugin API zamiast monolitu w guardian2 | IFGM/PSAG bez zmian core |
| ADR-6 | `--yes` wymagane dla mutacji | zachowanie guardian2 / bezpieczeństwo |

---

*Specyfikacja do review przed implementacją Etapu 1 orchestratora.*
