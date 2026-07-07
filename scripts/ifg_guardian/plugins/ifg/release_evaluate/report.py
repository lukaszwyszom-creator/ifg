from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.time_compat import UTC
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseEvaluateState, StatusSummary


def evaluate_from_transaction(transaction: WorkflowTransaction) -> ReleaseEvaluateState:
    return ReleaseEvaluateState.from_dict(transaction.release_evaluate or {})


def _workflow_duration_ms(transaction: WorkflowTransaction | None) -> int:
    if transaction is None:
        return 0
    return transaction.elapsed_ms()


def _render_summary_block(summary: StatusSummary | None, state: ReleaseEvaluateState) -> list[str]:
    if summary is None:
        return []
    return [
        "## Executive Summary",
        "",
        "| Dimension | Status |",
        "|---|---|",
        f"| **Project status** | `{summary.project_status}` |",
        f"| **Environment status** | `{summary.environment_status}` |",
        f"| **Policy status** | `{summary.policy_status}` |",
        f"| **Deployment recommendation** | `{state.deployment_recommendation}` |",
        "",
        "Operator note: blockers in **BLOCKERS** concern the project or policy. "
        "Items in **LOCAL ENVIRONMENT** reflect this machine's interpreter/tools — "
        "they do not block release by themselves.",
        "",
    ]


def _section(title: str, items: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if items:
        lines.extend([f"- {item}" for item in items])
    else:
        lines.append("- None")
    lines.append("")
    return lines


def render_markdown(state: ReleaseEvaluateState, *, transaction: WorkflowTransaction | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    duration = _workflow_duration_ms(transaction)
    lines = [
        "# IFG Guardian — Release Engine Evaluation",
        "",
        f"**Generated:** {ts}  ",
        f"**Decision:** `{state.status.value}`  ",
        f"**Deployment Profile:** `{state.deployment_profile}`  ",
        f"**Policy Engine:** final decision authority  ",
        f"**Release Score:** `{state.release_score}/100`  ",
        f"**Deployment Recommendation:** **{state.deployment_recommendation}**  ",
        f"**Backup Required:** `{state.backup_required}`  ",
        f"**Staging Required:** `{state.staging_required}`  ",
        f"**Production Blocked:** `{state.production_blocked}`  ",
    ]
    if transaction is not None:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")
        lines.append(f"**Duration:** {duration} ms  ")

    lines.extend(_render_summary_block(state.summary, state))
    lines.extend(["## Decision Rationale", "", state.rationale or "No rationale provided.", ""])
    lines.extend(_section("BLOCKERS", state.blockers))
    lines.extend(_section("WARNINGS", state.warnings))
    lines.extend(_section("LOCAL ENVIRONMENT", state.local_environment))
    lines.extend(_section("INFORMATION", state.information))

    lines.extend(["", "## Release Score Breakdown", "", "| Component | Weight | Score | Rationale |", "|---|---:|---:|---|"])
    for part in state.release_score_parts:
        lines.append(f"| {part.name} | {part.weight} | {part.score} | {part.rationale} |")

    lines.extend(["", "## Change Impact", "", "| Area | Impact |", "|---|---|"])
    for area, level in state.impact.items():
        lines.append(f"| {area} | {level.value} |")

    lines.extend(["", "## Policy Rules Triggered", ""])
    if state.policy_rules_triggered:
        lines.extend([f"- `{rule}`" for rule in state.policy_rules_triggered])
    else:
        lines.append("- None")

    lines.extend(["", "## Required Actions Before Production", ""])
    if state.required_actions:
        lines.extend([f"- {item}" for item in state.required_actions])
    else:
        lines.append("- None")

    lines.extend(["", "## Next Step", "", state.next_step or "N/A", ""])
    if transaction is not None:
        timeline = transaction.audit.get("progress_timeline")
        lines.extend(render_timeline_section(timeline))
    return "\n".join(lines)


def render_json(state: ReleaseEvaluateState, *, transaction: WorkflowTransaction) -> str:
    payload: dict[str, Any] = {
        "schema": "ifg_release_evaluate_report_v1",
        "workflow": transaction.to_dict(),
        "release_evaluate": state.to_dict(),
    }
    return json.dumps(payload, indent=2)


def render_terminal(state: ReleaseEvaluateState, *, transaction: WorkflowTransaction) -> str:
    duration = _workflow_duration_ms(transaction)
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
