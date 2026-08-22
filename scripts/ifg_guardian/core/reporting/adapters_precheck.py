"""Adapter preflight → wspólny model raportów (bez zależności od pluginów IFG)."""
from __future__ import annotations

from datetime import datetime

from ifg_guardian.core.preflight.models import DeploymentDecision, PreflightReport
from ifg_guardian.core.reporting.renderer import build_standard_build_actions
from ifg_guardian.core.reporting.schema import DecisionRow, DetailSection, ExecutiveSummary, GuardianReport, ScopeCheckRow
from ifg_guardian.core.reporting.status import ConfidenceLevel, normalize_deployment_gate, normalize_preflight_status
from ifg_guardian.core.time_compat import UTC
from ifg_guardian.core.workflow.transaction import WorkflowTransaction


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def build_precheck_report(
    report: PreflightReport,
    *,
    decision: DeploymentDecision,
    workflow_id: str = "",
    transaction: WorkflowTransaction | None = None,
) -> GuardianReport:
    gate = normalize_deployment_gate(decision.status)
    reports: list[str] = []
    handoffs: list[str] = []
    if transaction is not None:
        for artifact in transaction.artifacts:
            if artifact.path:
                reports.append(artifact.path)

    matrix = [
        DecisionRow(
            component=check.label,
            decision=normalize_preflight_status(check.status).value,
            confidence=ConfidenceLevel.HIGH.value,
            reason=check.description,
            impact=check.check_id,
        )
        for check in report.checks
    ]
    local_checks = [
        ScopeCheckRow(
            status=normalize_preflight_status(check.status).value,
            check_id=check.check_id,
            name=check.label,
            message=check.description,
        )
        for check in report.checks
    ]
    operator_actions = list(decision.blocking_items) + list(decision.recommendations)
    if decision.warnings:
        operator_actions.extend(f"Warning: {item}" for item in decision.warnings)
    if not operator_actions:
        operator_actions = ["Precheck complete — proceed per deployment gate."]

    detail_lines = [
        f"| PASS | WARNING | FAIL |",
        f"|------|---------|------|",
        f"| {report.passed} | {report.warnings} | {report.failures} |",
        "",
        "*Read-only preflight — no environment mutations.*",
    ]

    return GuardianReport(
        title="Guardian Preflight — PRECHECK_REPORT",
        generated_at=_timestamp(),
        executive_summary=ExecutiveSummary(
            status=gate.value,
            decision=decision.status.value,
            risk=ConfidenceLevel.UNKNOWN.value,
            workflow=workflow_id or report.workflow_id or "preflight",
            duration_ms=report.duration_ms,
            extras={"Mode": report.mode},
        ),
        decision_matrix=matrix,
        local_checks=local_checks,
        build_actions=build_standard_build_actions({}),
        operator_actions=operator_actions,
        generated_reports=reports,
        generated_handoffs=handoffs,
        detail_sections=[DetailSection(title="Preflight Summary", lines=detail_lines)],
    )
