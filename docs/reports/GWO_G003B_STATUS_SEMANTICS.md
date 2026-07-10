# GWO-G-003B — Unified Status Semantics

**Date:** 2026-07-06  
**Architecture:** [GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md](../guardian/architecture/GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md) §28  
**Status:** Approved (documentation only)  
**Scope:** Reporting and decision model — **no code changes**

---

## Summary

Guardian reports previously mixed **PASS**, **FAIL**, and **WARN** for semantically different situations (measurement vs non-execution vs unknown). This GWO defines a **canonical six-status model** for checks and separates **technical status** from **operational decision** across Doctor, Preflight, Safety Gate, Workflow, Operation Engine, Validation, and Production reports.

---

## Motivation

### Problems observed (GWO-IFG-002A)

| Report text | Misinterpretation | Correct semantics |
|-------------|-------------------|-------------------|
| Stack stopped → **PASS** | “Production OK” | **UNKNOWN** for health; contextual note for migration window |
| Health unreachable → **FAIL** | “Production broken” | **UNKNOWN** when stack intentionally stopped |
| Production Proven **0/11 FAIL** | “Everything failed” | Etap 3–5 **SKIPPED** after Safety Gate **NO_GO** |
| Preflight GO + “9 FAIL” in checklist | Contradictory | Separate **decision** (GO/NO_GO) from **validation** (executed or SKIPPED) |

Operators reading GWO-IFG-002A could conclude catastrophic prod failure when the procedure was **correctly blocked early**.

---

## Canonical status model

| Status | Operation executed? | Meaning |
|--------|-------------------|---------|
| **PASS** | Yes | Positive result |
| **WARN** | Yes | Warnings; may continue |
| **FAIL** | Yes | Negative result |
| **BLOCKED** | No | Blocked by Safety Gate, Policy, Capability, conscious decision |
| **SKIPPED** | No | Earlier stage halted workflow — **not an error** |
| **UNKNOWN** | N/A | Cannot determine (stack off, timeout, host down) |

### Decision statuses (separate namespace)

| Layer | Allowed values | Never use |
|-------|----------------|-----------|
| **Safety Gate** | `GO`, `NO_GO` | PASS, FAIL |
| **DeploymentDecision** | `GO`, `NO_GO` | PASS, FAIL |
| **Workflow lifecycle** | `Completed`, `Failed`, `Blocked`, `Cancelled` | PASS, FAIL |

### Core rules (ADR-005)

1. **PASS ≠ GO**
2. **FAIL ≠ BLOCKED**
3. **UNKNOWN ≠ FAIL**

---

## Component matrix

| Component | Check-level statuses | Aggregate / lifecycle |
|-----------|---------------------|------------------------|
| **Doctor** | PASS, WARN, FAIL, UNKNOWN | READY / READY_WITH_WARNINGS / BLOCKED / UNKNOWN |
| **Preflight** | PASS, WARN, FAIL, UNKNOWN | Counts → Safety Gate input |
| **Safety Gate** | — | **GO**, **NO_GO** |
| **Workflow** | PASS, WARN, FAIL, SKIPPED, BLOCKED (per stage) | Completed, Failed, Blocked, Cancelled |
| **Operation Engine** | PASS, FAIL, UNKNOWN | Via `OperationResult` |
| **Execution Backend** | PASS, FAIL, UNKNOWN | Platform step outcome |
| **Validation** | PASS, FAIL, SKIPPED, BLOCKED, UNKNOWN | Production Proven items |
| **DeploymentDecision** | — | **GO**, **NO_GO** |
| **Production reports (GWO)** | PASS, FAIL, SKIPPED, BLOCKED, UNKNOWN | No PASS/FAIL ratio |

---

## Role boundaries

### Doctor

- **Question:** Is the environment **healthy**?
- **Does not:** Decide whether deploy may proceed (Preflight + Safety Gate do).
- **Example:** Doctor BLOCKED overall = unhealthy or unmeasurable — informative, not deploy gate.

### Preflight

- **Question:** **May** we execute the operation? (read-only)
- **Output:** Check statuses + `PreflightReport`
- **Does not:** Mutate environment

### Safety Gate

- **Question:** **GO** or **NO_GO**?
- **Input:** Preflight FAIL → NO_GO; WARN → may still GO
- **Effect:** BLOCKED downstream stages (not FAIL on unexecuted validation)

### Workflow

- Reports orchestration outcome: **Completed / Failed / Blocked / Cancelled**
- Stage **SKIPPED** when dependency or gate prevents execution

---

## Technical status vs operational decision

Reports MUST show both when relevant:

```
Check:     Health endpoint
Status:    UNKNOWN          ← technical (stack stopped)
Decision:  —                ← no deploy attempted

Check:     Backup exists (LIVE)
Status:    FAIL             ← technical
Decision:  NO_GO            ← Safety Gate

Check:     API health (Etap 3)
Status:    SKIPPED          ← not executed
Decision:  BLOCKED          ← procedure stopped at Etap 1
```

---

## Production Proven — revised rules

