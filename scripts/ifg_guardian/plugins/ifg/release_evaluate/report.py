from __future__ import annotations

import json
from typing import Any

from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.reporting.renderer import render_guardian_report
from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseEvaluateState


def evaluate_from_transaction(transaction: WorkflowTransaction) -> ReleaseEvaluateState:
    return ReleaseEvaluateState.from_dict(transaction.release_evaluate or {})


def render_markdown(
    state: ReleaseEvaluateState,
    *,
    transaction: WorkflowTransaction | None = None,
    debt=None,
) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_release_evaluate_report

    report = build_release_evaluate_report(state, transaction)
    lines = render_guardian_report(report)
    if transaction is not None:
        timeline = transaction.audit.get("progress_timeline")
        lines.extend(render_timeline_section(timeline))
    return finish_markdown(lines, debt=debt, state=state, transaction=transaction)


def render_json(state: ReleaseEvaluateState, *, transaction: WorkflowTransaction) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_release_evaluate_report

    report = build_release_evaluate_report(state, transaction)
    payload: dict[str, Any] = {
        "schema": "ifg_release_evaluate_report_v1",
        "standard_schema": report.schema_version(),
        "workflow": transaction.to_dict(),
        "release_evaluate": state.to_dict(),
        "standard_report": {
            "title": report.title,
            "executive_summary": report.executive_summary.__dict__,
            "decision_matrix": [row.__dict__ for row in report.decision_matrix],
        },
    }
    return json.dumps(payload, indent=2)


def render_terminal(state: ReleaseEvaluateState, *, transaction: WorkflowTransaction) -> str:
    duration = transaction.elapsed_ms()
    lines = [
        "IFG Guardian — Release Engine Evaluation",
        "=" * 44,
        f"Workflow ID: {transaction.workflow_id}",
        f"Duration: {duration} ms",
        f"Decision: {state.status.value}",
        f"Deployment Profile: {state.deployment_profile}",
        "Policy Engine: final decision authority",
        f"Release Score: {state.release_score}/100",
        f"Deployment Recommendation: {state.deployment_recommendation}",
        f"Backup Required: {state.backup_required}",
        f"Staging Required: {state.staging_required}",
        f"Production Blocked: {state.production_blocked}",
        "",
    ]
    if state.summary is not None:
        lines.extend(
            [
                "Executive Summary:",
                f"  Project status:           {state.summary.project_status}",
                f"  Environment status:       {state.summary.environment_status}",
                f"  Policy status:            {state.summary.policy_status}",
                f"  Deployment recommendation: {state.deployment_recommendation}",
                "",
            ]
        )

    lines.extend(["BLOCKERS:"])
    if state.blockers:
        lines.extend([f"  • {item}" for item in state.blockers])
    else:
        lines.append("  • none")

    lines.extend(["", "WARNINGS:"])
    if state.warnings:
        lines.extend([f"  • {item}" for item in state.warnings])
    else:
        lines.append("  • none")

    lines.extend(["", "LOCAL ENVIRONMENT:"])
    if state.local_environment:
        lines.extend([f"  • {item}" for item in state.local_environment])
    else:
        lines.append("  • none")

    lines.extend(["", "INFORMATION:"])
    if state.information:
        lines.extend([f"  • {item}" for item in state.information[:8]])
        if len(state.information) > 8:
            lines.append(f"  • … and {len(state.information) - 8} more")
    else:
        lines.append("  • none")

    lines.extend(["", "Next Step:", f"  {state.next_step}", "", "=" * 44])
    return "\n".join(lines)
