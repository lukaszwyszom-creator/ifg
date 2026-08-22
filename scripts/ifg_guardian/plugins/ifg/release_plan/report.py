from __future__ import annotations

import json
from typing import Any

from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.reporting.renderer import render_guardian_report
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.release_plan.models import DeploymentRisk, ReleasePlanState


def plan_from_transaction(transaction: WorkflowTransaction) -> ReleasePlanState:
    payload = transaction.release_plan or {}
    return ReleasePlanState.from_dict(payload)


def render_markdown(
    state: ReleasePlanState,
    *,
    transaction: WorkflowTransaction | None = None,
    debt=None,
) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_release_plan_report

    report = build_release_plan_report(state, transaction)
    lines = render_guardian_report(report)
    if transaction is not None:
        timeline = transaction.audit.get("progress_timeline")
        lines.extend(render_timeline_section(timeline))
    return finish_markdown(lines, debt=debt, state=state, transaction=transaction)


def render_json(state: ReleasePlanState, *, transaction: WorkflowTransaction) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_release_plan_report

    report = build_release_plan_report(state, transaction)
    payload: dict[str, Any] = {
        "schema": "ifg_release_plan_report_v1",
        "standard_schema": report.schema_version(),
        "workflow": transaction.to_dict(),
        "release_plan": state.to_dict(),
        "standard_report": {
            "title": report.title,
            "executive_summary": report.executive_summary.__dict__,
            "decision_matrix": [row.__dict__ for row in report.decision_matrix],
        },
    }
    return json.dumps(payload, indent=2)


def render_terminal(state: ReleasePlanState, *, transaction: WorkflowTransaction) -> str:
    lines = [
        "IFG Guardian — Release Plan",
        "=" * 40,
        f"Workflow ID: {transaction.workflow_id}",
        f"Deployment risk: {state.deployment_risk.value}",
        f"Doctor status: {state.doctor_overall_status}",
        "",
        "Dependencies:",
    ]
    for dep_id, meta in transaction.dependencies.items():
        lines.append(f"  • {dep_id}: {meta.get('outcome', '?')}")

    lines.extend(["", "Build decisions:", ""])
    for decision in state.build_decisions:
        if decision.confidence == "BLOCKED":
            mark = "BLOCKED"
        else:
            mark = "YES" if decision.required else "NO"
        lines.append(f"  [{mark}] {decision.name} ({decision.confidence}) — {decision.reason}")
        if decision.trigger_files:
            for path in decision.trigger_files[:8]:
                lines.append(f"      - {path}")

    lines.extend(["", "Execution plan:", ""])
    for step in state.execution_plan:
        req = "required" if step.required else "skip"
        lines.append(f"  {step.order}. {step.action} ({req}) — {step.description}")

    lines.extend(["", "Risk rationale:", ""])
    for item in state.risk_rationale:
        lines.append(f"  • {item}")

    lines.extend(["", "=" * 40])
    if state.deployment_risk == DeploymentRisk.LOW:
        lines.append("Status: LOW RISK")
    elif state.deployment_risk == DeploymentRisk.MEDIUM:
        lines.append("Status: MEDIUM RISK")
    elif state.deployment_risk == DeploymentRisk.HIGH:
        lines.append("Status: HIGH RISK")
    else:
        lines.append("Status: CRITICAL RISK")
    return "\n".join(lines)
