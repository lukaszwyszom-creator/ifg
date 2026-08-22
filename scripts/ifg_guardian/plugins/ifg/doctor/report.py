from __future__ import annotations

import json
from typing import Any

from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.reporting.renderer import render_guardian_report
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.doctor.models import CheckStatus, DoctorState, OverallStatus


def doctor_from_transaction(transaction: WorkflowTransaction) -> DoctorState:
    payload = transaction.doctor or {}
    return DoctorState.from_dict(payload)


def _status_icon(status: CheckStatus) -> str:
    return {
        CheckStatus.PASS: "✅",
        CheckStatus.WARN: "⚠️",
        CheckStatus.FAIL: "❌",
        CheckStatus.CRITICAL: "🛑",
    }.get(status, "•")


def render_markdown(
    state: DoctorState,
    *,
    transaction: WorkflowTransaction | None = None,
    debt=None,
) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_doctor_report

    report = build_doctor_report(state, transaction)
    lines = render_guardian_report(report)
    if transaction is not None:
        timeline = transaction.audit.get("progress_timeline")
        lines.extend(render_timeline_section(timeline))
    return finish_markdown(lines, debt=debt, state=state, transaction=transaction)


def render_json(state: DoctorState, *, transaction: WorkflowTransaction) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_doctor_report

    report = build_doctor_report(state, transaction)
    payload: dict[str, Any] = {
        "schema": "ifg_doctor_report_v1",
        "standard_schema": report.schema_version(),
        "workflow": transaction.to_dict(),
        "doctor": state.to_dict(),
        "standard_report": {
            "title": report.title,
            "executive_summary": report.executive_summary.__dict__,
            "decision_matrix": [row.__dict__ for row in report.decision_matrix],
        },
    }
    return json.dumps(payload, indent=2)


def render_terminal(state: DoctorState, *, transaction: WorkflowTransaction) -> str:
    lines = [
        "IFG Guardian — IFG Doctor",
        "=" * 40,
        f"Workflow ID: {transaction.workflow_id}",
        f"Overall status: {state.overall_status.value}",
        f"Checks: {len(state.checks)}",
        f"Duration: {transaction.duration_ms} ms",
        "",
    ]
    current_group = ""
    for check in state.checks:
        if check.group != current_group:
            current_group = check.group
            lines.extend(["", f"## {current_group.upper()}", ""])
        lines.append(f"{_status_icon(check.status)} [{check.status.value}] {check.name}: {check.message}")
        for detail in check.details[:3]:
            lines.append(f"    • {detail}")
    lines.extend(["", "=" * 40])
    if state.overall_status == OverallStatus.READY:
        lines.append("Status: READY")
    elif state.overall_status == OverallStatus.READY_WITH_WARNINGS:
        lines.append("Status: READY WITH WARNINGS")
    else:
        lines.append("Status: BLOCKED")
    return "\n".join(lines)
