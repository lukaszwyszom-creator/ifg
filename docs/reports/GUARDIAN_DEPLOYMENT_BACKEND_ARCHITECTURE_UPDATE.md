# Guardian Deployment Backend Architecture — Update Report

**Date:** 2026-07-05  
**Document updated:** [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md](../guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md)  
**Previous version:** 0.1 (Draft)  
**New version:** 1.0 (Approved)

---

## Summary

The architecture document was extended from a deployment-centric model to a **universal Guardian Operation Engine** without removing or shortening existing content (§1–14). New sections §15–23 define v1.0 execution architecture, naming evolution, capabilities, discovery, events, roadmap, and ADRs.

---

## Changes

### Metadata

- Status: Draft → **Approved**
- Version: 0.1 → **1.0**
- Added version note explaining relationship between §1–14 (v0.1 foundation) and §15–23 (v1.0 extensions)

### §15 — Abstraction level (new)

- Compared `DeploymentBackend`, `ExecutionBackend`, and `RuntimeBackend`
- **Decision:** adopt `ExecutionBackend` as canonical name; keep `DeploymentBackend` as deprecated alias through v4
- Rejected `RuntimeBackend` (confusion with container/runtime layer)
- Terminology mapping table and phased naming migration (v3–v5)

### §16 — Capability Model (new)

- Backends declare capabilities instead of Workflow guessing
- Catalog: `supports_build`, `supports_restart`, `supports_logs`, `supports_stream`, `supports_snapshot`, `supports_backup`, `supports_restore`, `supports_health`, `supports_shell`, `supports_exec`, `supports_project`, `supports_scaling`, `supports_rolling_update`
- Capability Engine validation flow and Profile `requires` concept

### §17 — Discovery Engine (new)

- Pipeline: Host → Platform → Container Manager → Project → Backend
- Selection priority: CLI → Profile → Discovery → fallback
- IFG/DS723+ example flow; caching via `.guardian/runtime-context.json`

### §18 — Event Bus (new)

- Event taxonomy: Deployment*, Operation*, HealthChanged, BackendSelected, Verification*, Backup*, Rollback*
- Envelope schema, use cases, recommended JSONL-first implementation

### §19 — Guardian Operation Engine (new)

- Central thesis: **Deploy is one Operation**
- Operation catalog: Deploy, Update, Restart, Start, Stop, Backup, Restore, Verify, Health, Snapshot, Cleanup, Inventory, Audit, Repair, Rollback
- Layer responsibilities: Workflow picks Operation; Operation Engine picks Backend

### §20 — Guardian Execution Architecture vNext (new)

- Layer diagram: CLI → Operation Engine → Discovery / Capability / Event Bus → Execution Backend → Runtime → Infrastructure
- Role table for each layer; relation to §5.1

### §21 — Roadmap (new)

- **v3:** Foundation — DeploymentBackend alias, OperationEngine skeleton, Discovery manual, events JSONL
- **v4:** Synology Project, full lifecycle operations, capability enforcement, deprecate DeploymentEngine as primary API
- **v5:** Backup/Restore/Snapshot/Audit, optional K8s backends, remove DeploymentBackend name, retire guardian2 monolith

### §22 — ADRs (new)

- ADR-001: Workflow nie zna backendu
- ADR-002: Operation ważniejsze niż Deploy
- ADR-003: Capability jako osobna warstwa
- ADR-004: Discovery wybiera backend

### §23 — Approval & summary (new)

- Status: Approved, Version: 1.0
- “Co zyskuje Guardian po tej architekturze?” — six bullet summary

### §24 — References (new)

- Link to this update report

---

## Unchanged

- All §1–14 content preserved (Executive summary, problem statement, DeploymentEngine/Backend, Synology research, migration Etap 1–5, Profile YAML, testing, risks, GWO recommendations)
- Core philosophy: Workflow does not call `docker compose` or `synowebapi` directly

---

## Out of scope (as requested)

- No code changes
- No repository changes beyond these two markdown files
- No deploy or production migration

---

**End of report.**
