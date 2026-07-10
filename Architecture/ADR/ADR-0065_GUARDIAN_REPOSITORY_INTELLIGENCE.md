# ADR-0065 — Guardian Repository Intelligence (GRI)

Status: Proposed  
Date: 2026-07-09  
Decision scope: Guardian Core architecture layer (shared analysis substrate)

## Context

Guardian today answers operational questions well (`can we release now?`) but has limited semantic understanding of *what the repository changes represent*.

Current behavior is mostly file-centric:
- dirty working tree,
- changed files count,
- policy triggers based on paths/rules.

Observed gap during Release Gate work:
- missing first-class model of modules/capabilities/dependencies/change-groups,
- no consistent repository intelligence layer reusable by Release, Cleanup, Doctor, Deploy, GDD, PSAG.

Without a shared model, capabilities duplicate heuristics and produce fragmented explanations.

## Problem Statement

Need a reusable, read-oriented architecture layer that can answer:

1. What logically changed in the repository?
2. Which modules/capabilities are impacted?
3. How changes are related (dependency/impact graph)?
4. Which blockers are primary vs derivative?
5. Which deferred decisions (GDD) map to impacted modules?

This layer must be capability-agnostic and not tied to one workflow.

## Considered Options

### Option A — Keep file-centric checks, improve each capability separately
Pros:
- low short-term cost.

Cons:
- duplicated logic across Release/Cleanup/Doctor/PSAG/GDD,
- inconsistent output semantics,
- hard to maintain and extend.

Decision:
- Rejected.

### Option B — Build GRI as shared in-memory analysis service (on-demand)
Pros:
- single semantic model for repository state,
- reusable by multiple capabilities,
- no mandatory persistent DB,
- easy to integrate incrementally.

Cons:
- requires introducing canonical domain model and contracts,
- needs disciplined capability adoption.

Decision:
- Selected.

### Option C — Build persistent repository knowledge DB first
Pros:
- history and trend analysis ready early.

Cons:
- high complexity and migration burden,
- overkill for immediate release intelligence needs.

Decision:
- Deferred (future extension of Option B).

## Decision

Adopt **Option B**: create **Guardian Repository Intelligence (GRI)** as a shared analysis layer that:

- ingests repository state (git/worktree/policy/test/build signals),
- classifies changes into logical groups and modules,
- builds an impact/dependency graph,
- exposes normalized outputs via API contracts for all capability consumers.

GRI is read-focused. It can suggest, rank, and explain actions but does not mutate repo by itself.

## Target Architecture

### 1) Core Components

1. **Repository Snapshot Adapter**
   - collects raw state:
     - git status,
     - branch/ahead-behind,
     - changed file inventory,
     - workflow outputs (`release evaluate`, `doctor`, etc.).

2. **Change Classifier Engine**
   - maps files to:
     - module,
     - capability,
     - change type (code/test/docs/artifact/config/env),
     - release relevance.

3. **Dependency & Impact Graph**
   - graph nodes:
     - modules,
     - capabilities,
     - blockers,
     - decisions (GDD),
     - tests.
   - graph edges:
     - impacts,
     - requires,
     - blocked_by,
     - mitigated_by,
     - linked_to_gdd.

4. **Blocker Reducer**
   - marks blockers as:
     - primary,
     - derivative/aggregate.
   - example: `PRODUCTION_BLOCKED` => aggregate.

5. **Recommendation Planner**
   - outputs ordered, dependency-aware steps toward target state (`PRODUCTION_READY`).

6. **Consumer Facades**
   - Release, Deploy, Cleanup, Doctor, GDD, PSAG adapters to consume unified GRI objects.

### 2) Canonical Data Model (minimum)

- `RepositorySnapshot`
  - branch, sync status, dirty status, changed files.
- `ChangeItem`
  - path, change_kind, module, capability, category, release_scope.
- `ChangeGroup`
  - id, label, items, relevance (`include/defer/exclude`).
- `Blocker`
  - id, source, severity, primary(bool), depends_on[], auto_fixable(bool), requires_decision(bool).
- `ImpactRelation`
  - source_module -> target_module (type, confidence).
- `TestGateState`
  - required tests, discovery state, pass/fail blockers.
- `GRIRecommendationStep`
  - action, expected_result, unblocks[].

### 3) Information Flow

1. Raw inputs (git + workflow outputs) -> `RepositorySnapshot`.
2. Classifier -> `ChangeItem` + `ChangeGroup`.
3. Policy/workflow parser -> `Blocker` set.
4. Reducer -> primary/derivative blocker decomposition.
5. Graph builder -> impact and dependency graph.
6. Planner -> ordered remediation plan.
7. Capability facade renders domain-specific output.

## Integration Plan

### Release Gate
- Replace file-count-only phrasing with grouped, semantic explanation.
- Show primary blockers only; derive aggregates separately.
- Add `release advise` output from same source model.

### Deploy
- Use GRI preflight summary:
  - what is in release scope,
  - what is out-of-scope noise,
  - which prerequisites are pending.

### Cleanup
- Reclassify `N files` into semantic bins:
  - artifacts,
  - reports,
  - docs,
  - generated/cache.

### Doctor
- Attach environment/tooling failures to affected gates and modules.
- Distinguish local env issues from production policy blockers.

### GDD
- Link deferred decisions to impacted modules/capabilities from GRI graph.
- Enable `open GDD impacting current release scope`.

### PSAG
- Reuse classifier + graph metrics for repository class scoring.
- Avoid separate interpretation pipeline.

## Consequences

### Positive
- consistent explanations across Guardian capabilities,
- better operator decisions (primary vs derivative blockers),
- lower duplication of repository-analysis heuristics,
- stronger foundation for advisory tooling.

### Negative / Cost
- requires contract governance for taxonomy (module/capability labels),
- initial integration effort across multiple workflows,
- temporary dual-path period (legacy + GRI).

## Migration Strategy

Phase 0 — Taxonomy baseline
- define canonical module/capability map and category enums.

Phase 1 — Read-only MVP
- implement GRI snapshot + classifier + blocker reducer.
- expose via `guardian release advise` (analysis only).

Phase 2 — Consumer adoption
- Release evaluate + Release advise use GRI first.
- add GRI summaries to Deploy and Doctor.

Phase 3 — Cross-capability convergence
- integrate Cleanup and GDD linking.
- add PSAG interface.

Phase 4 — Optional persistence
- if needed, add historical snapshot store for trend analysis.

## Guardrails

- GRI does not execute deploys/commits/pushes.
- GRI outputs are advisory and explainable.
- Policy engine remains final authority for release decisions.

## Decision

Adopt GRI as shared, read-oriented architecture layer in Guardian Core and integrate incrementally starting with Release advisory path.
