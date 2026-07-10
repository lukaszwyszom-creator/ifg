# Repository Dependency Graph

**Generated:** 2026-07-07 10:39 UTC  
**Root:** `/Users/lukasz/projekty/ifg_standalone`  
**Scanned files:** 559  
**Tracked nodes:** 818  

## Summary

- Import edges: 1794
- Import cycles: 7
- Modules without importers: 177
- Executable scripts: 26
- Unused scripts: 7
- Modules without tests: 193
- Orphan docs: 100
- CLI commands mapped: 9
- Workflows mapped: 4

## False positives prevented

- Protected (__init__.py): 55
- Entrypoints: 23
- Alembic: 27
- Docs: 273
- Config: 8
- Framework: 121
- **Total:** 507

## Import cycles (sample)

- scripts/ifg_guardian/core/workflow/stage.py → scripts/ifg_guardian/core/workflow/context.py → scripts/ifg_guardian/core/plugins/registry.py → scripts/ifg_guardian/core/workflow/workflow_registry.py → scripts/ifg_guardian/core/workflow/definition.py → scripts/ifg_guardian/core/workflow/stage.py
- scripts/ifg_guardian/core/plugins/registry.py → scripts/ifg_guardian/core/workflow/workflow_registry.py → scripts/ifg_guardian/core/plugins/base.py → scripts/ifg_guardian/core/plugins/context.py → scripts/ifg_guardian/core/plugins/registry.py
- scripts/ifg_guardian/core/workflow/stage.py → scripts/ifg_guardian/core/workflow/context.py → scripts/ifg_guardian/core/workflow/stage.py
- scripts/ifg_guardian/core/workflow/transaction.py → scripts/ifg_guardian/core/workflow/stage.py → scripts/ifg_guardian/core/workflow/context.py → scripts/ifg_guardian/core/workflow/transaction.py
- scripts/ifg_guardian/core/workflow/executors/__init__.py → scripts/ifg_guardian/core/workflow/executors/__init__.py
- scripts/ifg_guardian/modules/repo_audit.py → scripts/ifg_guardian/core/plugins/bootstrap.py → scripts/ifg_guardian/core/plugins/loader.py → scripts/ifg_guardian/plugins/ifg/plugin.py → scripts/ifg_guardian/plugins/ifg/doctor/__init__.py → scripts/ifg_guardian/plugins/ifg/doctor/workflow.py → scripts/ifg_guardian/plugins/ifg/doctor/stages.py → scripts/ifg_guardian/modules/repo_audit.py
- scripts/guardian_platform/core/workflow/stage.py → scripts/guardian_platform/core/workflow/context.py → scripts/guardian_platform/core/workflow/stage.py

## CLI command map

- `ifg deploy check` → `scripts/guardian_platform/profiles/ifg/commands/deploy_check.py`
- `ifg deploy run` → `scripts/guardian_platform/profiles/ifg/commands/deploy_run.py`
- `ifg doctor` → `scripts/guardian_platform/profiles/ifg/commands/doctor.py`
- `ifg frontend check` → `scripts/guardian_platform/profiles/ifg/commands/frontend_check.py`
- `ifg ksef check` → `scripts/guardian_platform/profiles/ifg/commands/ksef_check.py`
- `ifg prod health` → `scripts/guardian_platform/profiles/ifg/commands/prod_health.py`
- `ifg prod recover` → `scripts/guardian_platform/profiles/ifg/commands/prod_recover.py`
- `ifg repo audit` → `scripts/guardian_platform/profiles/ifg/commands/repo_audit.py`
- `ifg repo cleanup` → `scripts/guardian_platform/profiles/ifg/commands/repo_cleanup.py`

## Guardian workflows

- `IFG_DEPLOY_RUN_WORKFLOW` → `scripts/guardian_platform/profiles/ifg/workflows/deploy_run.py`
- `IFG_DOCTOR_WORKFLOW` → `scripts/guardian_platform/profiles/ifg/workflows/doctor.py`
- `IFG_PROD_RECOVER_WORKFLOW` → `scripts/guardian_platform/profiles/ifg/workflows/prod_recover.py`
- `IFG_REPO_AUDIT_WORKFLOW` → `scripts/guardian_platform/profiles/ifg/workflows/repo_audit.py`
