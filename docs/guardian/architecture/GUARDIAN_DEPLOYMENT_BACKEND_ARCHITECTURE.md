Status: Approved
Owner: Guardian Core
Depends on: docs/reports/IFG_CONTAINER_MANAGER_MIGRATION.md, docs/GUARDIAN_V3_ARCHITECTURE_REVISED.md, Canon/GUARDIAN_CANON_V1.md (guardian repo)
Required by: GWO (future) — Execution Backend / Operation Engine implementation
Last Reviewed: 2026-07-05
Next Review: 2026-10-05

# Guardian — Deployment Backend Architecture

**Document type:** Architecture & migration plan (no implementation)  
**Scope:** IFG production on DS723+ (Synology Container Manager) + Mac mini (Guardian control plane)  
**Version:** 1.0

> **Version note:** Sections 1–14 describe the **v0.1 foundation** (Deployment-centric model).  
> Sections 15–23 extend the same philosophy to **Guardian as a universal Operation Engine** (v1.0).  
> Terminology evolution: `DeploymentBackend` → `ExecutionBackend` (see §15). No prior content removed.

---

## 1. Executive summary

Guardian today deploys IFG by **SSH + `docker compose`** on DS723+. Synology **Container Manager → Projekt** exposes the same stack as a first-class **Project** (Compose under the hood), but DSM tracks lifecycle, health, and UI grouping separately from raw container names (`docker-api-1` vs project **`ifg`**).

This document defines:

1. A **backend-agnostic Deployment Engine** with a stable operation surface (`deploy`, `restart`, `stop`, `start`, `status`, `logs`, `health`, `rollback`).
2. Two backends during transition: **`compose` (Legacy)** and **`synology_project` (target)**.
3. A **five-stage migration plan** from Legacy Compose to Project-default.
4. An analysis of whether Guardian should abstract entirely to **DeploymentProject** (enabling Kubernetes, Portainer, Swarm later).

**No code, deploy, or repo changes** are part of this document — design only.

---

## 2. Target model

```
GitHub (production branch)
        ↓
Mac mini — Guardian (control plane)
        ↓
Deployment Engine (backend-agnostic facade)
        ↓
┌───────────────────┬────────────────────────────┐
│  ComposeBackend   │  SynologyProjectBackend     │
│  (Legacy)         │  (target)                   │
└─────────┬─────────┴──────────────┬─────────────┘
          │                        │
          └──────────┬─────────────┘
                     ↓
        Synology DS723+ — Container Manager
                     ↓
              Project: ifg
                     ↓
        ┌────────────┼────────────┐
        api      worker      db
        (+ frontend bind-mount in api)
```

**Principle:** Guardian **Workflow** layers call only the Deployment Engine. They never import `docker compose` or `synowebapi` directly.

---

## 3. Current state (IFG + Guardian)

### 3.1 IFG production stack

| Element | Value |
|---------|--------|
| Repo path (DS723+) | `/volume1/docker/ifg_v2/ifg_standalone` |
| Compose file | `docker/docker-compose.prod.yml` |
| Env | `.env.production` |
| Services | `api`, `worker`, `db` |
| Frontend | bind mount `frontend-react/dist` → API (not separate container) |
| Compose project name (today) | **`docker`** (implicit from compose file directory) |
| Postgres volume | **`docker_postgres_data`** (must be preserved) |

See: [IFG_CONTAINER_MANAGER_MIGRATION.md](../../reports/IFG_CONTAINER_MANAGER_MIGRATION.md).

### 3.2 Guardian today (`ifg_standalone/scripts/ifg_guardian`)

| Component | Role |
|-----------|------|
| `deploy_run/pipeline.py` | Builds step list with hardcoded `docker compose` commands |
| `ComposeExecutor` | SSH remote `compose up`, `compose logs` |
| `core/compose.py` | Parse `compose ps`, health predicates |
| `guardian2.py` | Legacy MVP: `sudo docker compose -f docker/docker-compose.prod.yml` |
| `DS723Config` | Host, repo path, compose file, env file, Container Manager `PATH` |

**Gap:** Workflow and pipeline are **Compose-coupled**. No concept of Synology Project ID, no `synowebapi`, no backend selection.

---

## 4. Synology Container Manager — research findings

### 4.1 How Synology stores Projects

Container Manager **Project** = **Docker Compose stack** registered in DSM with:

| Attribute | Description |
|-----------|-------------|
| **UUID `id`** | Stable identifier used by API (`bddfea05-8010-4dd9-...`) |
| **Human `name`** | Display name in UI (target: **`ifg`**) |
| **Compose path** | Directory on NAS containing `compose.yml` / `docker-compose.yml` |
| **Container IDs** | Linked containers managed as project members |
| **State** | running / stopped (aggregate project state in UI) |

Under the hood Synology uses **docker-compose** (Container Manager ≥ DSM 7.2). Projects are **not** a separate orchestrator — they are **DSM-managed Compose projects** with lifecycle API and UI grouping.

Package developers can register projects via SPK `docker-project` worker (name + path + build_params). IFG uses **manual/UI or CLI registration** from existing repo path, not SPK.

### 4.2 Compose import in Container Manager

DSM supports:

- **UI:** Container Manager → Projekt → Utwórz → import from `docker-compose.yml` path on NAS.
- **Developer SPK:** `docker-project.projects[]` with `name` + `path` relative to package target.
- **CLI/API:** Creating/updating project registry from an **existing compose file path** on the filesystem (same files Guardian already maintains via `git pull`).

**Implication for IFG:** No need to duplicate compose to a second location if Project points at  
`/volume1/docker/ifg_v2/ifg_standalone/docker/docker-compose.prod.yml` (or symlinked `compose.yaml` in project directory). Project **references** the compose file; `git pull` updates source of truth.

### 4.3 API availability

Official / de-facto APIs (DSM 7.x):

| API | Purpose |
|-----|---------|
| **`SYNO.Docker.Project`** | Project lifecycle: `list`, `start`, `stop`, `start_stream`, `build` (reported) |
| **`SYNO.Docker.Container`** | Per-container ops |
| **`SYNO.Docker.Container.Log`** | Logs |
| **`SYNO.Docker.Network`**, **`SYNO.Docker.Image`** | Supporting resources |
| **`SYNO.API.Auth`** | Session / token for HTTP WebAPI |

**CLI on NAS (root):** `synowebapi --exec api=SYNO.Docker.Project version=1 method=<method> ...`

Examples from community documentation:

```bash
# List projects (resolve UUID by name)
synowebapi --exec api=SYNO.Docker.Project version=1 method=list

# Start / stop (note quoting of id)
synowebapi --exec api=SYNO.Docker.Project version=1 method=start 'id="PROJECT_UUID"'
synowebapi --exec api=SYNO.Docker.Project version=1 method=stop  'id="PROJECT_UUID"'

# Build / update (rebuild from compose on disk)
synowebapi --exec api=SYNO.Docker.Project version=1 method=build 'id="PROJECT_UUID"'
```

**Streaming:** UI uses `start_stream` for progress; automation may use non-stream `start` / `build`.

**HTTP WebAPI:** Same methods via `/webapi/entry.cgi` with authenticated session — suitable for remote Guardian if credentials managed securely (prefer SSH + `synowebapi` on NAS to avoid exposing DSM API to Mac mini).

### 4.4 CLI operations matrix (Project backend)

| Guardian op | Synology mechanism | Notes |
|-------------|-------------------|--------|
| **start** | `SYNO.Docker.Project` `method=start` | Uses project UUID |
| **stop** | `method=stop` | Stops all project containers; DSM-aware (fewer false alerts than raw `docker stop`) |
| **restart** | `stop` + `start`, or `build` with recreate | No single `restart` method documented — compose as `stop`→`start` or `build` |
| **update / deploy** | `method=build` + pre-steps (`git pull`, image build) | `build_params`: force_recreate, build, force_pull (SPK worker) |
| **status** | `method=list` or `get` / project info | Map to `DeploymentStatus` |
| **logs** | `SYNO.Docker.Container.Log` or fallback `docker compose logs` via SSH | Prefer project-scoped log aggregation in backend |
| **health** | HTTP check + project/container state | Same as today (`curl /health`); backend supplies reachability |

