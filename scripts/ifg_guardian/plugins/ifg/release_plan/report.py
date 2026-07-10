from __future__ import annotations

import json
from datetime import datetime

from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.time_compat import UTC
from typing import Any

from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.core.reporting.debt import finish_markdown
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
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# IFG Guardian — Release Plan",
        "",
        f"**Generated:** {ts}  ",
        f"**Question:** {state.question}  ",
        f"**Deployment risk:** `{state.deployment_risk.value}`  ",
        f"**Doctor status:** `{state.doctor_overall_status}`  ",
    ]
    if transaction is not None:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")
        lines.append(f"**Duration:** {transaction.duration_ms} ms  ")
        if transaction.dependencies:
            lines.append("")
            lines.append("## Dependencies")
            lines.append("")
            for dep_id, meta in transaction.dependencies.items():
                lines.append(f"- `{dep_id}` → {meta.get('outcome', '?')} ({meta.get('workflow_id', '')})")

    lines.extend([
        "",
        "## Repository",
        "",
        f"- Branch: `{state.repository.branch}`",
        f"- HEAD: `{state.repository.head_short}` (`{state.repository.head_sha}`)",
        f"- Dirty: {state.repository.dirty}",
        f"- Ahead/behind: {state.repository.ahead}/{state.repository.behind}",
        "",
        "## Build decisions",
        "",
        "| Decision | Required | Confidence | Reason |",
        "|----------|----------|------------|--------|",
    ])
    for decision in state.build_decisions:
        req = "yes" if decision.required else "no"
        lines.append(
            f"| {decision.name} | {req} | {decision.confidence} | {decision.reason} |"
        )

    lines.extend(["", "## Artifacts", ""])
    for artifact in state.artifacts:
        lines.append(f"- **{artifact.artifact_type}:** `{artifact.identifier}` — {artifact.notes}")

    lines.extend(["", "## Execution plan", ""])
    for step in state.execution_plan:
        flag = "required" if step.required else "optional"
        lines.append(f"{step.order}. **{step.action}** ({flag}) — {step.description}")

    lines.extend(["", "## Risk rationale", ""])
    for item in state.risk_rationale:
        lines.append(f"- {item}")

    if transaction is not None:
        timeline = transaction.audit.get("progress_timeline")
        lines.extend(render_timeline_section(timeline))

    return finish_markdown(lines, debt=debt, state=state, transaction=transaction)


def render_json(state: ReleasePlanState, *, transaction: WorkflowTransaction) -> str:
    payload: dict[str, Any] = {
        "schema": "ifg_release_plan_report_v1",
        "workflow": transaction.to_dict(),
        "release_plan": state.to_dict(),
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
        mark = "YES" if decision.required else "NO"
        lines.append(f"  [{mark}] {decision.name} ({decision.confidence}) — {decision.reason}")

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
