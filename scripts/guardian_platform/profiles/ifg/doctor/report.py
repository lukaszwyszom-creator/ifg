from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.profiles.ifg.doctor.models import CheckStatus, DoctorState, OverallStatus


def doctor_from_transaction(transaction: WorkflowTransaction) -> DoctorState:
    payload = transaction.profile_data.get("doctor") or {}
    return DoctorState.from_dict(payload)


def _status_icon(status: CheckStatus) -> str:
    return {
        CheckStatus.PASS: "✅",
        CheckStatus.WARN: "⚠️",
        CheckStatus.FAIL: "❌",
        CheckStatus.CRITICAL: "🛑",
    }.get(status, "•")


def render_markdown(state: DoctorState, *, transaction: WorkflowTransaction | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# IFG Guardian — IFG Doctor",
        "",
        f"**Generated:** {ts}  ",
        f"**Overall status:** `{state.overall_status.value}`  ",
        f"**Question:** Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?  ",
    ]
    if transaction is not None:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")
        lines.append(f"**Duration:** {transaction.duration_ms} ms  ")
    lines.extend(["", "## Checks", ""])
    groups: dict[str, list] = {}
    for check in state.checks:
        groups.setdefault(check.group, []).append(check)
    for group, checks in groups.items():
        lines.append(f"### {group.title()}")
        lines.append("")
        lines.append("| Status | Check | Message |")
        lines.append("|--------|-------|---------|")
        for check in checks:
            lines.append(f"| `{check.status.value}` | {check.name} | {check.message} |")
        lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key, value in state.summary.items():
        lines.append(f"- **{key}:** {value}")
    lines.append("")
    return "\n".join(lines)


def render_json(state: DoctorState, *, transaction: WorkflowTransaction) -> str:
    payload: dict[str, Any] = {
        "schema": "ifg_doctor_report_v1",
        "workflow": transaction.to_dict(),
        "doctor": state.to_dict(),
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