### 4.5 Limitations & risks

| Topic | Risk | Mitigation |
|-------|------|------------|
| Project UUID | Opaque, may change if project recreated | Store in Profile config; resolve by `name=ifg` via `list` |
| API stability | Undocumented WebAPI; version drift | Pin DSM version in Profile; integration tests on DS723+ |
| `synowebapi` requires root | SSH as root or sudo | Guardian SSH executor already uses sudo patterns |
| Build vs compose CLI | DSM `build` may differ from manual `docker compose build` | Backend implements deploy as **ordered sub-steps** with explicit compose build phase if needed |
| Dual control | Compose CLI + DSM API on same project | **Single backend active** per environment; Legacy locked during migration |
| Volume rename on project rename | See IFG migration report | Pin `external: true` on `docker_postgres_data` |

### 4.6 Can Project be updated from CLI?

**Yes**, with caveats:

1. **Filesystem update:** `git pull` in repo (Guardian already does this).
2. **Project rebuild:** `SYNO.Docker.Project` `method=build` (or compose build via SSH before build).
3. **Lifecycle:** `start` / `stop` via `synowebapi`.

Full **project registration** (first-time create) is typically UI-driven or SPK; for IFG migration: **one-time** create Project **`ifg`** pointing at compose path, then Guardian only **updates** via build/start.

---

## 5. Architectural design

### 5.1 Layering

```
┌─────────────────────────────────────────────────────────┐
│  Guardian CLI / Plugins (ifg deploy run, recover-prod)   │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  GuardianWorkflow                                        │
│    deploy() recover() verify() update()                  │
│    (orchestration, git, frontend, alembic — agnostic)    │
└───────────────────────────┬─────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│  DeploymentEngine                                        │
│    backend: DeploymentBackend                            │
│    deploy|restart|stop|start|status|logs|health|rollback │
└───────────────────────────┬─────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          ▼                                   ▼
┌──────────────────┐              ┌──────────────────────┐
│ ComposeBackend   │              │ SynologyProjectBackend│
│ (legacy)         │              │ (target)              │
└────────┬─────────┘              └──────────┬───────────┘
         │                                    │
         └────────────────┬───────────────────┘
                          ▼
              SSH / Local Executor (existing)
                          ▼
                   DS723+ host
```

### 5.2 Core domain types (backend-agnostic)

```python
# Conceptual — not implemented

@dataclass(frozen=True)
class DeploymentTarget:
    host: str
    repo_path: str
    profile: str                    # "ifg"
    environment: str                # "production"

@dataclass(frozen=True)
class DeploymentProjectRef:
    name: str                       # "ifg"
    external_id: str | None         # Synology UUID (optional for compose)
    compose_file: str               # docker/docker-compose.prod.yml
    env_file: str                   # .env.production

@dataclass
class DeploymentStatus:
    project_name: str
    backend: str                    # "compose" | "synology_project"
    overall: str                    # "healthy" | "degraded" | "stopped" | "unknown"
    services: dict[str, ServiceStatus]  # api, worker, db
    raw: dict                       # backend-specific debug

@dataclass
class DeploymentResult:
    ok: bool
    operation: str
    message: str
    status: DeploymentStatus | None
    artifacts: dict                 # logs excerpt, command transcript
```

Workflows consume **only** these types — never raw `docker ps` lines.

### 5.3 `DeploymentBackend` interface

```python
class DeploymentBackend(Protocol):
    name: str  # "compose" | "synology_project"

    def deploy(self, ctx: DeployContext) -> DeploymentResult: ...
    def restart(self, ctx: DeployContext, *, services: list[str] | None = None) -> DeploymentResult: ...
    def stop(self, ctx: DeployContext) -> DeploymentResult: ...
    def start(self, ctx: DeployContext) -> DeploymentResult: ...
    def status(self, ctx: DeployContext) -> DeploymentStatus: ...
    def logs(self, ctx: LogContext) -> DeploymentResult: ...
    def health(self, ctx: DeployContext) -> DeploymentResult: ...
    def rollback(self, ctx: RollbackContext) -> DeploymentResult: ...
```

**`DeployContext`** includes: target, project ref, dry_run, options (force_recreate, build_images, skip_migrations).

### 5.4 `ComposeBackend` (Legacy)

**Responsibility:** Current behavior — SSH + `docker compose`.

| Operation | Implementation sketch |
|-----------|----------------------|
| deploy | `git pull` (workflow) → `compose build` → `alembic` → `compose up -d` |
| restart | `compose up -d --force-recreate [services]` |
| stop | `compose stop` |
| start | `compose up -d` |
| status | `compose ps` → parse to `DeploymentStatus` |
| logs | `compose logs --tail=N` |
| health | `curl /health` + compose ps healthy |
| rollback | `git checkout` + `compose up -d` |

Maps 1:1 to existing `ComposeExecutor`, `guardian2.py`, `deploy_run/pipeline.py`.

**Config:** `DS723Config.compose_file`, `--env-file .env.production`, optional `-p` / compose `name:` from file.

### 5.5 `SynologyProjectBackend` (target)

**Responsibility:** DSM Project lifecycle via `synowebapi` (+ selective compose for build when API insufficient).

| Operation | Implementation sketch |
|-----------|----------------------|
| deploy | Pre: workflow git/fe/npm/rsync → SSH `compose build` (if needed) → `synowebapi ... method=build id=UUID` → verify |
| restart | `stop` + `start`, or `build` with force_recreate |
| stop | `synowebapi method=stop` |
| start | `synowebapi method=start` |
| status | `method=list` → find by name → container states |
| logs | `SYNO.Docker.Container.Log` per service container, or compose logs fallback |
| health | Same HTTP checks; status from Project API |
| rollback | Workflow git rollback → `build` → `start` |

**Project resolution:**

```bash
synowebapi --exec api=SYNO.Docker.Project version=1 method=list \
  | jq -r '.data[] | select(.name=="ifg") | .id'
```

Cache UUID in `.guardian/ds723-project.json` (Profile artifact), refresh on miss.

**Important:** File changes still land via **git on NAS**. Project `build` tells DSM to reconcile containers with compose on disk — aligns with Repository First.

### 5.6 `DeploymentEngine`

```python
class DeploymentEngine:
    def __init__(self, backend: DeploymentBackend) -> None:
        self._backend = backend

    @classmethod
    def from_profile(cls, profile: ProfileConfig) -> DeploymentEngine:
        backend = create_backend(profile.deployment.backend)
        return cls(backend)

    def deploy(self, ctx: DeployContext) -> DeploymentResult:
        return self._backend.deploy(ctx)
    # ... delegate all operations
```

**Factory** reads Profile YAML:

```yaml
# .guardian/profiles/ifg-production.yaml (conceptual)
deployment:
  backend: synology_project   # or compose
  target:
    host: ds723
    repo: /volume1/docker/ifg_v2/ifg_standalone
  project:
    name: ifg
    id: "<uuid-or-null-auto-resolve>"
    compose_file: docker/docker-compose.prod.yml
    env_file: .env.production
  health:
    url: http://127.0.0.1:8000/health
  services: [api, worker, db]
```

### 5.7 `GuardianWorkflow` (refactored responsibilities)

| Workflow method | Owns | Delegates to Engine |
|-----------------|------|---------------------|
| `deploy()` | git pull, frontend build, rsync dist, alembic decision | `engine.deploy()` |
| `recover()` | diagnose DB/API order | `engine.start()`, `engine.status()` |
| `verify()` | release plan checks | `engine.health()`, `engine.status()` |
| `update()` | rolling/image-only | `engine.restart()` or `engine.deploy()` |

Workflow **never** chooses compose vs synology — Profile config does.

### 5.8 Mapping to existing Guardian v3 modules

| Existing | Future |
|----------|--------|
| `ComposeExecutor` | Internal detail of `ComposeBackend` |
| `deploy_run/pipeline.py` commands | Split: **prepare steps** (workflow) + **runtime steps** (engine) |
| `core/compose.py` parsers | `ComposeBackend` + shared `ServiceStatusParser` |
| `DS723Config` | `DeploymentTarget` + Profile |
| `guardian2 deploy-ksef` | Thin wrapper → `GuardianWorkflow.deploy()` |

