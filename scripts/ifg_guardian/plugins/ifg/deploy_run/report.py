from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState, DeployStepStatus


def deploy_from_transaction(transaction: WorkflowTransaction) -> DeployRunState:
    payload = transaction.deploy_run or {}
    return DeployRunState.from_dict(payload)


def render_markdown(state: DeployRunState, *, transaction: WorkflowTransaction | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    mode = "DRY-RUN" if state.dry_run else "LIVE"
    lines = [
        "# IFG Guardian — Deploy Run",
        "",
        f"**Generated:** {ts}  ",
        f"**Mode:** {mode}  ",
        f"**Deployment risk:** `{state.deployment_risk}`  ",
        f"**Doctor status:** `{state.doctor_status}`  ",
        f"**Release plan:** `{state.release_plan_workflow_id}`  ",
    ]
    if transaction is not None:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")
        lines.append(f"**Duration:** {transaction.duration_ms} ms  ")
        if transaction.dependencies:
            lines.extend(["", "## Dependencies", ""])
            for dep_id, meta in transaction.dependencies.items():
                lines.append(f"- `{dep_id}` → {meta.get('outcome', '?')}")

    if state.rollback_point.commit_before or state.rollback_point.alembic_before:
        lines.extend(["", "## Rollback point", ""])
        lines.append(f"- **commit_before:** `{state.rollback_point.commit_before}`")
        lines.append(f"- **images_before:** `{state.rollback_point.images_before}`")
        lines.append(f"- **alembic_before:** `{state.rollback_point.alembic_before}`")

    if state.blockers:
        lines.extend(["", "## Blockers", ""])
        for blocker in state.blockers:
            lines.append(f"- 🛑 {blocker}")

    if state.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in state.warnings:
            lines.append(f"- ⚠ {warning}")

    lines.extend(["", "## Execution pipeline", ""])
    lines.append("| # | Action | Required | Status | Duration | Reason | Command |")
    lines.append("|---|--------|----------|--------|----------|--------|---------|")
    for step in state.steps:
        req = "yes" if step.required else "no"
        status = step.status.value
        if step.skipped:
            status = "SKIPPED"
        lines.append(
            f"| {step.order} | {step.action} | {req} | {status} | {step.duration_ms}ms "
            f"| {step.reason} | `{step.command}` |"
        )

    if state.executed_commands:
        lines.extend(["", "## Executed commands", ""])
        for cmd in state.executed_commands:
            lines.append(f"- `{cmd}`")

    if state.health:
        lines.extend(["", "## Health", "", f"```\n{state.health}\n```"])

    if state.containers:
        lines.extend(["", "## Containers", "", f"```\n{state.containers}\n```"])

    lines.extend(["", "## Summary", ""])
    for key, value in state.summary.items():
        lines.append(f"- **{key}:** {value}")
    lines.append("")
    return "\n".join(lines)


def render_json(state: DeployRunState, *, transaction: WorkflowTransaction) -> str:
    payload: dict[str, Any] = {
        "schema": "ifg_deploy_run_report_v1",
        "workflow": transaction.to_dict(),
        "deploy_run": state.to_dict(),
    }
    return json.dumps(payload, indent=2)


def render_terminal(state: DeployRunState, *, transaction: WorkflowTransaction) -> str:
    lines = [
        "IFG Guardian — Deploy Run (DRY-RUN)" if state.dry_run else "IFG Guardian — Deploy Run (LIVE)",
        "=" * 40,
        f"Workflow ID: {transaction.workflow_id}",
        f"Mode: {'DRY-RUN' if state.dry_run else 'LIVE'}",
        f"Duration: {transaction.duration_ms} ms",
        f"Deployment risk: {state.deployment_risk}",
        f"Doctor status: {state.doctor_status}",
        f"Release plan: {state.release_plan_workflow_id}",
        "",
        "Dependencies:",
    ]
    for dep_id, meta in transaction.dependencies.items():
        lines.append(f"  • {dep_id}: {meta.get('outcome', '?')}")

    if state.rollback_point.commit_before:
        lines.extend([
            "",
            "Rollback point:",
            f"  commit: {state.rollback_point.commit_before}",
            f"  alembic: {state.rollback_point.alembic_before or 'n/a'}",
        ])

    if state.blockers:
        lines.extend(["", "Blockers:", ""])
        for blocker in state.blockers:
            lines.append(f"  🛑 {blocker}")

    lines.extend(["", "Pipeline:", ""])
    for step in state.steps:
        if step.skipped:
            label = "SKIP"
        elif step.status == DeployStepStatus.SIMULATED:
            label = "SIMULATED"
        elif step.status == DeployStepStatus.EXECUTED:
            label = "EXECUTED"
        elif step.status == DeployStepStatus.FAILED:
            label = "FAILED"
        elif step.required:
            label = "REQUIRED"
        else:
            label = "OPTIONAL"
        lines.append(f"  {step.order}. [{label}] {step.action}")
        lines.append(f"      Why: {step.reason}")
        if not step.skipped:
            verb = "Would run" if state.dry_run else "Ran"
            lines.append(f"      {verb}: {step.command}")
            if step.output and step.status in (DeployStepStatus.EXECUTED, DeployStepStatus.SIMULATED):
                preview = step.output[:120].replace("\n", " ")
                lines.append(f"      Output: {preview}")

    lines.extend(["", "=" * 40])
    required = sum(1 for s in state.steps if s.required and not s.skipped)
    simulated = sum(1 for s in state.steps if s.status == DeployStepStatus.SIMULATED)
    executed = sum(1 for s in state.steps if s.status == DeployStepStatus.EXECUTED)
    if state.dry_run:
        lines.append(f"Required steps: {required}, simulated: {simulated}, blockers: {len(state.blockers)}")
    else:
        lines.append(f"Required steps: {required}, executed: {executed}, blockers: {len(state.blockers)}")
    if state.blockers:
        lines.append("Status: BLOCKED")
    elif state.dry_run:
        lines.append("Status: DRY-RUN COMPLETE (no changes made)")
    elif any(s.status == DeployStepStatus.FAILED for s in state.steps):
        lines.append("Status: LIVE FAILED")
    else:
        lines.append("Status: LIVE COMPLETE")
    return "\n".join(lines)


def exit_code_for_deploy(state: DeployRunState) -> int:
    if state.blockers:
        return 1
    if state.deployment_risk == "CRITICAL":
        return 1
    if any(s.status == DeployStepStatus.FAILED for s in state.steps):
        return 1
    return 0
