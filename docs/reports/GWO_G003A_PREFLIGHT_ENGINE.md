# GWO-G-003A — Preflight Engine & Safety Gate

**Date:** 2026-07-06  
**Architecture:** [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md](../guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md) §26  
**Status:** Complete  
**Scope:** Operational safety layer before production deploy — **not** a new architecture version

---

## Summary

Guardian gained a read-only **Preflight Engine** and **Safety Gate** that run before deploy execution. If any critical check fails, deploy is blocked with **NO_GO** and a `PRECHECK_REPORT` artifact. Existing Execution Backend / Operation Engine classes were **not modified**.

---

## Philosophy

> Guardian ma być bardziej ostrożny niż operator.

Preflight performs verification only — no compose, no deploy, no restart. Safety Gate converts check results into **GO** or **NO_GO**.

---

## Layer placement

```
Workflow (ifg.deploy.run)
    ↓
Preflight Engine      ← NEW (read-only)
    ↓
Safety Gate           ← NEW (GO / NO_GO)
    ↓
Operation Engine      ← unchanged
    ↓
ComposeBackend        ← unchanged
```

---

## New module: `ifg_guardian/core/preflight/`

| File | Purpose |
|------|---------|
| `models.py` | `PreflightStatus`, `PreflightCheckResult`, `PreflightReport`, `DeploymentDecision`, `PreflightContext` |
| `config.py` | Backup dir, max age, disk threshold, postgres volume name |
| `probes.py` | Read-only SSH probe helper |
| `checks.py` | 19 individual checks |
| `engine.py` | `PreflightEngine.run()` |
| `gate.py` | `SafetyGate.evaluate()` |
| `report.py` | `PRECHECK_REPORT.md` renderer |

---

## Models

### DeploymentDecision

| Field | Type |
|-------|------|
| `status` | `GO` \| `NO_GO` |
| `blocking_items` | list of FAIL descriptions |
| `warnings` | list of WARNING descriptions |
| `recommendations` | operator guidance |

### PreflightCheckResult

| Field | Type |
|-------|------|
| `status` | `PASS` \| `WARNING` \| `FAIL` |
| `description` | outcome text |
| `duration_ms` | execution time |
| `details` | structured debug dict |

---

## Check catalog

| Check | Blocking (FAIL) | Notes |
|-------|-----------------|-------|
| Repo accessible | Yes | Local root path |
| Compose file exists | Yes | `docker/docker-compose.prod.yml` |
| Local `.env` | Warning if missing | Remote verified separately |
| Git branch | FAIL on LIVE | WARNING on dry-run |
| Git clean | Warning | Uncommitted changes |
| SSH | Yes | Read-only echo probe |
| Docker available | Yes | Remote |
| Docker Compose available | Yes | Remote |
| Compose config valid | Yes | `compose config` exit 0 |
| Compose config validation | Yes | Must reference `docker_postgres_data` |
| Remote `.env` | Yes | On DS723+ |
| PostgreSQL volume | Yes | `docker volume inspect` |
| External volume pin | FAIL if `name: ifg` without external | WARNING pre-migration |
| Backup exists | FAIL on LIVE | WARNING on dry-run |
| Backup freshness | Warning | Default max 7 days |
| Health endpoint | Warning | OK if stack stopped |
| Disk space | Warning | Min 5 GB free |
| Docker permissions | Yes | `docker ps` |

---

## Workflow integration

**New file:** `plugins/ifg/deploy_run/preflight_stage.py` — `PreflightStage`

**Modified:** `plugins/ifg/deploy_run/workflow.py` — stage inserted before `SimulateExecutionStage`

Stage count: 7 → **8**

On NO_GO:
- Workflow halts before `SimulateExecutionStage`
- `PRECHECK_REPORT_YYYY_MM_DD.md` written to `docs/guardian/`
- Transaction artifact `precheck_report` recorded

Escape hatches (tests / emergency):
- `ctx.data["skip_preflight"] = True`
- `ctx.data["skip_preflight_remote"] = True`

---

## Not implemented (separate GWO)

- Auto repair
- Auto backup
- Auto rollback

---

## Files changed

| Path | Change |
|------|--------|
| `scripts/ifg_guardian/core/preflight/*` | **Added** (8 files) |
| `scripts/ifg_guardian/plugins/ifg/deploy_run/preflight_stage.py` | **Added** |
| `scripts/ifg_guardian/plugins/ifg/deploy_run/workflow.py` | **Modified** — +PreflightStage |
| `tests/unit/test_guardian_preflight.py` | **Added** |
| `tests/unit/test_guardian_ifg_deploy_run_workflow.py` | **Modified** — stage count, preflight mock |
| `docs/guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md` | **Modified** — §26 |

**Not modified:** `OperationEngine`, `ComposeBackend`, `DeploymentEngine`, `IntentExecutor` routing.

---

## Test results

```bash
python3.11 -m pytest tests/unit/test_guardian_*.py --confcutdir=tests/unit -q
```

| Suite | Result |
|-------|--------|
| `ifg_guardian` unit tests | **110 passed** (+6 preflight) |

---

## Production impact

| Aspect | Effect |
|--------|--------|
| LIVE deploy without passing preflight | **Blocked** (NO_GO) |
| Dry-run | Also blocked on NO_GO (same Safety Gate) |
| Remote checks | Require SSH to DS723+ |
| Backup check | LIVE deploy requires backup in `/volume1/docker/ifg_v2/backups` |

**Before first production deploy:** ensure DS723+ backup exists and SSH probes succeed, or expect NO_GO.

---

## Risks

| Risk | Mitigation |
|------|------------|
| False NO_GO (no backup yet) | Create pre-migration backup per GWO-IFG-002 |
| SSH timeout slows deploy | 120s probe timeout; checks are parallelizable in future |
| Stack stopped → health WARNING | Expected; not blocking |

---

**End of report.**