Aligns with [GUARDIAN_V3_ARCHITECTURE_REVISED.md](../../GUARDIAN_V3_ARCHITECTURE_REVISED.md): Core provides engine + backends; IFG plugin provides Profile and pre-deploy steps (KSeF checks, frontend).

---

## 6. Integration with Synology Container Manager

### 6.1 Recommended integration pattern

**Hybrid SSH** (Mac mini → DS723+):

1. **Source of truth:** git repo on NAS (unchanged).
2. **Prepare artifacts:** Guardian on Mac mini or NAS (npm build, rsync dist) — unchanged.
3. **Runtime reconcile:** `SynologyProjectBackend.deploy()` calls DSM **`build`** after compose file + images ready.
4. **Verification:** `health()` HTTP + `status()` Project API.
5. **Operator UI:** Container Manager shows **Project ifg** with three services.

**Why not pure WebAPI from Mac mini?** Reduces attack surface; reuses SSH; `synowebapi` runs locally on NAS with correct DSM session context.

### 6.2 One-time Project registration (operator)

Before Backend Stage 2:

1. Apply compose changes (`name: ifg`, external volume pin) — see IFG migration report.
2. Container Manager → **Create Project** → path to compose directory on NAS.
3. Name: **`ifg`**.
4. Record Project UUID in Profile config.
5. Verify `synowebapi method=list` shows `ifg`.

Guardian does **not** auto-create Project in Stage 2 (too risky); optional in Stage 4+ with explicit ADR.

### 6.3 Coexistence with Legacy compose

During migration:

| Environment variable / Profile | Backend |
|------------------------------|---------|
| `deployment.backend=compose` | Legacy (default) |
| `deployment.backend=synology_project` | Target |

**Never** run both backends against the same stack concurrently.

---

## 7. Migration plan (Guardian)

### Etap 1 — Legacy Compose + new backend interface

**Goal:** Introduce abstractions without behavior change.

| Deliverable | Detail |
|-------------|--------|
| `DeploymentBackend` protocol | As §5.3 |
| `ComposeBackend` | Wraps existing compose/SSH code |
| `DeploymentEngine` | Facade |
| `GuardianWorkflow` | Refactor deploy_run to call engine |
| Profile schema v1 | `backend: compose` only |
| Tests | ComposeBackend parity with current guardian2 |

**Production:** Still 100% Legacy compose. **Zero** DSM API calls.

### Etap 2 — Synology Project backend (parallel, opt-in)

**Goal:** Implement `SynologyProjectBackend` behind feature flag.

| Deliverable | Detail |
|-------------|--------|
| `SynologyProjectBackend` | synowebapi start/stop/build/list |
| Project UUID resolver | By name `ifg` |
| Integration test job | DS723+ dry-run: list + status only |
| Profile | `backend: synology_project` on staging or manual `--backend=synology_project` |
| Docs | Runbook + rollback |

**Production default:** still `compose`. IFG Project registered in DSM per §6.2.

### Etap 3 — Automatic backend detection

**Goal:** Guardian selects backend from environment signals.

Detection order:

1. Explicit Profile / CLI flag (`--deployment-backend=`)
2. `.guardian/profiles/<profile>.yaml`
3. Heuristic: if `synowebapi method=list` contains project `ifg` **and** Profile `project.id` set → `synology_project`
4. Fallback → `compose`

Log chosen backend at start of every deploy (`DEPLOYMENT_BACKEND_SELECTED backend=synology_project project=ifg`).

### Etap 4 — Compose → Legacy

**Goal:** Deprecate direct compose in workflows.

| Action | Detail |
|--------|--------|
| Mark `ComposeBackend` `@deprecated` in docs |
| `deploy_run` default → `synology_project` on DS723+ |
| `guardian2.py` | Delegate to GuardianWorkflow + engine |
| Keep ComposeBackend for dev/local/non-Synology hosts |

### Etap 5 — Project as default

**Goal:** Production IFG always uses Project backend.

| Action | Detail |
|--------|--------|
| Profile `ifg-production`: `backend: synology_project` |
| Remove compose-specific strings from IFG plugin pipeline |
| Container Manager is operational source of truth for **runtime** state |
| Compose file remains source of truth for **definition** (Repository First) |

---

## 8. Configuration evolution

### 8.1 Profile file (conceptual)

```yaml
profile: ifg
environment: production
deployment:
  backend: synology_project
  target:
    host: ds723
    repo: /volume1/docker/ifg_v2/ifg_standalone
    ssh_user: admin
  project:
    name: ifg
    id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    compose_file: docker/docker-compose.prod.yml
    env_file: .env.production
  legacy_compose:
    project_name: docker          # only for ComposeBackend rollback
    pinned_volumes:
      postgres_data: docker_postgres_data
  operations:
    deploy:
      build_images: true
      run_migrations: true
      force_recreate: false
    health:
      url: http://127.0.0.1:8000/health
      timeout_seconds: 30
```

### 8.2 Guardian Core vs IFG plugin boundary

| Layer | Owns |
|-------|------|
| **Core** | `DeploymentBackend`, `DeploymentEngine`, SSH executor, status model |
| **IFG plugin** | Profile defaults, KSeF async check, frontend build, alembic step, DS723 paths |
| **Synology adapter** | Optional core submodule or plugin `guardian.backends.synology` |

Per Guardian v3: Synology-specific code should not leak into generic workflow — only into `SynologyProjectBackend`.

---

## 9. Operation semantics (cross-backend contract)

| Operation | Semantics | Success criteria |
|-----------|-----------|------------------|
| **deploy** | Apply latest code + config + recreate if needed | All required services running; health OK |
| **restart** | Stop and start without git pull | Services running |
| **stop** | Graceful stop all project services | Status stopped |
| **start** | Start existing project | Services running |
| **status** | Snapshot | `DeploymentStatus` populated |
| **logs** | Tail logs for services | Non-empty or explicit empty |
| **health** | App-level probe | HTTP 200 + optional DB check |
| **rollback** | Git ref revert + redeploy | Previous ref running; health OK |

Backends may differ in **how**, not **what** success means.

---

## 10. Testing strategy (future implementation)

| Level | ComposeBackend | SynologyProjectBackend |
|-------|----------------|------------------------|
| Unit | Mock SSH transcripts | Mock synowebapi JSON |
| Integration (DS723+) | `compose config`, dry-run ps | `method=list` only |
| E2E | Full deploy to staging | Full deploy after IFG Project migration |
| Parity | Same `DeploymentStatus` shape from both backends |

---

## 11. Analysis: abstract beyond Docker to “Project”?

### 11.1 Question

Should Guardian operate only on **`DeploymentProject`**, never on “container” or “compose”, to support Kubernetes, Portainer, Docker Swarm, Nomad later?

### 11.2 Recommendation: **Yes — with a thin backend protocol**

**Adopt domain language:**

| Avoid in Workflow | Prefer |
|-------------------|--------|
| container, pod, compose service | **service** (logical role: api, worker, db) |
| docker compose up | **deploy()** |
| synowebapi start | **start()** |

**Do not** pretend all platforms are identical internally. Use:

```
DeploymentProject (name, services[], ref)
DeploymentBackend (platform-specific)
```

### 11.3 Future backends (illustrative)

| Backend | `deploy()` maps to |
|---------|-------------------|
| `compose` | docker compose (Legacy) |
| `synology_project` | SYNO.Docker.Project |
| `kubernetes` | helm upgrade / kubectl rollout |
| `portainer` | Portainer Stack API |
| `docker_swarm` | stack deploy |
| `nomad` | job run |

Workflow stays stable; Profile selects backend.

### 11.4 What not to abstract

| Concern | Reason |
|---------|--------|
| Image build on NAS vs CI | Stays in **prepare** phase; platform-specific |
| Volume pinning / PVC | Backend-specific config (IFG postgres external volume) |
| Log format | Backend normalizes to text blob in `DeploymentResult` |
| Zero-downtime deploy | Not all backends support — expose capability flag `supports_rolling: bool` |

### 11.5 Verdict

**Full Docker abstraction is desirable and low-cost** if done at the **DeploymentBackend** boundary already planned. Synology Project is the first non-raw-compose backend; it validates the model because DSM itself is compose-backed — migration risk is moderate, learning value is high.