### Do not

- Score “0/11 FAIL” without distinguishing SKIPPED/BLOCKED/UNKNOWN
- Mark unexecuted post-migration checks as FAIL

### Do

| Status | Criterion |
|--------|-----------|
| **PASS** | Executed and met |
| **FAIL** | Executed and not met |
| **SKIPPED** | Not executed — workflow halted earlier |
| **BLOCKED** | Deliberately not run — gate/policy |
| **UNKNOWN** | Could not measure |

**GWO COMPLETED** only when all **executed** required criteria PASS.

---

## GWO-IFG-002A — reinterpreted checklist (example)

Applying §28 to [GWO_IFG_002A_PRODUCTION_MIGRATION.md](./GWO_IFG_002A_PRODUCTION_MIGRATION.md):

| # | Criterion | Old label | Canonical status | Reason |
|---|-----------|-----------|------------------|--------|
| 1 | IFG visible as Project | FAIL | **SKIPPED** | Etap 2 not executed (NO_GO) |
| 2 | No second stack | PASS | **PASS** | Measured pre-migration |
| 3 | API responds | FAIL | **UNKNOWN** | Stack stopped — not measured as failure |
| 4 | Worker runs | FAIL | **SKIPPED** | Etap 2 not executed |
| 5 | DB runs | FAIL | **UNKNOWN** | Stack stopped |
| 6 | Frontend works | FAIL | **SKIPPED** | Etap 2 not executed |
| 7 | Health OK | FAIL | **UNKNOWN** | Stack stopped |
| 8 | Preflight PASS (LIVE) | FAIL | **BLOCKED** | Safety Gate NO_GO (backup) |
| 9 | Guardian verify PASS | FAIL | **FAIL** | Doctor executed — BLOCKED verdict |
| 10 | deploy --dry-run PASS | PASS | **PASS** | Executed successfully |
| 11 | Rollback verified | FAIL | **SKIPPED** | No migration to roll back |

**Summary (canonical):** PASS 2 · FAIL 1 · SKIPPED 5 · BLOCKED 1 · UNKNOWN 3 — **not** “0/11 FAIL”.

**Decision:** **NOT PRODUCTION PROVEN** (unchanged) — but narrative is **procedure blocked at Etap 1**, not total production collapse.

---

## Preflight examples

| Scenario | Old | Canonical |
|----------|-----|-----------|
| SSH OK | PASS | **PASS** |
| Git dirty | WARNING | **WARN** |
| Backup missing (dry-run) | WARNING | **WARN** |
| Backup missing (LIVE) | FAIL | **FAIL** → NO_GO |
| Health unreachable, stack down | WARNING/FAIL | **UNKNOWN** |
| Remote check skipped (test mode) | WARNING | **SKIPPED** or **UNKNOWN** with reason |

---

## Changes made (documentation)

| File | Change |
|------|--------|
| `GUARDIAN_DEPLOYMENT_BACKEND_ARCHITECTURE.md` | New **§28 Status Semantics**, **ADR-005**, §29 References |
| `GWO_G003B_STATUS_SEMANTICS.md` | This report |

**Not changed:** Operation Engine, ComposeBackend, Preflight code (`WARNING` enum remains until code GWO).

---

## Impact

| Area | Impact |
|------|--------|
| **Operators** | Clearer GWO/migration reports; less false alarm |
| **GWO templates** | Use SKIPPED/BLOCKED/UNKNOWN columns |
| **Preflight reports** | Health when stack down → UNKNOWN |
| **Safety Gate** | Unchanged (GO/NO_GO) |
| **Doctor** | Clarified: health only, not deploy gate |
| **Code** | Follow-up GWO for `WARNING`→`WARN`, UNKNOWN classification |

---

## Recommendations

### Immediate (documentation)

1. Use canonical statuses in all new GWO reports (starting with GWO-IFG-002A addendum if reopened).
2. Production Proven tables: five columns (PASS/FAIL/SKIPPED/BLOCKED/UNKNOWN), no aggregate FAIL count alone.

### Follow-up (code — separate GWO)

| Priority | Task |
|----------|------|
| P1 | Rename `PreflightStatus.WARNING` → `WARN` |
| P1 | Classify health-on-stopped-stack as **UNKNOWN** in preflight |
| P2 | GWO report generator helper with SKIPPED propagation after NO_GO |
| P2 | Workflow stage `BLOCKED` when Safety Gate NO_GO (distinct from FAIL) |
| P3 | Doctor dry-run remote skip → **SKIPPED** not WARN |

### Anti-patterns (do not)

- Label **PASS** when operation was not executed
- Use **FAIL** when measurement was impossible
- Conflate Safety Gate **NO_GO** with Validation **FAIL**
- Report Production Proven as fraction of FAIL without SKIPPED context

---

## ADR-005 reference

Full text in architecture doc §28.9.

**Decision:** Six check statuses; GO/NO_GO only for Safety Gate; Doctor ≠ deploy gate; Production Proven distinguishes executed vs non-executed.

---

**End of report.**
