# Guardian Workflow Engine — specyfikacja architektoniczna

**Data:** 2026-06-26  
**Status:** Specyfikacja finalna przed implementacją — **bez kodu**  
**Poprzedniki:** [`GUARDIAN_V3_ARCHITECTURE_REVISED.md`](GUARDIAN_V3_ARCHITECTURE_REVISED.md), [`GUARDIAN_DEPLOY_ORCHESTRATOR.md`](GUARDIAN_DEPLOY_ORCHESTRATOR.md), [`GUARDIAN_CRLF_CLASSIFICATION.md`](GUARDIAN_CRLF_CLASSIFICATION.md)

---

## 0. Werdykt projektowy

Guardian **nie buduje osobnego silnika dla deployu**. Deploy, doctor, repo audit, backup, rollback, recovery i maintenance są **workflow** — różnymi definicjami tego samego **Workflow Engine**.

```
guardian ifg deploy run     ──► Workflow: ifg.deploy.run
guardian doctor             ──► Workflow: core.doctor
guardian repo audit         ──► Workflow: core.repo.audit
guardian ifg backup run     ──► Workflow: ifg.backup.run
guardian ifg rollback       ──► Workflow: ifg.rollback
guardian ifg prod recover   ──► Workflow: ifg.recovery
```

**Deploy Orchestrator** (poprzedni dokument) staje się **jedną definicją workflow** + plugin IFG dostarczający Stage i logikę decyzyjną — nie osobnym modułem `orchestrator/deploy.py`.

---

## 1. Workflow Engine — model uniwersalny

### 1.1 Warstwy systemu

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI                     guardian ifg deploy run --dry-run     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│  Workflow Registry       mapowanie komenda → WorkflowDefinition │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│  Execution Engine (Core)  state machine, retry, abort, timing,  │
│                           logging, transaction, artifacts, report │
└───────────────────────────────┬─────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   Stage Pipeline         Action Executors      Artifact Store
   (plugin definiuje)     (Core wykonuje)       (.guardian/)
          │                     │
          │    GitExecutor      │
          │    SshExecutor      │
          │    DockerExecutor   │
          │    FsExecutor       │
          │    HttpExecutor     │
          └─────────────────────┘
```

### 1.2 Pojęcia

| Pojęcie | Właściciel | Opis |
|---------|------------|------|
| **Workflow** | Plugin / Core | Nazwany pipeline: lista Stage + metadata |
| **WorkflowInstance** | Core | Pojedyncze uruchomienie z ID, stanem, transakcją |
| **Stage** | Plugin | Jednostka pracy; zwraca **plan** (intencje), nie wykonuje I/O |
| **ActionIntent** | Plugin (deklaratywnie) | Opis operacji: „git fetch origin”, „ssh exec compose up” |
| **ActionExecutor** | Core | Wykonuje intent w trybie LIVE lub DRY_RUN |
| **WorkflowTransaction** | Core | Pełny kontekst runu — przed/po, artefakty, outcome |
| **BuildReason** | Plugin + Core | Uzasadnienie każdej decyzji |
| **Artifact** | Core zapisuje | SHA, image ID, raporty — plugin deklaruje typy |

### 1.3 Zasada rozdziału odpowiedzialności

| Plugin robi | Plugin **nie** robi |
|-------------|---------------------|
| Definiuje workflow i Stage | SSH, subprocess, docker CLI |
| Określa warunki skip/retry | Bezpośredni dostęp do git/ssh/docker/fs |
| Dostarcza logikę biznesową (build detector, health rules IFG) | Zna implementację executorów Core |
| Deklaruje ActionIntent + BuildReason | Zarządza state machine |
| Implementuje **RollbackPlan** (co przywrócić) | Wykonuje rollback bez Engine |
| Interpretuje wyniki Stage (PASS/WARN/FAIL) | Pisze raport końcowy (Core renderuje) |

Plugin **nie importuje** `guardian.core.ssh`, `subprocess`, `docker`. Plugin zwraca intencje; Core je realizuje.

---

## 2. State Machine

### 2.1 Diagram

```
                    workflow_created
                          │
                          ▼
                    ┌──────────┐
                    │ UNKNOWN  │
                    └────┬─────┘
                         │ config_valid, plugin_loaded, transaction_init
                         ▼
                    ┌──────────┐
         abort ◄────│  READY   │────► (blocked: CRITICAL precheck w trybie plan)
                    └────┬─────┘
                         │ execute_start [--yes | read-only auto]
                         ▼
                    ┌──────────┐
         abort ◄────│ RUNNING  │────► stage_fail (non-retryable)
                    └────┬─────┘
                         │ all_stages_done | mutating_complete
                         ▼
                    ┌──────────┐
                    │VERIFYING │
                    └────┬─────┘
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
      ┌─────────┐  ┌──────────┐  ┌───────────┐
      │ SUCCESS │  │  FAILED  │  │ROLLED_BACK│
      └─────────┘  └──────────┘  └───────────┘

         ABORTED ◄── z UNKNOWN, READY, RUNNING (user abort / SIGINT / CRITICAL block)