Kubernetes etc. remain **future backends**, not workflow forks.

---

## 12. Risks & open questions

| ID | Risk / question | Mitigation / next step |
|----|-----------------|------------------------|
| R1 | DSM API undocumented | Pin DSM version; capture HAR on DS723+ for `build` payload |
| R2 | Project UUID churn | Resolve by name; cache with validation |
| R3 | Dual backend race | Enforce mutex in Profile; document "one backend" |
| R4 | Guardian v3 "Core doesn't know Synology" | Synology adapter as optional package, not core import from IFG |
| R5 | IFG volume migration | Complete [IFG_CONTAINER_MANAGER_MIGRATION.md](../../reports/IFG_CONTAINER_MANAGER_MIGRATION.md) before Stage 2 |
| Q1 | Does `build` run compose build on NAS? | Empirical test on DS723+; document in backend README |
| Q2 | Alembic via compose exec vs api container | Stays in Workflow prepare phase, not backend |
| Q3 | cloudflared outside project | Separate Profile entry or future compose service |

---

## 13. Recommended next work orders

| GWO | Title | Depends on |
|-----|-------|------------|
| GWO-IFG-002 | IFG Profile + compose `name: ifg` + volume pin | IFG migration report |
| GWO-G-003 | DeploymentBackend + ComposeBackend refactor (Etap 1) | This document |
| GWO-G-004 | SynologyProjectBackend spike on DS723+ (Etap 2) | GWO-IFG-002, DSM Project registered |
| GWO-G-005 | Backend auto-detection (Etap 3) | GWO-G-004 |

---

## 14. References

