from __future__ import annotations

from pathlib import Path

from guardian_platform.core.repository.analyzer import RepositoryAnalyzer
from guardian_platform.core.repository.models import FileAnalysis
from guardian_platform.profiles.ifg.repo_cleanup.advisor import advise_path
from guardian_platform.profiles.ifg.repo_cleanup.boundaries import (
    discover_phase0_artifacts,
    is_within_repo_boundary,
)
from guardian_platform.profiles.ifg.repo_cleanup.models import AdvisorDecision, CleanupAction
from guardian_platform.profiles.ifg.repo_cleanup.policy import (
    CleanupOperation,
    CleanupPlan,
    archive_destination,
    is_never_delete_path,
    phase2_destination,
)


def _rollback_for(op: CleanupOperation) -> str:
    if op.action == CleanupAction.LOCAL_REMOVE:
        if op.source.endswith("__pycache__") or "/__pycache__" in op.source:
            return f"Regenerate: run Python/tests (recreates {op.source})"
        if "dist" in op.source or "node_modules" in op.source:
            return f"Rebuild: npm ci && npm run build (restores {op.source})"
        return f"Restore from VCS or rebuild if needed ({op.source})"
    if op.action == CleanupAction.GIT_MV and op.target:
        return f"git mv {op.target} {op.source}"
    return "No rollback required"


def _boundary_paths(files: dict[str, FileAnalysis]) -> dict[str, FileAnalysis]:
    return {p: v for p, v in files.items() if is_within_repo_boundary(p)}


def build_cleanup_plan(
    root: Path,
    *,
    phase: int | None = None,
    dry_run: bool = True,
) -> CleanupPlan:
    analysis = RepositoryAnalyzer(root).analyze()
    tracked_files = _boundary_paths(analysis.files)

    plan = CleanupPlan(phase=phase, dry_run=dry_run)
    phases = [0, 1, 2, 3] if phase is None else [phase]
    seen_candidates: set[str] = set()

    def _track(candidate) -> None:
        if candidate.path not in seen_candidates:
            plan.candidates.append(candidate)
            seen_candidates.add(candidate.path)

    def _append_op(op: CleanupOperation) -> None:
        for check in (op.source, op.target or ""):
            if check and not is_within_repo_boundary(check):
                return
        plan.operations.append(op)

    if 0 in phases:
        for rel in discover_phase0_artifacts(root):
            candidate = advise_path(rel, analysis.files.get(rel))
            _track(candidate)
            if candidate.decision != AdvisorDecision.DELETE:
                continue
            op = CleanupOperation(
                phase=0,
                action=CleanupAction.LOCAL_REMOVE,
                source=rel,
                rationale=candidate.rationale,
                impact=candidate.impact,
                confidence=candidate.confidence,
            )
            op.rollback = _rollback_for(op)
            _append_op(op)

    if 1 in phases:
        for path, graph in sorted(tracked_files.items()):
            if not path.startswith("docs/"):
                continue
            if path.startswith("docs/archive/"):
                continue
            candidate = advise_path(path, graph)
            _track(candidate)
            if candidate.decision != AdvisorDecision.ARCHIVE:
                continue
            target = archive_destination(path)
            if path == target:
                continue
            op = CleanupOperation(
                phase=1,
                action=CleanupAction.GIT_MV,
                source=path,
                target=target,
                rationale=candidate.rationale,
                impact=candidate.impact,
                confidence=candidate.confidence,
            )
            op.rollback = _rollback_for(op)
            _append_op(op)

    if 2 in phases:
        for path, graph in sorted(tracked_files.items()):
            if not path.startswith("docs/"):
                continue
            candidate = advise_path(path, graph)
            if candidate.decision != AdvisorDecision.KEEP:
                continue
            target = phase2_destination(path)
            if not target or path == target:
                continue
            op = CleanupOperation(
                phase=2,
                action=CleanupAction.GIT_MV,
                source=path,
                target=target,
                rationale="Phase 2 organization — REPO_CLEANUP_PLAN target structure",
                impact="Update README links after move",
                confidence=candidate.confidence,
            )
            op.rollback = _rollback_for(op)
            _append_op(op)

    if 3 in phases:
        for path, graph in sorted(tracked_files.items()):
            candidate = advise_path(path, graph)
            if candidate.decision != AdvisorDecision.REVIEW:
                continue
            if is_never_delete_path(path) and graph and graph.recommendation.value == "KEEP":
                continue
            _track(candidate)
            op = CleanupOperation(
                phase=3,
                action=CleanupAction.LIST_REVIEW,
                source=path,
                rationale=candidate.rationale,
                impact=candidate.impact,
                confidence=candidate.confidence,
            )
            _append_op(op)

    plan.rollback_steps = [_rollback_for(op) for op in plan.operations if op.rollback]
    return plan
