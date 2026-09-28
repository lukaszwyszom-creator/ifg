# GWO-IFG-PROD-MONITOR-MANAGED-RUNTIME-0010E

**Date:** 2026-09-28  
**Branch:** `gwo/ifg-prod-monitor-managed-runtime-0010e`  
**Scope:** `com.ifg.guardian.prod-monitor` managed runtime only

## STATUS

PROD_MONITOR_DECOUPLED_PR_PENDING

## VERDICT

PROD_MONITOR_DECOUPLED_PR_PENDING

## OUTPUT

```
STATUS: PROD_MONITOR_DECOUPLED_PR_PENDING
VERDICT: PROD_MONITOR_DECOUPLED_PR_PENDING
SOURCE_REPO: /Volumes/WorkspaceSSD/projects/ifg_standalone
SOURCE_SHA: 4b1df454d92314873dd360b25eef8048e51402aa
RUNTIME_ROOT: ~/Library/Application Support/Guardian/ifg-prod-monitor/
RELEASE_PATH: .../releases/<SOURCE_SHA>/
CURRENT_RELEASE: 4b1df454d92314873dd360b25eef8048e51402aa
PREVIOUS_RELEASE: 88840e3c9e761261e616633cd4c21618a40556ea
RUNTIME_MANIFEST: scripts/ifg_guardian/prod_monitor_runtime/MANIFEST.txt (~30 files)
PYTHON_RUNTIME: managed venv via /opt/homebrew/bin/python3.13 (stdlib-only; no pip deps)
STATE_PATH: .../runtime/state/
LOG_PATH: .../runtime/logs/
DEPLOYED_SHA: 4b1df454d92314873dd360b25eef8048e51402aa
PRE_CUTOVER_SMOKE: PASS
LAUNCHAGENT_BEFORE: OLD checkout .venv + WorkingDirectory /Users/lukasz/projekty/ifg_standalone
LAUNCHAGENT_AFTER: managed runner + runtime/venv (internal disk)
LAUNCHAGENT_SMOKE: PASS
TCC_WORKSPACESSD_RUNTIME_DEPENDENCY: NONE
OLD_CHECKOUT_DEPENDENCY: NONE
DS723_READONLY_SMOKE: PASS
ROLLBACK_READY: YES
DEV_BOOTSTRAP_TOUCHED: NO
DS723_MUTATED: NO
KSEF_TOUCHED: NO
DB_TOUCHED: NO
PR1: SUPERSEDED
BRANCH: gwo/ifg-prod-monitor-managed-runtime-0010e
COMMIT: d370b4322d10ce683cf0d4c57e8fbec7846d0aff
PR: https://github.com/lukaszwyszom-creator/ifg/pull/2
TESTS: test_prod_monitor_managed_runtime_0010e.py + test_production_runtime_gwo_0072.py PASS
RISKS: Homebrew python path used only to create venv; runtime uses venv copy. install.py docstring mentions SSD/OLD paths as operator examples only.
NEXT_GWO: GWO-IFG-DEV-BOOTSTRAP-DEMOTION-0010F
```

## Architecture

- Canonical repo remains on WorkspaceSSD.
- Runtime materialization via `git archive` + explicit MANIFEST (not `cp -R`).
- Durable `runtime/state` + `runtime/logs` outside immutable releases.
- Env overrides: `IFG_GUARDIAN_STATE_DIR`, `IFG_GUARDIAN_LOG_DIR`.
- LaunchAgent ProgramArguments: `runtime/venv/bin/python3` + `runner.py`.

## Out of scope (confirmed)

- `pl.ifg.dev-bootstrap` untouched → 0010F
- No TCC/FDA work
- No DS723 deploy / KSeF / DB mutation
- PR #1 not merged (SUPERSEDED)

## RELEASE STATE

- [x] READY_FOR_DEPLOY
- [ ] DEPLOYED_TO_DS723
- [ ] PRODUCTION_VERIFIED

(Note: this GWO deploys Mac-mini LaunchAgent runtime only — not DS723 app containers.)


## Cutover evidence

- Pre-cutover smoke: `Observed: PRODUCTION_RUNNING`, exit 0
- LaunchAgent after: WorkingDirectory / Application Support/Guardian/ifg-prod-monitor
- Program: runtime/venv/bin/python3 + runner.py
- last exit code = 0; no EX_CONFIG
- Rollback 4b1df45 → 88840e3 → 4b1df45: PASS; state preserved
- OLD_CHECKOUT_DEPENDENCY: NONE
- TCC_WORKSPACESSD_RUNTIME_DEPENDENCY: NONE
- pl.ifg.dev-bootstrap: untouched (still OLD checkout — 0010F)