- [IFG Container Manager migration (DS723+)](../../reports/IFG_CONTAINER_MANAGER_MIGRATION.md)
- [Guardian v3 architecture (revised)](../../GUARDIAN_V3_ARCHITECTURE_REVISED.md)
- Synology developer guide: [Docker Project worker](https://help.synology.com/developer-guide/resource_acquisition/docker-project.html)
- Community: [synowebapi Container Manager projects](http://blog.differentpla.net/blog/2025/07/12/synowebapi-container-manager-projects/)
- Synology API catalog: `SYNO.Docker.Project` (community docs / synology-api)

---

## 15. Abstraction level — `DeploymentBackend` vs `ExecutionBackend` vs `RuntimeBackend`

### 15.1 Context

Sections 1–14 introduced **`DeploymentBackend`** and **`DeploymentEngine`** because the immediate driver was IFG production deploy on DS723+. v1.0 generalizes Guardian to a **universal operation executor** (deploy, backup, audit, repair, …). The backend name must reflect that scope without breaking the original design.

### 15.2 Comparison

| Criterion | `DeploymentBackend` | `ExecutionBackend` | `RuntimeBackend` |
|-----------|---------------------|--------------------|--------------------|
| **Scope** | Deploy, rollback, lifecycle | Any **Operation** Guardian can invoke | Where workloads **run** (container/OS) |
| **Matches Operation Engine** | Partial — sounds deploy-only | **Strong** — executes requested operations | Weak — implies infra layer, not control plane |
| **Matches Workflow role** | Workflow “deploys” | Workflow **requests operations** | Workflow does not manage runtime directly |
| **Future ops** (backup, audit, inventory) | Awkward naming | **Natural** | Misleading (backup ≠ runtime) |
| **Risk of confusion** | Low | Low | **High** — collides with “container runtime”, Kubernetes runtime class, Node runtime |
| **Industry usage** | CI/CD deploy tools | Job runners, workflow engines (Temporal, Step Functions) | containerd, CRI-O, WASM runtime |
| **Aligns with v3 Core** | Yes (current doc) | **Yes** — executor pattern already in workflow engine | No — wrong layer |

### 15.3 Decision (v1.0)

**Adopt `ExecutionBackend` as the canonical name** for the platform adapter layer.

**Retain `DeploymentBackend` as a deprecated alias** through Guardian v4 for backward compatibility with §5.3 interfaces and migration Etap 1–2 deliverables.

**Reject `RuntimeBackend`** for the adapter layer — “runtime” in Guardian vocabulary refers to **infrastructure under management** (DS723+, Container Manager, cluster), not the Guardian component that invokes APIs.

### 15.4 Terminology mapping

| v0.1 (§1–14) | v1.0 (§15–23) | Notes |
|--------------|---------------|-------|
| `DeploymentEngine` | **`OperationEngine`** | Engine routes **Operations**; deploy is one operation |
| `DeploymentBackend` | **`ExecutionBackend`** | Implements operations against infrastructure |
| `DeploymentProjectRef` | **`RuntimeProjectRef`** | Logical project on a **runtime** (ifg @ DS723+) |
| `DeploymentStatus` | **`OperationResult` / `RuntimeStatus`** | Normalized outcome |
| `GuardianWorkflow.deploy()` | **`Workflow.run(Operation.Deploy)`** | Workflow selects operation |

### 15.5 Migration path (naming only)

| Phase | Action |
|-------|--------|
| Guardian v3 (Etap 1–2) | Implement `DeploymentBackend` protocol; add type alias `ExecutionBackend = DeploymentBackend` |
| Guardian v4 | Primary docs + APIs use `ExecutionBackend`; `DeploymentEngine` wraps `OperationEngine.deploy()` |
| Guardian v5 | Remove `DeploymentBackend` alias; single `ExecutionBackend` + `OperationEngine` |

**Philosophy unchanged:** Workflow never imports `docker compose` or `synowebapi`. Only the **name** of the adapter layer widens from “deployment” to “execution”.

---

## 16. Capability Model

### 16.1 Purpose

Workflows must not **guess** what a backend can do (e.g. call `rolling_update` on Compose Legacy). Each **`ExecutionBackend`** declares a **`CapabilitySet`** at registration time. The **Capability Engine** (§20) validates operations before dispatch.

Capabilities are **declarative**, **testable**, and **versioned** with the backend.

### 16.2 Capability catalog

| Capability | Meaning | Used by operations | Compose Legacy | Synology Project | K8s (future) |
|------------|---------|------------------|----------------|------------------|--------------|
| **`supports_project`** | Backend manages a named **project/stack** as one unit | Deploy, Start, Stop, Status | ✓ (compose project) | ✓ (DSM Project) | ✓ (namespace/release) |
| **`supports_build`** | Can build images or reconcile build from spec | Deploy, Update | ✓ | ✓ (via build API) | ✓ |
| **`supports_restart`** | Restart services without full redeploy | Restart | ✓ | ✓ (stop+start) | ✓ |
| **`supports_logs`** | Fetch log tail for services | Logs, Audit, Repair | ✓ | ✓ | ✓ |
| **`supports_stream`** | Streaming logs or deploy progress | Deploy (UI), Logs follow | partial | ✓ (start_stream) | ✓ |
| **`supports_snapshot`** | Point-in-time snapshot of project/state | Snapshot | ✗ | partial | ✓ |
| **`supports_backup`** | Coordinated backup (DB + volumes) | Backup | partial (exec pg_dump) | partial | ✓ |
| **`supports_restore`** | Restore from backup/snapshot | Restore, Rollback | partial | partial | ✓ |
| **`supports_health`** | App-level health probe integration | Health, Verify | ✓ (HTTP) | ✓ | ✓ |
| **`supports_shell`** | Interactive or scripted shell on target | Repair (manual) | ✓ (ssh) | ✓ (ssh) | ✓ (kubectl exec) |
| **`supports_exec`** | One-shot command in service context | Repair, Audit, Migrations prep | ✓ (compose exec) | ✓ | ✓ |
| **`supports_scaling`** | Change replica count / scale service | Update (future) | ✗ | ✗ | ✓ |
| **`supports_rolling_update`** | Zero-downtime rolling deploy | Update, Deploy | ✗ | ✗ | ✓ |

### 16.3 Capability declaration (conceptual)

```yaml
# Profile or backend manifest
backend: synology_project
capabilities:
  supports_project: true
  supports_build: true
  supports_restart: true
  supports_logs: true
  supports_stream: true
  supports_snapshot: false
  supports_backup: false
  supports_restore: false
  supports_health: true
  supports_shell: true
  supports_exec: true
  supports_scaling: false
  supports_rolling_update: false
version: "1.0"
```

### 16.4 Capability Engine behavior

1. **Workflow** requests `Operation.Backup`.
2. **Operation Engine** asks Capability Engine: `can_execute(backend, Operation.Backup)`?
3. If **`supports_backup`** is false → fail fast with structured error (`CapabilityMissing`) and suggested alternatives (e.g. manual runbook, different backend).
4. If true → dispatch to `ExecutionBackend.execute(Operation.Backup, ctx)`.

Workflows may also declare **required capabilities** in Profile:

```yaml
operations:
  deploy:
    requires: [supports_project, supports_build, supports_health]
```

### 16.5 Relationship to §11.4 (“what not to abstract”)

Capabilities encode exactly what §11.4 left implicit: zero-downtime deploy, snapshot, scaling — **not** assumed universal; **explicitly** declared per backend.

---

## 17. Discovery Engine

### 17.1 Purpose

Guardian runs on **Mac mini** (control plane) against **unknown or evolving targets** (DS723+, local dev, future cloud). **Discovery Engine** builds a **`RuntimeContext`** before any operation — so Workflow does not hardcode backend selection when the environment can be inferred.

Discovery complements Profile (explicit config) — it does not replace Repository First or Canon.

### 17.2 Discovery pipeline

```
Guardian CLI / Workflow start
        │
        ▼
┌───────────────────┐
│ Discovery Engine  │
└─────────┬─────────┘
          │
    ┌─────┴─────┬─────────────┬──────────────┐
    ▼           ▼             ▼              ▼
 HostProbe   PlatformProbe  ProjectProbe  ProfileLoad
 (SSH?)      (Synology?)    (ifg exists?)  (.guardian/)
    │           │             │              │
    └─────┬─────┴─────────────┴──────────────┘
          ▼
   RuntimeContext
   - host: ds723
   - platform: synology_dsm
   - container_manager: true
   - project: { name: ifg, id: uuid }
   - suggested_backend: synology_project
   - confidence: high | medium | low
          │
          ▼
   Backend selection (§17.4)
```

### 17.3 Probes (examples)

| Probe | Method | Yields |
|-------|--------|--------|
| **HostProbe** | SSH connect, `uname`, hostname | `host_id`, reachable |
| **PlatformProbe** | `synowebapi --exec api=SYNO.DSM.Info` or `/etc/synoinfo.conf` | `platform=synology`, DSM version |
| **ContainerManagerProbe** | `synowebapi api=SYNO.Docker.Project method=list` | `container_manager=true`, project list |
| **ProjectProbe** | Match Profile `project.name` against list | `project.id`, state |
| **ComposeProbe** | `docker compose version`, compose file exists | `compose_available`, project name from config |
| **ProfileLoad** | Read `.guardian/profiles/*.yaml` | explicit overrides |

### 17.4 Backend selection rules

Priority (highest wins):

1. **CLI flag** `--backend=compose|synology_project|auto`
2. **Profile** `execution.backend` (explicit)
3. **Discovery suggestion** if `confidence >= medium` and Profile `discovery.allow_auto: true`
4. **Fallback** `compose` (Legacy) with warning event `BackendSelected` (reason=fallback)

Workflow **never** embeds `if synology: … else: …`. It passes `RuntimeContext` to Operation Engine.

### 17.5 IFG / DS723+ example

```
Discovery
    ↓
wykryto host: ds723 (SSH OK)
    ↓
wykryto Synology DSM 7.x
    ↓
wykryto Container Manager (SYNO.Docker.Project list OK)
    ↓
wykryto Project "ifg" (UUID …)
    ↓
wybrano Backend: synology_project (confidence: high)
    ↓
emit: BackendSelected { backend, project, source: discovery }
```

If Project **not** registered yet → `confidence: low`, suggest `compose` or abort with runbook link to [IFG_CONTAINER_MANAGER_MIGRATION.md](../../reports/IFG_CONTAINER_MANAGER_MIGRATION.md).

### 17.6 Caching

Discovery results cached in `.guardian/runtime-context.json` with TTL (e.g. 1h) and invalidated on deploy failure or `HealthChanged` event.

---

## 18. Event Bus

### 18.1 Purpose

Decouple **observers** (logging, reporting, UI, future dashboard, Self Improving Platform) from **operation execution**. Synchronous SSH/compose remains in ExecutionBackend; events carry **facts** for audit and automation.

**Not implemented in v1.0 doc** — architecture only.

### 18.2 Event categories

| Category | Events | Consumers |
|----------|--------|-----------|
| **Deployment** (legacy naming) | `DeploymentStarted`, `DeploymentFinished`, `DeploymentFailed` | Reports, `.guardian/history/`, notifications |
| **Operation** (v1.0) | `OperationStarted`, `OperationFinished`, `OperationFailed` | Same + metrics |
| **Health** | `HealthChanged` | Doctor, auto-recover workflow, DSM alerts |
| **Discovery** | `BackendSelected`, `DiscoveryCompleted`, `DiscoveryFailed` | Logs, Profile suggestions |
| **Verification** | `VerificationStarted`, `VerificationFinished` | Release plan, CI gates |
| **Data protection** | `BackupCreated`, `SnapshotCreated` | Runbooks, retention |
| **Rollback** | `RollbackStarted`, `RollbackFinished` | Audit trail |

### 18.3 Event envelope (conceptual)

```json
{
  "event": "OperationFinished",
  "timestamp": "2026-07-05T20:00:00Z",
  "correlation_id": "guardian-run-uuid",
  "operation": "Deploy",
  "backend": "synology_project",
  "profile": "ifg-production",
  "target": { "host": "ds723", "project": "ifg" },
  "ok": true,
  "duration_ms": 142000,
  "artifacts": { "report_path": ".guardian/reports/deploy-….json" }
}
```

### 18.4 Use cases

| Use case | Events |
|----------|--------|
| **Markdown deploy report** | Subscribe to `OperationFinished` → write `docs/reports/guardian_deploy_*.md` |
| **Doctor aggregation** | `HealthChanged` + last `OperationFailed` |
| **Guardian history** | All `Operation*` → append-only JSONL in `.guardian/events/` |
| **Future ops dashboard** | Stream `OperationStarted` / progress via `supports_stream` |
| **Rollback audit** | `RollbackStarted` → `RollbackFinished` chain |
| **Backend analytics** | Count `BackendSelected` by source (discovery vs profile) |

### 18.5 Bus implementation options (future)

| Option | Pros | Cons |
|--------|------|------|
| In-process pub/sub | Simple, v3 compatible | Single process only |
| JSONL append log | Repository First, grep-friendly | No real-time |
| Plugin hooks | Matches Guardian plugin model | Manual subscribe |

**Recommendation:** Start with **synchronous dispatch + JSONL append** (Repository First); evolve to async bus in v5 if dashboard required.

---

## 19. Guardian Operation Engine

### 19.1 Central thesis

**Deployment is one Operation.** Guardian v1.0 executes **Operations** against **ExecutionBackends**, selected by Discovery and constrained by Capabilities.

```
Workflow  →  chooses Operation (Deploy, Backup, Verify, …)
Operation Engine  →  validates capability, selects backend, executes
ExecutionBackend  →  platform-specific steps
```

§5 **`DeploymentEngine`** becomes the **deploy specialization** of Operation Engine (facade for backward compatibility):

```python
# Conceptual
class OperationEngine:
    def execute(self, operation: Operation, ctx: OperationContext) -> OperationResult: ...

class DeploymentEngine:  # legacy facade
    def deploy(self, ctx): return self._ops.execute(Operation.Deploy, ctx)
```

### 19.2 Operation catalog

| Operation | Description | Typical Workflow | Primary capabilities |
|-----------|-------------|------------------|----------------------|
| **Deploy** | Apply latest code, build, migrate, start | `deploy run`, `guardian2 deploy-ksef` | project, build, health |
| **Update** | Refresh running stack (image/config) without full git narrative | Rolling refresh | build, restart, rolling_update? |
| **Restart** | Cycle services | recover-prod | restart, project |
| **Start** | Start stopped project | recover-prod | project |
| **Stop** | Graceful stop | maintenance | project |
| **Backup** | Coordinated DB/volume backup | scheduled task | backup, exec |
| **Restore** | Restore from backup | disaster recovery | restore |
| **Verify** | Post-deploy checks, release plan | doctor, deploy verify | health, logs |
| **Health** | Liveness/readiness probe | doctor, monitor | health |
| **Snapshot** | Point-in-time state | pre-migration | snapshot |
| **Cleanup** | Remove orphans, old images, stale jobs | housekeeping | exec, project |
| **Inventory** | List services, images, volumes, versions | doctor, audit | project, logs |
| **Audit** | Collect evidence (logs, configs, SQL counts) | incident, KSeF sync report | logs, exec, health |
| **Repair** | Guided fix (start db before api, etc.) | recover-prod | start, exec, health |
| **Rollback** | Revert git + reconcile runtime | failed deploy | restore, build, project |

### 19.3 Operation vs Workflow vs Backend

| Layer | Responsibility | Knows backend? | Knows docker? |
|-------|----------------|----------------|---------------|
| **Guardian CLI** | Parse args, load Profile | No | No |
| **Workflow** (plugin) | Orchestrate **business steps** (git, npm, KSeF check) + pick **Operation** | No | No |
| **Operation Engine** | Capability check, dispatch, events | **Selects** via Discovery/Profile | No |
| **ExecutionBackend** | Implement operation | Yes (self) | Only internally |

### 19.4 Deploy operation decomposition (IFG example)

**Workflow** (`ifg deploy run`) still owns **prepare** steps:

1. git pull  
2. frontend build / rsync  
3. alembic decision  
4. KSeF async check (plugin)

**Operation Engine** executes **`Operation.Deploy`** on backend:

1. build images (if `supports_build`)  
2. reconcile project (compose up / synowebapi build)  
3. verify health  

Same split as §5.7 — now generalized to all operations.

### 19.5 Mapping from §9 operation semantics

§9 cross-backend contract remains valid. Each row becomes an **`Operation`** enum value with shared **`OperationResult`** success criteria. §9 is the **normative contract**; §19 is the **taxonomy**.

---

## 20. Guardian Execution Architecture vNext

### 20.1 Layer diagram

```
                    Guardian CLI
                         │
                         ▼
              ┌─────────────────────┐
              │  Workflow Layer      │  ← plugins: ifg, psag (Canon, KSeF, npm)
              │  selects Operation   │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Operation Engine    │  ← Deploy, Backup, Verify, …
              │  dispatch + events   │
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Discovery  │  │ Capability  │  │  Event Bus  │
│  Engine     │  │  Engine     │  │  (observers)│
└──────┬──────┘  └──────┬──────┘  └─────────────┘
       │                │
       └────────┬───────┘
                ▼
              ┌─────────────────────┐
              │  Execution Backend   │  ← ComposeBackend, SynologyProjectBackend, …
              │  (adapter)           │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Runtime             │  ← logical project: ifg (api, worker, db)
              │  (managed state)     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Infrastructure      │  ← DS723+, Container Manager, Docker, network, volumes
              └─────────────────────┘
```

### 20.2 Layer roles

| Layer | Role | Does not |
|-------|------|----------|
| **Guardian CLI** | Entry point, format output, global flags | Execute SSH |
| **Workflow** | Plugin orchestration, prepare steps, pick Operation | Choose docker vs synology |
| **Operation Engine** | Route operations, enforce capabilities, emit events | Parse compose files |
| **Discovery Engine** | Build `RuntimeContext`, suggest backend | Mutate infrastructure |
| **Capability Engine** | Validate operation ⊆ backend capabilities | Run probes on every log line |
| **Event Bus** | Fan-out lifecycle events | Block operation path |
| **Execution Backend** | Platform-specific execution | Know KSeF or invoice rules |
| **Runtime** | Logical project + services (api, worker, db) | Physical host |
| **Infrastructure** | NAS, DSM, containers, volumes, SSH | Business logic |

### 20.3 Relation to §5.1 layering

§5.1 remains accurate for **deploy path**. vNext **inserts** Discovery, Capability, Event Bus **around** Operation Engine (superset of DeploymentEngine). **`ComposeBackend`** and **`SynologyProjectBackend`** unchanged in role — they implement **`ExecutionBackend`** interface expanded from §5.3.

---

## 21. Roadmap — Guardian v3, v4, v5

### 21.1 Guardian v3 — Foundation (current trajectory)

| Area | Status |
|------|--------|
| **Stays** | Plugin model, Doctor, deploy_run pipeline, SSH executor, ComposeExecutor, guardian2, IFG Profile concept |
| **Adds** | `DeploymentBackend` protocol (= ExecutionBackend alias), `ComposeBackend` wrapper, `OperationEngine` skeleton with Deploy-only |
| **Adds** | Capability model (read-only declarations), Discovery probes (manual `--discover`) |
| **Adds** | Event JSONL for `OperationStarted` / `OperationFinished` |
| **Deprecated** | Nothing yet — direct compose strings in pipeline marked `@legacy` in docs |

Maps to §7 Etap 1–2.

### 21.2 Guardian v4 — Synology Project + Operations

| Area | Status |
|------|--------|
| **Stays** | v3 core, IFG plugin, Repository First reports |
| **Adds** | `SynologyProjectBackend`, auto Discovery default on DS723+ |
| **Adds** | Operations: Deploy, Start, Stop, Restart, Health, Verify, Logs, Rollback, Repair, Inventory |
| **Adds** | Capability enforcement (fail-fast) |
| **Deprecated** | `DeploymentEngine` as primary API → use `OperationEngine`; `DeploymentBackend` alias; direct `guardian2` compose strings |
| **Deprecated** | Manual `-p docker` compose project on DS723+ (after IFG migration) |

Maps to §7 Etap 3–5.

### 21.3 Guardian v5 — Universal execution platform

| Area | Status |
|------|--------|
| **Stays** | Operation Engine, ExecutionBackend, Capability, Discovery, Event Bus, Profile |
| **Adds** | Operations: Backup, Restore, Snapshot, Cleanup, Audit (full) |
| **Adds** | Optional backends: kubernetes, portainer (ADR each) |
| **Adds** | Ops dashboard / metrics from event stream |
| **Deprecated** | `ComposeBackend` on production paths (dev/local only); `DeploymentBackend` name removed |
| **Removed** | `guardian2.py` monolith — fully delegated to CLI + workflows |

### 21.4 IFG-specific milestones (cross-cutting)

| Milestone | Guardian version | IFG action |
|-----------|------------------|----------|
| Compose `name: ifg` + volume pin | v3 | [IFG_CONTAINER_MANAGER_MIGRATION.md](../../reports/IFG_CONTAINER_MANAGER_MIGRATION.md) |
| DSM Project registered | v3 | One-time operator |
| Default backend synology_project | v4 | Profile update |
| Deploy via Operation Engine only | v4 | guardian2 → `ifg deploy run` |

---

## 22. Architecture Decision Records

### ADR-001 — Workflow nie zna backendu

**Status:** Accepted  
**Context:** §5.7, §19.3 — duplicate logic if every Workflow branches on compose vs DSM.  
**Decision:** Workflow wybiera **Operation** i **Profile**; backend wybiera Operation Engine po Discovery/Profile.  
**Consequences:** (+) Testowalne workflow bez mock SSH compose. (+) Jeden plugin IFG na dev i prod. (−) Indirection — debug via `BackendSelected` event.

### ADR-002 — Operation jest ważniejsze niż Deploy

**Status:** Accepted  
**Context:** Guardian ma obsługiwać recover, backup, audit — nie tylko deploy (§19).  
**Decision:** **`Operation`** jest pierwszą klasą; Deploy to jedna wartość enum; `DeploymentEngine` to cienki facade.  
**Consequences:** (+) Jednolity model dla `recover-prod` i `deploy run`. (+) Roadmap v5 naturalna. (−) Migracja nazw z v0.1 dokumentacji.

### ADR-003 — Capability jest osobną warstwą

**Status:** Accepted  
**Context:** §11.4 — nie wszystkie backendy wspierają rolling update, snapshot, backup.  
**Decision:** **Capability Engine** osobno od ExecutionBackend; deklaracja zdolności przed wykonaniem.  
**Consequences:** (+) Fail-fast z jasnym komunikatem. (+) Profile `requires:`. (−) Każdy nowy backend musi wypełnić capability matrix.

### ADR-004 — Discovery wybiera backend

**Status:** Accepted  
**Context:** §7 Etap 3, §17 — operator nie powinien pamiętać `-p ifg` vs synowebapi.  
**Decision:** Discovery Engine proponuje backend; Profile może nadpisać; Workflow nie wybiera.  
**Consequences:** (+) Mniej błędów prod (pusty wolumen). (+) `RuntimeContext` cache. (−) Discovery może zawieść — wymaga fallback i explicit override.

---

## 23. Document status & summary

### 23.1 Approval

| Field | Value |
|-------|-------|
| **Status** | **Approved** |
| **Version** | **1.0** |
| **Supersedes** | Version 0.1 (sections 1–14 unchanged in substance, extended by 15–23) |
| **Implementation** | Out of scope until GWO-G-003+ |

### 23.2 Co zyskuje Guardian po tej architekturze?

1. **Uniwersalny silnik operacji** — deploy, recover, backup, audit i inventory to ten sam mechanizm (`Operation` + `ExecutionBackend`), nie osobne skrypty.
2. **Bezpieczniejsza produkcja IFG** — Discovery + Capability zapobiegają uruchomieniu compose z niewłaściwym projektem/wolumenem; Synology Project staje się first-class bez hardcode w workflow.
3. **Testowalność** — Workflow testuje się z mock Operation Engine; backend testuje się z mock SSH/DSM; capabilities są kontraktem.
4. **Obserwowalność** — Event Bus + JSONL daje historię operacji zgodną z Repository First i Self Improving Platform (Canon).
5. **Przyszłe backendy bez rewrite workflow** — Kubernetes, Portainer, Swarm to nowe `ExecutionBackend`, nie nowe `guardian3`.
6. **Zachowana filozofia v0.1** — Workflow nadal nie woła `docker compose`; Profile + Discovery + Capability decydują; compose file pozostaje definicją infrastruktury w git.

---

## 24. Implementation status

**Last updated:** 2026-07-05 (GWO-G-003 Etap 1)

| Component | Package path | Status | Notes |
|-----------|--------------|--------|-------|
| **ExecutionBackend** | `ifg_guardian.core.execution.backend` | **Implemented** | Protocol; `DeploymentBackend` alias |
| **ComposeBackend** | `ifg_guardian.core.execution.compose_backend` | **Implemented** | Wraps `ComposeExecutor`; deploy + logs |
| **OperationEngine** | `ifg_guardian.core.execution.operation_engine` | **Partial** | `Operation.Deploy` only; other ops TODO |
| **DeploymentEngine** | `ifg_guardian.core.execution.deployment_engine` | **Partial** | `deploy()` facade → OperationEngine |
| **Discovery** | `ifg_guardian.core.execution.discovery` | **Planned** | Stub + `RuntimeContext` model |
| **Capability** | `ifg_guardian.core.execution.capability` | **Planned** | Stub + `CapabilitySet` model |
| **EventBus** | `ifg_guardian.core.execution.event_bus` | **Planned** | Stub only |
| **SynologyProjectBackend** | `ifg_guardian.core.execution.synology_project_backend` | **Planned** | Etap 2 |
| **PreflightEngine** | `ifg_guardian.core.preflight.engine` | **Implemented** | Read-only checks (GWO-G-003A) |
| **SafetyGate** | `ifg_guardian.core.preflight.gate` | **Implemented** | GO / NO_GO decision |
| **DeploymentDecision** | `ifg_guardian.core.preflight.models` | **Implemented** | Preflight outcome model |

**Etap 1 wiring:** `IntentExecutor` routes `COMPOSE_UP` through `DeploymentEngine.deploy()` → `OperationEngine` → `ComposeBackend`. `COMPOSE_LOGS` through `ComposeBackend.logs()`. No behavior change; production still 100% Legacy compose.

**Preflight wiring (GWO-G-003A):** `ifg.deploy.run` workflow inserts `PreflightStage` before `SimulateExecutionStage`. Read-only checks → `SafetyGate` → blocks on NO_GO.

**Tests (2026-07-06):** 110 `ifg_guardian` unit tests + 301 `guardian_platform` tests — all passed.

---

## 26. Preflight Engine & Safety Gate (operational safety)

> **Scope note:** This section extends v1.0 with operational safety — **not** a new architecture version. Execution Backend, Operation Engine, and Capability/Discovery stubs remain unchanged.

### 26.1 Philosophy

Guardian must be **more cautious than the operator**. Preflight runs **read-only** verification before mutating operations. If any critical check fails, **Safety Gate** returns **NO_GO** and the workflow halts before Operation Engine dispatch.

### 26.2 Layer placement

```
Guardian CLI / Workflow
        │
        ▼
Preflight Engine          ← read-only checks
        │
        ▼
Safety Gate               ← GO / NO_GO
        │
        ▼
Operation Engine        ← unchanged (§19)
        │
        ▼
Execution Backend       ← unchanged (§15–16)
        │
        ▼
Runtime / Health / Report
```

### 26.3 Preflight Engine

| Property | Value |
|----------|-------|
| Package | `ifg_guardian.core.preflight` |
| Mutations | **None** — no deploy, compose up, restart |
| Output | `PreflightReport` |
| Report artifact | `PRECHECK_REPORT_YYYY_MM_DD.md` |

Each check returns `PreflightCheckResult`:

| Field | Description |
|-------|-------------|
| `check_id` | Stable identifier |
| `label` | Human label |
| `status` | `PASS` \| `WARN` \| `FAIL` \| `UNKNOWN` (see §28) |
| `description` | Outcome summary |
| `duration_ms` | Execution time |
| `details` | Structured debug |

**Check catalog (v1):** repo accessible, branch, git clean, compose file, `.env`, SSH, Docker, Compose, compose config valid, compose config validation (volume pin), PostgreSQL volume, external volume, backup exists/freshness, health (warning if down), disk space, permissions.

### 26.4 Safety Gate

```python
class SafetyGate:
    def evaluate(self, report: PreflightReport) -> DeploymentDecision: ...
```

| `DeploymentDecision.status` | Meaning |
|----------------------------|---------|
| **GO** | No FAIL checks; warnings allowed |
| **NO_GO** | At least one FAIL — operation blocked |

| Field | Content |
|-------|---------|
| `blocking_items` | FAIL check descriptions |
| `warnings` | WARN check descriptions |
| `recommendations` | Operator guidance |

### 26.5 Deploy workflow integration

`ifg.deploy.run` stage order:

1. Init → Dependency → Release Plan → Blocker → Build Pipeline  
2. **Preflight** (new)  
3. Simulate Execution (Operation Engine path)  
4. Summary  

On **NO_GO**: `SimulateExecutionStage` is not reached; `PRECHECK_REPORT.md` written.

**Not implemented (separate GWO):** auto repair, auto backup, auto rollback.

> **Status semantics:** Canonical definitions in §28. Implementation may still emit legacy `WARNING` until GWO-G-003B code alignment.

---

## 28. Status Semantics

> **Scope note:** Reporting and decision model refinement — **not** an architecture version change. Layers (Operation Engine, Execution Backend, …) unchanged; **how results are labeled and interpreted** is unified here.

### 28.1 Problem statement

Guardian reports mixed `PASS`, `FAIL`, and `WARN` for situations that mean different things operationally:

| Misleading report (GWO-IFG-002A) | Problem |
|----------------------------------|---------|
| Stack stopped → check marked **PASS** | Stack down is not a positive outcome |
| Health unreachable → **FAIL** | May be **UNKNOWN** when stack is intentionally stopped |
| Production Proven **0/11 FAIL** | Steps after Safety Gate **NO_GO** were **not executed** — should be **SKIPPED**, not FAIL |

Without unified semantics, operators misread **NOT PRODUCTION PROVEN** as catastrophic failure instead of **procedure blocked early**.

### 28.2 Canonical check statuses

Used by **Doctor**, **Preflight**, **Validation**, and **Operation** results unless a component defines a stricter subset.

| Status | Meaning | Operation executed? |
|--------|---------|---------------------|
| **PASS** | Check completed; result positive | Yes |
| **WARN** | Check completed; warnings present; may continue | Yes |
| **FAIL** | Check completed; result negative | Yes |
| **BLOCKED** | Check **not** executed — blocked by Safety Gate, Policy, Capability, or conscious decision | **No** |
| **SKIPPED** | Check **not** executed — earlier stage halted workflow | **No** (not an error) |
| **UNKNOWN** | Cannot determine result (stack off, host down, timeout, probe impossible) | Attempted or N/A |

**Rules:**

- **PASS ≠ GO** — a check can PASS while Safety Gate returns NO_GO (other checks FAIL).
- **FAIL ≠ BLOCKED** — FAIL means we measured and failed; BLOCKED means we never ran.
- **UNKNOWN ≠ FAIL** — absence of measurement is not negative proof.

Legacy alias: `WARNING` → **WARN** (deprecated in docs; code migration in GWO-G-003B follow-up).

### 28.3 Component responsibilities

| Component | Question it answers | Decision authority? |
|-----------|---------------------|---------------------|
| **Doctor** | Is the environment **healthy**? | **No** deploy decision |
| **Preflight** | **May** we execute the operation? (read-only probes) | **No** — feeds Safety Gate |
| **Safety Gate** | **GO** or **NO_GO**? | **Yes** — blocks Operation Engine |
| **Workflow** | Did the orchestration **complete**? | Reports lifecycle only |
| **Operation Engine** | Did the **operation** succeed? | Dispatches to backend |
| **Execution Backend** | Did the **platform step** succeed? | Implements operation |
| **Validation** | Did post-conditions hold? | Reports only |
| **DeploymentDecision** | **GO** / **NO_GO** only | Never PASS/FAIL |

### 28.4 Allowed statuses per component

| Component | Check / step level | Aggregate / lifecycle level |
|-----------|-------------------|----------------------------|
| **Doctor** | `PASS`, `WARN`, `FAIL`, `UNKNOWN` | Overall: `READY`, `READY_WITH_WARNINGS`, `BLOCKED`, `UNKNOWN` (health verdict — not GO/NO_GO) |
| **Preflight** | `PASS`, `WARN`, `FAIL`, `UNKNOWN` | Report summary counts; feeds Safety Gate |
| **Safety Gate** | — (no check statuses) | **`GO`**, **`NO_GO`** only |
| **Workflow** | Stage: `PASS`, `WARN`, `FAIL`, `SKIPPED`, `BLOCKED` | **`Completed`**, **`Failed`**, **`Blocked`**, **`Cancelled`** |
| **Operation Engine** | Per operation: `PASS`, `FAIL`, `UNKNOWN` | `OperationResult.ok` maps to PASS/FAIL |
| **Execution Backend** | Same as operation step | Backend-specific `details` only |
| **Validation** | `PASS`, `FAIL`, `SKIPPED`, `BLOCKED`, `UNKNOWN` | Production Proven checklist |
| **DeploymentDecision** | — | **`GO`**, **`NO_GO`** only |
| **Production reports (GWO)** | `PASS`, `FAIL`, `SKIPPED`, `BLOCKED`, `UNKNOWN` | **No** PASS/FAIL ratio scoring |

### 28.5 Separating technical status from operational decision

Reports MUST distinguish:

1. **Technical status** — outcome of a probe or step (`UNKNOWN` for health when stack is down).
2. **Operational decision** — what Guardian decided (`BLOCKED` when Safety Gate NO_GO).

**Example (corrected GWO-IFG-002A semantics):**

| Check | Technical status | Operational decision | Notes |
|-------|------------------|----------------------|-------|
| Stack stopped (containers Exited) | **UNKNOWN** or contextual **PASS** for “safe migration window” | — | Use explicit label *migration window* in Validation, not generic PASS |
| Health endpoint | **UNKNOWN** | — | Stack intentionally stopped |
| Backup missing (LIVE) | **FAIL** | **NO_GO** | Preflight FAIL → Safety Gate |
| Etap 3 API health (after NO_GO) | **SKIPPED** | **BLOCKED** | Not executed — not FAIL |
| Production Proven item “API responds” | **SKIPPED** | — | Procedure stopped at Etap 1 |

### 28.6 Production Proven checklist

Checklist items use **`PASS` | `FAIL` | `SKIPPED` | `BLOCKED` | `UNKNOWN`** — never a raw score like “0/11 FAIL”.

| Status | When to use |
|--------|-------------|
| **PASS** | Criterion **executed and met** |
| **FAIL** | Criterion **executed and not met** |
| **SKIPPED** | Criterion **not executed** — earlier halt (e.g. NO_GO) |
| **BLOCKED** | Criterion **deliberately not run** — policy / gate |
| **UNKNOWN** | **Could not evaluate** (environment unavailable) |

**GWO completion rule:** **COMPLETED** / **PRODUCTION PROVEN** only when all **executed** criteria are PASS and no blocking FAIL on executed items. SKIPPED/BLOCKED/UNKNOWN must be listed explicitly with reason.

### 28.7 Workflow lifecycle vs stage status

| Workflow lifecycle | Meaning |
|--------------------|---------|
| **Completed** | All stages ran to summary (may include WARN) |
| **Failed** | Stage FAIL halted pipeline (on_fail=halt) |
| **Blocked** | Safety Gate NO_GO or policy block before mutating stages |
| **Cancelled** | Operator abort |

Stage **SKIPPED** ≠ Workflow **Failed**.

### 28.8 Mapping from current implementation (transitional)

| Current (code/docs) | Canonical (§28) |
|---------------------|-----------------|
| `PreflightStatus.WARNING` | **WARN** |
| `StageStatus.SKIP` | **SKIPPED** |
| Doctor `BLOCKED` overall | Doctor aggregate (unchanged label) |
| Safety Gate `NO_GO` | Workflow **Blocked** + checklist **BLOCKED** |
| Health unreachable (stack down) | **UNKNOWN** (Preflight), not FAIL |
| GWO “0/11 FAIL” | Replace with per-item SKIPPED/BLOCKED/UNKNOWN |

Code alignment: **GWO-G-003B follow-up** (out of scope for this doc revision).

### 28.9 ADR-005 — Semantyka statusów

**Status:** Accepted  
**Context:** GWO-IFG-002A and Preflight reports conflated execution failure with non-execution and unknown conditions.  
**Decision:**

1. Adopt six check statuses: **PASS, WARN, FAIL, BLOCKED, SKIPPED, UNKNOWN**.
2. **Safety Gate** and **DeploymentDecision** use only **GO / NO_GO** — never PASS/FAIL.
3. **Doctor** reports health only; does not gate deploy (Preflight + Safety Gate do).
4. **Production Proven** checklists distinguish executed vs non-executed criteria.
5. **PASS ≠ GO**, **FAIL ≠ BLOCKED**, **UNKNOWN ≠ FAIL**.

**Consequences:**

- (+) Operators can read GWO reports without false “everything failed” narrative.
- (+) Migration windows (stack stopped) documented as UNKNOWN/SKIPPED, not FAIL.
- (−) One-time doc and code migration from `WARNING` and ambiguous PASS usage.

---

## 29. References (v1.0 additions)

- [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE_UPDATE.md](../../reports/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE_UPDATE.md) — changelog v0.1 → v1.0
- [GWO_G003_IMPLEMENTATION_STAGE1.md](../../reports/GWO_G003_IMPLEMENTATION_STAGE1.md) — Etap 1 implementation report
- [GWO_G003A_PREFLIGHT_ENGINE.md](../../reports/GWO_G003A_PREFLIGHT_ENGINE.md) — Preflight Engine + Safety Gate
- [GWO_G003B_STATUS_SEMANTICS.md](../../reports/GWO_G003B_STATUS_SEMANTICS.md) — unified status semantics
- Guardian repo Canon: Repository First, Documentation First (external)

---

**End of document (v1.0).** Etap 1 implementation complete (GWO-G-003). Status semantics canonical in §28 (GWO-G-003B). Production deploy unchanged. Etap 2+ remain gated by GWO.
