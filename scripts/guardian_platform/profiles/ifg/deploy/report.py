from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.profiles.ifg.deploy.models import DeployRunState, StepStatus


def render_markdown(state: DeployRunState, *, transaction: WorkflowTransaction | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    mode = "DRY-RUN" if state.dry_run else "LIVE"
    lines = [
        "# IFG Guardian — Deploy Run",
        "",
        f"**Generated:** {ts}  ",
        f"**Mode:** {mode}  ",
        f"**Rollback available:** `{state.rollback_available}`  ",
    ]
    if transaction:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")
        lines.append(f"**Duration:** {transaction.duration_ms} ms  ")

    if state.blockers:
        lines.extend(["", "## Blockers", ""])
        for b in state.blockers:
            lines.append(f"- 🛑 {b}")

    if state.halted:
        lines.extend(["", "## Halted", "", f"- {state.halt_reason}"])

    lines.extend(["", "## Pipeline", ""])
    lines.append("| # | Action | Status | Command |")
    lines.append("|---|--------|--------|---------|")
    for step in state.steps:
        lines.append(f"| {step.order} | {step.action} | {step.status.value} | `{step.command}` |")

    if state.health:
        lines.extend(["", "## Health", "", f"```\n{state.health}\n```"])

    lines.extend(["", "## Summary", ""])
    for k, v in state.summary.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    return "\n".join(lines)


def render_json(state: DeployRunState, *, transaction: WorkflowTransaction) -> str:
    return json.dumps(
        {"schema": "ifg_deploy_run_v1", "workflow": transaction.to_dict(), "deploy": state.to_dict()},
        indent=2,
    )


def render_terminal(state: DeployRunState, *, transaction: WorkflowTransaction) -> str:
    mode = "DRY-RUN" if state.dry_run else "LIVE"
    lines = [
        f"IFG Guardian — Deploy Run ({mode})",
        "=" * 40,
        f"Workflow ID: {transaction.workflow_id}",
        f"Rollback available: {state.rollback_available}",
        "",
    ]
    for step in state.steps:
        lines.append(f"  {step.order}. [{step.status.value}] {step.action}")
        lines.append(f"      {step.command}")
    lines.extend(["", "=" * 40])
    if state.halted:
        lines.append(f"Status: HALTED — {state.halt_reason}")
    elif state.blockers:
        lines.append("Status: BLOCKED")
    elif state.dry_run:
        lines.append("Status: DRY-RUN COMPLETE")
    elif state.smoke_ok:
        lines.append("Status: LIVE COMPLETE")
    else:
        lines.append("Status: LIVE FAILED")
    return "\n".join(lines)


def exit_code_for_deploy(state: DeployRunState) -> int:
    if state.blockers or state.halted:
        return 1
    if any(s.status == StepStatus.FAILED for s in state.steps if s.required):
        return 1
    return 0
