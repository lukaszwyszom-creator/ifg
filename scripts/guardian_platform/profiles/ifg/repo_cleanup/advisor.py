from __future__ import annotations

from guardian_platform.core.repository.models import FileAnalysis, FileStatus, Recommendation
from guardian_platform.profiles.ifg.repo_cleanup.history import classify_history
from guardian_platform.profiles.ifg.repo_cleanup.models import AdvisorDecision, HistoryKind
from guardian_platform.profiles.ifg.repo_cleanup.policy import (
    AdvisorCandidate,
    KEEP_CANONICAL_DOCS,
    archive_destination,
    is_never_delete_path,
    phase2_destination,
)


def _confidence_base(graph: FileAnalysis, history: HistoryKind) -> int:
    score = 50
    if graph.protected_category and graph.protected_category != "NONE":
        score += 25
    if history in {HistoryKind.CANONICAL, HistoryKind.CLOSED_INCIDENT, HistoryKind.SPRINT_REPORT}:
        score += 20
    if graph.metrics.imported_by >= 3 or graph.metrics.test_refs >= 2:
        score += 15
    if graph.risk.value == "HIGH":
        score += 10
    return min(score, 95)


def advise_document(path: str, graph: FileAnalysis) -> AdvisorCandidate:
    history, history_note = classify_history(path)
    name = path.rsplit("/", 1)[-1]

    if name in KEEP_CANONICAL_DOCS or history == HistoryKind.CANONICAL:
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="canonical documentation — always KEEP",
            decision=AdvisorDecision.KEEP,
            confidence=98,
            rationale="Canonical IFG/Guardian reference document",
            impact="Removing would break documentation map and cleanup plan",
        )

    if history == HistoryKind.CLOSED_INCIDENT or history == HistoryKind.SPRINT_REPORT:
        conf = 97 if history == HistoryKind.CLOSED_INCIDENT else 94
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="archive finished incidents and sprint reports",
            decision=AdvisorDecision.ARCHIVE,
            confidence=conf,
            rationale=f"{history_note} — move to {archive_destination(path)}",
            impact="Historical reference preserved in archive; no code impact",
        )

    if history == HistoryKind.RUNTIME_REPORT:
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="archive runtime Guardian reports",
            decision=AdvisorDecision.ARCHIVE,
            confidence=92,
            rationale="Generated runtime report — archive under docs/archive/2026-06/",
            impact="Low — superseded by newer reports",
        )

    if history == HistoryKind.OPERATIONS or phase2_destination(path):
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="operations / phase-2 organization target",
            decision=AdvisorDecision.KEEP,
            confidence=88,
            rationale="Active operations documentation — reorganize in phase 2",
            impact="Link updates required in README during phase 2",
        )

    if graph.recommendation == Recommendation.REVIEW or graph.status == FileStatus.UNKNOWN:
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="requires human review before archive or delete",
            decision=AdvisorDecision.REVIEW,
            confidence=max(60, _confidence_base(graph, history)),
            rationale="Ambiguous documentation — manual review required",
            impact="Unknown until reviewed",
        )

    if graph.recommendation == Recommendation.DELETE:
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="IFG policy blocks DELETE on docs",
            decision=AdvisorDecision.REVIEW,
            confidence=85,
            rationale="Repo Graph suggested DELETE — overridden by IFG doc protection policy",
            impact="Must not auto-delete documentation",
        )

    return AdvisorCandidate(
        path=path,
        graph_status=graph.status.value,
        graph_recommendation=graph.recommendation.value,
        graph_risk=graph.risk.value,
        history=history,
        history_note=history_note,
        policy_rule="default documentation KEEP",
        decision=AdvisorDecision.KEEP,
        confidence=80,
        rationale="Documentation retained pending explicit review",
        impact="None",
    )


def advise_code_path(path: str, graph: FileAnalysis) -> AdvisorCandidate:
    history, history_note = classify_history(path)

    if is_never_delete_path(path):
        decision = AdvisorDecision.KEEP
        if graph.recommendation == Recommendation.REVIEW:
            decision = AdvisorDecision.REVIEW
        conf = 96 if graph.status in {FileStatus.PROTECTED, FileStatus.ENTRYPOINT, FileStatus.FRAMEWORK} else 90
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="production path — DELETE forbidden",
            decision=decision,
            confidence=conf,
            rationale="Protected production code or configuration",
            impact=f"Imported by {graph.metrics.imported_by}; tests {graph.metrics.test_refs}",
        )

    if graph.recommendation == Recommendation.DELETE and graph.risk.value == "SAFE":
        return AdvisorCandidate(
            path=path,
            graph_status=graph.status.value,
            graph_recommendation=graph.recommendation.value,
            graph_risk=graph.risk.value,
            history=history,
            history_note=history_note,
            policy_rule="orphan with SAFE risk — REVIEW before delete",
            decision=AdvisorDecision.REVIEW,
            confidence=75,
            rationale="Potential dead code — requires explicit REVIEW approval",
            impact="Low if truly unused",
        )

    decision = AdvisorDecision.KEEP
    if graph.recommendation == Recommendation.REVIEW:
        decision = AdvisorDecision.REVIEW

    return AdvisorCandidate(
        path=path,
        graph_status=graph.status.value,
        graph_recommendation=graph.recommendation.value,
        graph_risk=graph.risk.value,
        history=history,
        history_note=history_note,
        policy_rule="default code KEEP",
        decision=decision,
        confidence=_confidence_base(graph, history),
        rationale="Production code retained",
        impact=f"Imported by {graph.metrics.imported_by}",
    )


def advise_path(path: str, graph: FileAnalysis | None) -> AdvisorCandidate:
    if graph is None:
        history, history_note = classify_history(path)
        if history == HistoryKind.LOCAL_ARTIFACT:
            return AdvisorCandidate(
                path=path,
                graph_status="N/A",
                graph_recommendation="N/A",
                graph_risk="SAFE",
                history=history,
                history_note=history_note,
                policy_rule="phase 0 local artifact",
                decision=AdvisorDecision.DELETE,
                confidence=99,
                rationale="Local cache/build artifact — safe local removal",
                impact="Regenerated on next build/run",
            )
        return AdvisorCandidate(
            path=path,
            graph_status="UNKNOWN",
            graph_recommendation="UNKNOWN",
            graph_risk="UNKNOWN",
            history=history,
            history_note=history_note,
            policy_rule="untracked path",
            decision=AdvisorDecision.REVIEW,
            confidence=50,
            rationale="Path not in repository graph",
            impact="Unknown",
        )

    if path.startswith("docs/") or path.endswith(".md"):
        return advise_document(path, graph)
    return advise_code_path(path, graph)
