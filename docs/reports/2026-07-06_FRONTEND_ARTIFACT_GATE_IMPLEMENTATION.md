# Frontend Artifact Verification Gate — implementacja

**Data:** 2026-07-06  
**Cel:** Guardian gwarantuje obecność `frontend-react/dist/index.html` i `assets/*.js` **przed** `docker compose up` (deploy i cutover).  
**LIVE cutover:** nie wykonano.

---

## 1. Problem

| Luka | Skutek |
|------|--------|
| `dist/` poza Git | `git pull` nie dostarcza `index.html` |
| Cutover bez `npm run build` | API startuje z pustym/brakującym dist |
| Deploy warunkowy (Doctor) | build/sync mógł być pominięty |
| Weryfikacja remote | tylko mtime `assets/*.js`, nie `index.html` |
| `compose up` bez gate | kontenery startowały mimo braku SPA |

Potwierdzony przypadek DS723+ (2026-07-06): `index.html` **MISSING**, `assets/` obecne → UI niedostępne po restarcie.

---

## 2. Rozwiązanie — Artifact Verification Gate

Nowy moduł: `scripts/ifg_guardian/core/frontend_artifacts.py`

| Element | Opis |
|---------|------|
| `verify_local_dist()` | GO/NO_GO na Mac mini |
| `remote_artifact_verify_script()` | bash na DS723+ — `index.html` + `assets/*.js` |
| `remote_frontend_build_script()` | `npm run build` na DS723+ |
| `build_rsync_dist_command()` | rsync przez SSH (`ssh -p`) |
| `parse_artifact_gate_output()` | parser `ARTIFACT_GATE_STATUS=GO\|NO_GO` |

Markery komend deploy:

- `ifg_guardian_frontend_artifact_gate local`
- `ifg_guardian_frontend_artifact_gate remote`

---

## 3. Zmiany w pipeline deploy (`ifg deploy run`)

Kolejność kroków (zawsze obowiązkowe — niezależnie od Doctor):

```
1. git pull
2. frontend build          (npm run build — Mac)
3. artifact verify local   (gate)
4. dist sync               (rsync przez SSH)
5. artifact verify         (gate remote DS723+)
6. docker build            (warunkowo)
7. alembic upgrade         (warunkowo)
8. compose up              (tylko po gate GO)
9. health check
10. log verification
```

**Blokada compose:**

- `SimulateExecutionStage` — po FAIL gate/build/sync → `compose up` = **BLOCKED**
- `ComposeExecutor.execute_up()` — ponowna weryfikacja remote przed `up -d` (defense in depth)

---

## 4. Zmiany w cutover (`ifg cutover run`)

Nowe etapy **przed** `cutover_up`:

| Stage | ID | Akcja |
|-------|-----|--------|
| Frontend build | `frontend_build` | `npm run build` na DS723+ |
| Artifact Gate | `frontend_artifact_gate` | weryfikacja `index.html` + assets |

`CutoverUpStage`:

- wymaga `state.frontend_artifacts_ok == True` (LIVE)
- `cutover_up_script()` ponownie uruchamia gate przed `compose up`

Stan cutover (`CutoverRunState`):

- `frontend_artifacts_ok: bool`
- `artifact_gate_status: str`

---

## 5. Werdykt gate

| Status | Zachowanie |
|--------|------------|
| **GO** | `index.html` istnieje, `assets/` istnieje, ≥1 plik `*.js` |
| **NO_GO** | brak któregokolwiek → workflow **FAIL**, `compose up` **nie** wykonywany |

---

## 6. Pliki zmienione

| Plik | Zmiana |
|------|--------|
| `core/frontend_artifacts.py` | **nowy** — logika gate |
| `core/workflow/executors/router.py` | typy `ARTIFACT_GATE_*` |
| `core/workflow/executors/__init__.py` | executor lokalny + remote gate |
| `core/workflow/executors/compose_executor.py` | gate przed `up` |
| `plugins/ifg/deploy_run/pipeline.py` | obowiązkowe kroki + rsync SSH |
| `plugins/ifg/deploy_run/stages.py` | blokada compose po FAIL |
| `plugins/ifg/container_cutover/stages.py` | `FrontendBuildStage`, `FrontendArtifactGateStage` |
| `plugins/ifg/container_cutover/workflow.py` | rejestracja etapów |
| `plugins/ifg/container_cutover/remote.py` | skrypty build + gate w `cutover_up` |
| `plugins/ifg/container_cutover/models.py` | pola stanu gate |
| `plugins/ifg/container_cutover/report.py` | wiersz Artifact Gate |
| `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md` | kroki 4b, 4c, checklist |
| `tests/unit/test_guardian_frontend_artifacts.py` | **nowy** |
| `tests/unit/test_guardian_*` | aktualizacja (10 kroków deploy, 14 etapów cutover) |

---

## 7. Testy

```bash
PYTHONPATH=scripts python3 -m pytest \
  tests/unit/test_guardian_frontend_artifacts.py \
  tests/unit/test_guardian_deploy_executors.py \
  tests/unit/test_guardian_ifg_deploy_run_workflow.py \
  tests/unit/test_guardian_container_cutover_workflow.py \
  --no-cov -q
```

**Wynik:** 46 passed

Pokrycie:

- `verify_local_dist` GO / NO_GO (brak index, brak JS)
- parser output remote
- routing komend gate
- compose up zablokowany przy NO_GO
- pipeline — frontend zawsze required mimo Doctor skip
- cutover — 14 etapów w rejestrze

---

## 8. Dry-run cutover (po implementacji)

```bash
PYTHONPATH=scripts python3 -m ifg_guardian ifg cutover run --dry-run
```

| Pole | Wynik |
|------|--------|
| Workflow | **SUCCESS** |
| Safety Gate | **GO** |
| `frontend_build` | pass (simulated) |
| `frontend_artifact_gate` | pass (simulated GO) |
| Cutover executed | False |
| LIVE cutover | nie wykonano |

Raport: `docs/guardian/IFG_CONTAINER_CUTOVER_2026_07_06.md`

---

## 9. Operator — co się zmienia

**Przed LIVE cutover / deploy:**

1. Guardian **zawsze** wykona build frontendu (cutover: na DS723+, deploy: Mac + rsync).
2. Bez `index.html` na hoście → **NO_GO**, kontenery nie wystartują.
3. Ręczny `compose up` poza Guardianem nadal możliwy — gate jest w `ComposeExecutor` tylko dla ścieżki Guardian deploy.

**Zalecenie:** używać wyłącznie `ifg cutover run` / `ifg deploy run` do startu stacku po tej zmianie.

---

*Implementacja zakończona. LIVE cutover nie wykonano.*