```

### 2.2 Stany — szczegółowo

#### UNKNOWN

| Aspekt | Opis |
|--------|------|
| **Wejście** | Wywołanie CLI; parsowanie argumentów |
| **Co się dzieje** | Tworzenie `WorkflowInstance`; ładowanie `project.yaml`; discovery pluginu; alokacja `workflow_id` |
| **Wyjście** | `WorkflowContext` z pustą transakcją; lista Stage z definicji workflow |
| **Możliwe zdarzenia** | `config_loaded`, `config_invalid`, `plugin_not_found`, `workflow_registered` |
| **Przejścia** | → **READY** gdy config + plugin OK; → **ABORTED** gdy brak pluginu / invalid config |

#### READY

| Aspekt | Opis |
|--------|------|
| **Wejście** | Walidacja zakończona; transakcja utworzona (`start_ts`, `commit_before`, …) |
| **Co się dzieje** | Opcjonalny prompt `[y/N]` dla mutating; snapshot stanu „before” (git HEAD, image, alembic) |
| **Wyjście** | `ExecutionMode` = `LIVE` \| `DRY_RUN`; potwierdzenie użytkownika |
| **Możliwe zdarzenia** | `user_confirmed`, `user_declined`, `dry_run_selected`, `precheck_blocked` (early abort) |
| **Przejścia** | → **RUNNING** po confirm / auto-start (read-only); → **ABORTED** na decline lub CRITICAL block |

#### RUNNING

| Aspekt | Opis |
|--------|------|
| **Wejście** | Pierwszy Stage w kolejności |
| **Co się dzieje** | Engine iteruje Stage: `build_plan()` → execute intents → `interpret()`; retry wg policy; timing per stage |
| **Wyjście** | Lista `StageResult[]`; artefakty pośrednie; `commit_after`, `image_after` (jeśli dotyczy) |
| **Możliwe zdarzenia** | `stage_started`, `stage_completed`, `stage_skipped`, `stage_failed`, `stage_retried`, `abort_requested`, `intent_executed`, `intent_simulated` |
| **Przejścia** | → **VERIFYING** gdy wszystkie Stage done lub pipeline read-only kończy agregację; → **FAILED** gdy fail non-retryable i `on_fail=halt`; → **ABORTED** na SIGINT / user abort |

#### VERIFYING

| Aspekt | Opis |
|--------|------|
| **Wejście** | Stage mutujące zakończone (deploy) lub Stage analityczne (audit/doctor) |
| **Co się dzieje** | Post-validation: health checks, spójność raportu, diff vs expected; ocena rollback eligibility |
| **Wyjście** | `VerificationResult`; `rollback_possible: bool` |
| **Możliwe zdarzenia** | `verify_pass`, `verify_warn`, `verify_fail`, `rollback_started`, `rollback_completed`, `rollback_failed` |
| **Przejścia** | → **SUCCESS** gdy verify pass (WARN dozwolony); → **FAILED** gdy verify fail bez rollback; → **ROLLED_BACK** gdy rollback wykonany pomyślnie |

#### SUCCESS (terminal)

| Aspekt | Opis |
|--------|------|
| **Wejście** | VERIFYING pass |
| **Wyjście** | Raport końcowy; `outcome=SUCCESS`; exit 0; zapis `latest.json` |
| **Zdarzenia** | `workflow_completed`, `artifacts_persisted` |

#### FAILED (terminal)

| Aspekt | Opis |
|--------|------|
| **Wejście** | Stage fail / verify fail / rollback fail |
| **Wyjście** | Raport z `outcome=FAILED`; exit 1; rekomendacje naprawy |
| **Zdarzenia** | `workflow_failed`, `failure_reason` |

#### ROLLED_BACK (terminal)

| Aspekt | Opis |
|--------|------|
| **Wejście** | Verify fail + rollback executed (--rollback-on-fail + --yes) |
| **Wyjście** | Raport z `outcome=ROLLED_BACK`; stan „before” przywrócony częściowo |
| **Zdarzenia** | `rollback_completed`, `partial_restore` |

#### ABORTED (terminal)

| Aspekt | Opis |
|--------|------|
| **Wejście** | User decline, SIGINT, CRITICAL precheck przed mutacją |
| **Wyjście** | Raport `outcome=ABORTED`; exit 2; brak mutacji |
| **Zdarzenia** | `workflow_aborted` |

### 2.3 Mapowanie workflow → VERIFYING

| Workflow | Co w VERIFYING |
|----------|----------------|
| `ifg.deploy.run` | Health HTTP, compose ps, log analysis, alembic head |
| `core.doctor` | Agregacja checków, overall health, delta vs poprzedni run |
| `core.repo.audit` | Spójność klasyfikacji, CRLF verification completeness |
| `ifg.rollback` | Health po rollback, potwierdzenie image/commit restored |
| `ifg.recovery` | Health + cloudflared diag |
| `ifg.backup.run` | Integrity check backupu (checksum, size) |
| `ifg.maintenance.*` | Smoke test po maintenance |

Read-only workflow (audit, doctor, deploy check) **nie przechodzi przez RUNNING mutacji** — VERIFYING = walidacja wyniku analitycznego + zapis raportu.

---

## 3. Workflow Transaction

Każde uruchomienie tworzy **WorkflowTransaction** — jeden rekord prawdy w `.guardian/workflows/`.

### 3.1 Schema (`workflow_transaction_v1`)

```json
{
  "schema": "workflow_transaction_v1",
  "workflow_id": "2026-06-26T143022Z_ifg_deploy_run",
  "workflow_type": "ifg.deploy.run",
  "plugin": "ifg",
  "execution_mode": "LIVE",

  "lifecycle": {
    "state": "SUCCESS",
    "started_at": "2026-06-26T14:30:22Z",
    "ended_at": "2026-06-26T14:34:54Z",
    "duration_ms": 272000
  },

  "host": {
    "local": "mac-mini.local",
    "remote": "ds723",
    "remote_path": "/volume1/docker/ifg_v2/ifg_standalone"
  },

  "git": {
    "commit_before": "b4e1f2a",
    "commit_after": "ac7b339",
    "branch": "production"
  },

  "docker": {
    "image_before": "sha256:abc123...",
    "image_after": "sha256:def456...",
    "containers_restarted": ["api", "worker"]
  },

  "alembic": {
    "revision_before": "770c033eeb7f",
    "revision_after": "cb43e5557073"
  },

  "frontend": {
    "bundle_hash_before": "a1b2c3...",
    "bundle_hash_after": "d4e5f6...",
    "built": true,
    "synced": true
  },

  "stages": [
    {
      "id": "precheck",
      "status": "pass",
      "duration_ms": 12000,
      "reasons": []
    },
    {
      "id": "build_decision",
      "status": "pass",
      "reasons": [
        {
          "decision": "backend_build",
          "because": ["app/services/payment_service.py"]
        }
      ]
    }
  ],

  "artifacts": [
    { "type": "deploy_report", "path": ".guardian/workflows/.../deploy_report.json" },
    { "type": "health_report", "path": ".guardian/workflows/.../health_report.json" }
  ],

  "outcome": "SUCCESS",
  "rollback_possible": false,
  "rollback_executed": false,

  "warnings": [],
  "recommended_actions": []
}
```

### 3.2 Snapshot „before”

Engine w stanie **READY** zbiera snapshot ( przez intencje read-only):

| Pole | Źródło (Core executor) |
|------|------------------------|
| `commit_before` | `git rev-parse HEAD` |
| `image_before` | `docker inspect ifg-api:latest` (remote) |
| `alembic_before` | `docker compose exec api alembic current` |
| `bundle_hash_before` | hash `dist/assets/*.js` (local lub remote) |

Snapshot umożliwia rollback i Build Detector (`last_successful_deploy`).

### 3.3 Persystencja

```
.guardian/
  workflows/
    index.json                           # indeks wszystkich runów
    2026-06-26T143022Z_ifg_deploy_run/
      transaction.json                   # WorkflowTransaction
      workflow_report.json               # raport unifikowany
      deploy_report.json                 # artifact pluginu
      health_report.json
      stages/
        01_precheck.json
        02_fetch.json
        ...
  latest/
    ifg_deploy_run.json                  # ostatni udany deploy
    doctor.json
    repo_audit.json
```

---

## 4. Stage API

### 4.1 Interfejs Stage (koncept)

```python
class Stage(ABC):
    """Plugin definiuje Stage — zero I/O."""

    id: str                          # np. "precheck"
    label: str                       # "Safety precheck"
    mutating: bool                   # False dla precheck, True dla deploy
    optional: bool                   # skip bez FAIL gdy warunek niespełniony
    retry_policy: RetryPolicy        # patrz §10

    def should_skip(self, ctx: WorkflowContext) -> SkipReason | None:
        """Np. skip FrontendBuild gdy build_plan.frontend=False."""

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        """
        Zwraca listę ActionIntent + BuildReason.
        Wywoływane w LIVE i DRY_RUN identycznie.
        """

    def interpret(
        self, ctx: WorkflowContext, results: StageExecutionResults
    ) -> StageResult:
        """
        Ocena PASS/WARN/FAIL na podstawie wyników executorów.
        Może zwrócić rollback_hint (plugin), nie wykonuje rollback.
        """
```

### 4.2 StagePlan

```python
@dataclass
class StagePlan:
    intents: list[ActionIntent]
    reasons: list[BuildReason]
    on_fail: Literal["halt", "continue", "verify"] = "halt"
    verify_after: bool = False       # wymusza mini-verify po stage
```

### 4.3 Przykład — Deploy Workflow (plugin IFG)

```python
DeployRunWorkflow = WorkflowDefinition(
    id="ifg.deploy.run",
    plugin="ifg",
    mutating=True,
    requires_yes=True,
    stages=[
        PrecheckStage(),
        FetchStage(),
        PullLocalStage(),
        BuildDecisionStage(),
        FrontendBuildStage(),      # optional — skip via should_skip
        SyncDistStage(),           # optional
        PullRemoteStage(),
        DockerBuildStage(),        # optional
        DeployStage(),
        HealthStage(),             # verify_after=True → VERIFYING overlap
        LogAnalysisStage(),
        SummaryStage(),
    ],
)
```

### 4.4 Przykład — Doctor Workflow (core + pluginy)

```python
DoctorWorkflow = WorkflowDefinition(
    id="core.doctor",
    plugin=None,                   # multi-plugin fan-out
    mutating=False,
    stages=[
        InitStage(),
        CoreGitStage(),
        CoreSshStage(),
        CoreDockerStage(),
        PluginChecksStage(),       # dynamic: każdy plugin → sub-stage
        AggregateStage(),
        HistoryDeltaStage(),
        SummaryStage(),
    ],
)
```

### 4.5 Przykład — Repo Audit Workflow

```python
RepoAuditWorkflow = WorkflowDefinition(
    id="core.repo.audit",
    mutating=False,
    stages=[
        CollectGitStatusStage(),
        ClassifyFilesStage(),      # core generic + plugin risk_checks
        LineEndingAnalysisStage(), # reuse line_endings.py logic via intents
        RiskAggregateStage(),
        RecommendedActionsStage(),
        ReportStage(),
    ],
)
```

### 4.6 ActionIntent — typy (Core)

Plugin składa intencje z katalogu Core:

| Intent | Parametry (przykład) | Executor |
|--------|----------------------|----------|
| `GitFetchIntent` | remote=origin | GitExecutor |
| `GitPullIntent` | branch=production | GitExecutor |
| `GitRevParseIntent` | ref=HEAD | GitExecutor |
| `GitDiffIntent` | range=last..HEAD, paths=[] | GitExecutor |
| `SshExecIntent` | host, command, cwd | SshExecutor |
| `SshReadFileIntent` | host, path | SshExecutor |
| `DockerComposeConfigIntent` | compose_file, env_file | DockerExecutor |
| `DockerComposeBuildIntent` | services=[api] | DockerExecutor |
| `DockerComposeUpIntent` | services=[api, worker] | DockerExecutor |
| `DockerComposePsIntent` | | DockerExecutor |
| `DockerComposeExecIntent` | service=api, command=[alembic, upgrade, head] | DockerExecutor |
| `DockerInspectIntent` | image=ifg-api:latest | DockerExecutor |
| `DockerLogsIntent` | service=api, since=5m | DockerExecutor |
| `FsHashIntent` | glob=frontend-react/dist/assets/*.js | FsExecutor |
| `FsExistsIntent` | path=.env.production | FsExecutor |
| `HttpGetIntent` | url=http://127.0.0.1:8000/health | HttpExecutor |
| `LocalExecIntent` | command=[npm, run, build], cwd=frontend-react | LocalExecExecutor |
| `NoOpIntent` | reason="docs-only: skip build" | — (DRY_RUN log only) |

**Plugin nie tworzy nowych executorów** — rozszerzenie listy intentów wymaga zmiany Core (rzadko).

---

## 5. Execution Engine

### 5.1 Odpowiedzialności Core

| Odpowiedzialność | Opis |
|------------------|------|
| **Kolejność** | Iteracja Stage wg definicji; respect `should_skip` |
| **Retry** | Polityka per Stage; exponential backoff |
| **Abort** | SIGINT → graceful ABORTED; zapis partial transaction |
| **Rollback dispatch** | W VERIFYING: jeśli plugin zwrócił `RollbackPlan` i flagi OK → wykonaj intencje rollback |
| **Timing** | `duration_ms` per stage, per intent, total |
| **Logowanie** | Structured log: workflow_id, stage_id, intent_id, correlation |
| **Zbieranie wyników** | `StageExecutionResults` → `WorkflowTransaction` |
| **Raport końcowy** | Render terminal / markdown / json z jednego modelu |

### 5.2 Pętla wykonania

```
for stage in workflow.stages:
    if stage.should_skip(ctx):
        record SKIP with reason
        continue

    plan = stage.build_plan(ctx)          # plugin — czysta logika
    record plan.reasons → transaction

    for attempt in retry_policy:
        results = engine.execute(plan.intents, mode)   # Core — I/O
        if all_intents_ok(results):
            break
        if not retry_policy.allows_retry(stage, results):
            break

    stage_result = stage.interpret(ctx, results)       # plugin — ocena
    record stage_result → transaction

    if stage_result.status == FAIL and plan.on_fail == "halt":
        transition RUNNING → FAILED (or VERIFYING if verify_after)
        break

    if stage_result.verify_after:
        queue for VERIFYING phase

if mutating and not failed:
    transition RUNNING → VERIFYING
    run verification stages / hooks
    evaluate rollback eligibility
```

### 5.3 ExecutionMode

```python
class ExecutionMode(Enum):
    LIVE = "live"           # pełne wykonanie intencji mutujących
    DRY_RUN = "dry_run"     # ten sam pipeline; mutacje → simulate/log
    PLAN = "plan"           # alias DRY_RUN + rozszerzony BuildReason output
```

**Zasada:** jeden pipeline, jedna definicja Stage. `DRY_RUN` **nie duplikuje** workflow.

| Intent w DRY_RUN | Zachowanie |
|------------------|------------|
| Read-only (git status, curl health) | **Wykonaj** — potrzebne do planu |
| Mutating (pull, build, up, rsync) | **Simulate** — log `[dry-run] would: ...`, zwróć synthetic OK |
| `requires_yes` | Ignorowane — DRY_RUN nigdy nie mutuje |

`guardian ifg deploy run --dry-run` = pełny `build_plan()` + simulate + raport „co by się stało”.

---

## 6. Plugin Responsibility — wzorzec deklaratywny

### 6.1 Przykład BuildDecisionStage (plugin IFG)

Plugin **nie** woła `git diff`. Plugin zwraca:

```python
def build_plan(self, ctx):
    return StagePlan(
        intents=[
            GitDiffIntent(range=f"{ctx.last_deploy_sha}..HEAD"),
            GitDiffIntent(range="origin/production..HEAD", fallback=True),
            FsHashIntent(glob="frontend-react/dist/assets/*.js"),
        ],
        reasons=[],  # uzupełnione w interpret()
    )

def interpret(self, ctx, results):
    changed_files = results.get(GitDiffIntent).files
    plan = build_detector.analyze(changed_files)   # czysta logika Python
    return StageResult(
        status=PASS,
        data={"build_plan": plan},
        reasons=[
            BuildReason("frontend_build", ["frontend-react/src/pages/Invoice.jsx"]),
            BuildReason("backend_build", ["app/services/payment_service.py"]),
        ],
    )
```

### 6.2 Plugin API (rozszerzenie GUARDIAN_V3)

```python
class GuardianPlugin(ABC):
    def workflows(self) -> list[WorkflowDefinition]: ...
    def stages_for(self, workflow_id: str) -> list[Stage]: ...  # opcjonalnie factory
    def rollback_plan(self, ctx: WorkflowContext, failure: StageResult) -> RollbackPlan | None: ...
```

Core **nie zna** IFG, KSeF, warehouse — zna `WorkflowDefinition` i `ActionIntent`.

---

## 7. Dry Run

### 7.1 Zasady

1. **Identyczny** `WorkflowDefinition` i kolejność Stage.
2. `ExecutionMode.DRY_RUN` ustawiane w READY.
3. `build_plan()` — **identyczne** wywołania; plugin nie sprawdza `if dry_run`.
4. Executors rozróżniają mutację:

```python
class DockerComposeUpIntent(ActionIntent):
    mutating = True

# DockerExecutor.execute(intent, mode):
if mode == DRY_RUN and intent.mutating:
    return SimulatedResult(command=intent.describe(), status=SIMULATED_OK)
```

5. Raport DRY_RUN zawiera sekcję **Would execute** z pełnymi BuildReason.

### 7.2 Komendy

| Komenda | Mode |
|---------|------|
| `guardian ifg deploy run --dry-run` | DRY_RUN |
| `guardian ifg deploy plan` | PLAN (= DRY_RUN + tylko do BuildDecisionStage) |
| `guardian repo audit` | LIVE read-only (brak mutacji z natury) |
| `guardian repo clean` | DRY_RUN (już dziś read-only) |

---

## 8. Build Reasons

Każda decyzja workflow musi mieć **BuildReason** — audytowalne uzasadnienie.

### 8.1 Model

```python
@dataclass
class BuildReason:
    decision: str           # np. "backend_build", "skip_frontend", "rollback"
    because: list[str]      # ścieżki plików, check IDs, lub opisy
    confidence: str = "HIGH"  # opcjonalnie — spójne z CRLF Confidence
    source_stage: str = ""    # np. "build_decision"
```

### 8.2 Przykłady

| Decision | Because |
|----------|---------|
| `frontend_build` | `frontend-react/src/pages/Invoice.jsx`, `frontend-react/vite.config.js` |
| `backend_build` | `app/services/payment_service.py`, `alembic/versions/cb43e5557073.py` |
| `skip_docker_build` | `docs/GUARDIAN_WORKFLOW_ENGINE.md` (docs-only) |
| `sync_dist` | `build_plan.frontend=true` |
| `alembic_upgrade` | `alembic/versions/*.py` changed |
| `deploy_blocked` | `precheck.branch: not production` |
| `rollback_recommended` | `health.http: FAIL`, `Health check timeout after 60s` |
| `crlf_unknown_no_restore` | `app/api/deps.py` (UNKNOWN_LINE_ENDINGS) |

### 8.3 Raportowanie

BuildReason trafia do:
- `WorkflowTransaction.stages[].reasons`
- sekcji raportu **Decisions**
- JSON `--format json` (pole `decisions[]`)

---

## 9. Artifacts

### 9.1 Typy artefaktów

| Artifact | Workflow | Zawartość |
|----------|----------|-----------|
| `git_sha` | wszystkie | commit before/after |
| `docker_image_id` | deploy, rollback | image digest |
| `frontend_bundle_hash` | deploy | hash dist/assets |
| `alembic_revision` | deploy, recovery | revision before/after |
| `workflow_report` | wszystkie | unifikowany raport Engine |
| `deploy_report` | ifg.deploy.* | sekcje specyficzne IFG |
| `health_report` | deploy, recovery, rollback | wyniki health stage |
| `doctor_report` | core.doctor | aggregated checks |
| `repo_audit_report` | core.repo.audit | klasyfikacja plików |
| `backup_manifest` | ifg.backup.run | lista plików, checksum |
| `rollback_report` | ifg.rollback | co przywrócono |

### 9.2 Zapis

Engine zapisuje artefakty **automatycznie** po SUCCESS/FAILED/ROLLED_BACK. Plugin deklaruje w Stage:

```python
def interpret(...) -> StageResult:
    return StageResult(
        artifacts=[
            ArtifactSpec(type="health_report", producer="health_json"),
        ],
    )
```

Core renderuje producent → plik w katalogu transaction.

### 9.3 Eksport

```bash
guardian ifg deploy run --format markdown -o docs/guardian/DEPLOY_REPORT.md
```

Kopia artefaktu do `docs/guardian/` — opcjonalna; `.guardian/` zawsze source of truth.

---

## 10. Retry Policy

### 10.1 Model

```python
@dataclass
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0
    retry_on: list[str] = []    # intent error codes
    human_required: bool = False
```

### 10.2 Macierz Stage — Deploy Workflow

| Stage | Retry | max | Human required gdy |
|-------|-------|-----|---------------------|
| Precheck | ❌ | 0 | CRITICAL fail — napraw ręcznie |
| Fetch | ✅ | 3 | network timeout |
| Pull (local/remote) | ❌ | 0 | merge conflict |
| Build Decision | ❌ | 0 | — |
| Frontend Build | ❌ | 0 | npm error — napraw kod |
| Sync Dist | ✅ | 2 | SSH transient |
| Docker Build | ❌ | 0 | Dockerfile error |
| Deploy (up) | ✅ | 2 | pull image transient |
| Alembic | ❌ | 0 | **zawsze human** — migration fail |
| Health | ✅ | 12 | poll co 5s (60s total) |
| Log Analysis | ❌ | 0 | — |
| Summary | ❌ | 0 | — |

### 10.3 Macierz — Doctor / Audit

| Stage | Retry | Uwagi |
|-------|-------|-------|
| SSH check | ✅ 2 | transient |
| Plugin checks | ❌ | fail → raport, continue other plugins |
| CRLF analysis | ❌ | per-file, skip on read error |

### 10.4 Zasady globalne

1. **Nigdy retry** Stage mutujących z side-effects (alembic, git merge).
2. **Health poll** = retry wbudowany (nie liczy się jako `max_attempts` Stage).
3. Po wyczerpaniu retry → `stage_failed` → `on_fail` policy.
4. `human_required=True` → raport z `Recommended Action`; Engine nie retry dalej.

---

## 11. Rollback Engine

### 11.1 Podział odpowiedzialności

| Warstwa | Odpowiedzialność |
|---------|------------------|
| **Core Rollback Engine** | Wie **czy** rollback możliwy; ma snapshot „before”; wykonuje `RollbackPlan` intencjami |
| **Plugin** | Dostarcza **RollbackPlan** — listę intencji przywracających stan |

### 11.2 Rollback eligibility (Core)

```python
def rollback_possible(ctx: WorkflowContext) -> bool:
    return (
        ctx.transaction.outcome != "ABORTED"
        and ctx.snapshot.image_before is not None
        and ctx.mutating_stages_executed > 0
        and not ctx.transaction.rollback_executed
    )
```

Core **nie wie** jak rollbackować IFG vs PSAG — pyta plugin:

```python
plan = plugin.rollback_plan(ctx, failure=last_failure)
if plan and ctx.flags.rollback_on_fail and ctx.flags.yes:
    engine.execute(plan.intents, mode=LIVE)
    transition → ROLLED_BACK
```

### 11.3 RollbackPlan (plugin IFG — przykład)

```python
RollbackPlan(
    reasons=[BuildReason("rollback", ["Health FAIL: /health timeout"])],
    intents=[
        DockerComposeUpIntent(image=ctx.snapshot.image_before),
        SshExecIntent(command="restore dist from backup tarball"),  # jeśli dist backup istnieje
    ],
    excludes=[AlembicDowngradeIntent],  # nigdy auto
)
```

### 11.4 Osobny workflow Rollback

`guardian ifg rollback` to **osobny workflow** (nie automatyczny), ale używa tego samego Engine:

```
PrecheckStage → ValidateSnapshotStage → RollbackExecuteStage → HealthStage → SummaryStage
```

---

## 12. Mapowanie workflow → obecny kod (donor)

| Workflow | Źródło donor code | Stage reuse |
|----------|-------------------|-------------|
| `ifg.deploy.run` | `deploy-ds723.sh`, `deploy.py`, `frontend.py`, `production.py` | BuildDecision, Health |
| `ifg.deploy.check` | `deploy.py` | read-only subset Precheck+Verify |
| `core.doctor` | `doctor` w cli, moduły check | PluginChecksStage |
| `core.repo.audit` | `repo.py`, `line_endings.py` | LineEndingAnalysisStage |
| `ifg.recovery` | `guardian2 recover-prod` | RecoveryStage |
| `ifg.rollback` | WORKFLOW.md rollback | RollbackExecuteStage |

---

## 13. Integracja z CRLF Classification

Repo audit Stage `LineEndingAnalysisStage` używa intencji:

```
GitShowBlobIntent(HEAD), GitShowBlobIntent(index), FsReadIntent(worktree)
GitDiffIntent(--ignore-cr-at-eol), GitLsFilesEolIntent, LocalExecIntent(file)
```

Logika klasyfikacji pozostaje w pluginie (przeniesienie `line_endings.py`); Engine wykonuje odczyty. BuildReason:

```
Decision: unknown_line_endings
Because: app/api/deps.py (HEAD==index==worktree, restore simulation negative)
```

Spójne z [`GUARDIAN_CRLF_CLASSIFICATION.md`](GUARDIAN_CRLF_CLASSIFICATION.md).

---

## 14. Roadmapa implementacji

### Etap 1 — Workflow Engine (Core)

| Deliverable | Zakres |
|-------------|--------|
| State machine | UNKNOWN → … → terminal states |
| WorkflowTransaction | schema v1, zapis `.guardian/workflows/` |
| Stage API | `Stage`, `StagePlan`, `ActionIntent` katalog |
| Execution Engine | pętla, timing, abort, DRY_RUN simulate |
| Executors | Git, LocalExec, Fs (minimal) |
| Raport | workflow_report.json + terminal |
| Test workflow | `core.ping` — jeden Stage, read-only |

**Kryterium done:** `guardian workflow run core.ping` działa w LIVE i DRY_RUN.

### Etap 2 — Deploy Engine (plugin IFG)

| Deliverable | Zakres |
|-------------|--------|
| `ifg.deploy.run` workflow | wszystkie Stage z DEPLOY_ORCHESTRATOR |
| Executors | Ssh, Docker, Http |
| Build Detector | BuildReason, skip logic |
| Artifacts | deploy_report, health_report |
| Shim | `deploy-ds723.sh` → wywołuje orchestrator |

**Kryterium done:** `guardian ifg deploy run --dry-run` pełny plan; `--yes` zastępuje bash.

### Etap 3 — Doctor

| Deliverable | Zakres |
|-------------|--------|
| `core.doctor` workflow | fan-out plugin checks |
| History delta | diff vs `.guardian/latest/doctor.json` |
| Agregacja | overall health/risk |

**Kryterium done:** `guardian doctor` używa Engine; JSON schema zgodny z REVISED §5.2.

### Etap 4 — Repo Audit

| Deliverable | Zakres |
|-------------|--------|
| `core.repo.audit` workflow | classify + CRLF stage |
| Plugin risk_checks | IFG rozszerzenia |
| Raport | REPO_AUDIT z Verification |

**Kryterium done:** `guardian repo audit` = workflow; CRLF verification w Stage.

### Etap 5 — Recovery

| Deliverable | Zakres |
|-------------|--------|
| `ifg.recovery` workflow | ex recover-prod |
| RollbackPlan | health fail → recommend |

**Kryterium done:** `guardian ifg prod recover --yes` przez Engine.

### Etap 6 — Backup

| Deliverable | Zakres |
|-------------|--------|
| `ifg.backup.run` | pg_dump / dist backup / config snapshot |
| Artifacts | backup_manifest |

**Kryterium done:** backup przed deploy opcjonalny `--backup`.

### Etap 7 — IFGM

| Deliverable | Zakres |
|-------------|--------|
| Plugin IFGM | własne workflow definitions |
| Weryfikacja | Core API wystarczające bez zmian |

**Kryterium done:** `guardian ifgm deploy run` bez modyfikacji Core.

### Etap 8 — PSAG

| Deliverable | Zakres |
|-------------|--------|
| Plugin PSAG | watchers/mail/cron workflow |
| Brak Docker IFG | inne intencje (systemd, mailq) — **nowe executory w Core** |

**Kryterium done:** PSAG jako trzeci consumer; ewentualne rozszerzenie katalogu Intent.

---

## 15. ADR — decyzje architektoniczne

| # | Decyzja | Alternatywa odrzucona |
|---|---------|------------------------|
| ADR-W1 | Jeden Workflow Engine dla wszystkich operacji | Osobny Deploy Orchestrator |
| ADR-W2 | Plugin deklaruje intencje; Core wykonuje | Plugin woła SSH/docker bezpośrednio |
| ADR-W3 | DRY_RUN = ten sam pipeline | Osobny „plan mode” z duplikacją Stage |
| ADR-W4 | WorkflowTransaction zawsze | Raport tylko stdout |
| ADR-W5 | VERIFYING jako osobny stan | Health jako zwykły Stage bez rozróżnienia |
| ADR-W6 | RollbackPlan od pluginu | Core hardcoded IFG rollback |
| ADR-W7 | BuildReason obowiązkowy | Decyzje bez audytu |
| ADR-W8 | Read-only też przez Engine | Doctor/audit poza Engine |

---

## 16. Relacja do poprzednich dokumentów

| Dokument | Status po Workflow Engine |
|----------|---------------------------|
| `GUARDIAN_V3_ARCHITECTURE_REVISED.md` | Plugin API rozszerzone o `workflows()`; doctor/deploy przez Engine |
| `GUARDIAN_DEPLOY_ORCHESTRATOR.md` | Stage list dla `ifg.deploy.run`; nie osobny orchestrator |
| `GUARDIAN_CRLF_CLASSIFICATION.md` | Stage w repo audit; intencje read-only via Core |

---

*Dokument finalny przed implementacją. Następny krok: Etap 1 — Workflow Engine (Core skeleton).*
