from __future__ import annotations

import json
from typing import Any

from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.reporting.renderer import render_guardian_report
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState, DeployStepStatus


def deploy_from_transaction(transaction: WorkflowTransaction) -> DeployRunState:
    payload = transaction.deploy_run or {}
    return DeployRunState.from_dict(payload)


def render_markdown(
    state: DeployRunState,
    *,
    transaction: WorkflowTransaction | None = None,
    debt=None,
) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_deploy_run_report

    report = build_deploy_run_report(state, transaction)
    lines = render_guardian_report(report)
    if transaction is not None:
        timeline = transaction.audit.get("progress_timeline")
        lines.extend(render_timeline_section(timeline))
    return finish_markdown(lines, debt=debt, state=state, transaction=transaction)


def render_json(state: DeployRunState, *, transaction: WorkflowTransaction) -> str:
    from ifg_guardian.plugins.ifg.reporting.adapters import build_deploy_run_report

    report = build_deploy_run_report(state, transaction)
    payload: dict[str, Any] = {
        "schema": "ifg_deploy_run_report_v1",
        "standard_schema": report.schema_version(),
        "workflow": transaction.to_dict(),
        "deploy_run": state.to_dict(),
        "standard_report": {
            "title": report.title,
            "executive_summary": report.executive_summary.__dict__,
            "decision_matrix": [row.__dict__ for row in report.decision_matrix],
        },
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
        f"Release evaluate: {state.release_evaluate_workflow_id}",
        f"Release decision: {state.release_decision}",
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
        if step.exit_code is not None:
            lines.append(f"      Exit code: {step.exit_code}")
        if not step.skipped:
            verb = "Would run" if state.dry_run else "Ran"
            lines.append(f"      {verb}: {step.command}")
            if step.output and step.status in (DeployStepStatus.EXECUTED, DeployStepStatus.SIMULATED):
                preview = step.output[:120].replace("\n", " ")
                lines.append(f"      Output: {preview}")
            if step.status == DeployStepStatus.FAILED:
                lines.append(f"      Failure: {step.failure_reason or step.error}")

    if state.failed_step:
        lines.extend([
            "",
            "FAILED STEP:",
            f"  {state.failed_step.get('step', '')}",
            "",
            "COMMAND:",
            f"  {state.failed_step.get('command', '')}",
            "",
            "EXIT CODE:",
            f"  {state.failed_step.get('exit_code')}",
            "",
            "STDERR:",
            f"  {state.failed_step.get('stderr', '')}",
            "",
            "ROOT CAUSE:",
            f"  {state.failed_step.get('root_cause', '')}",
        ])

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
    if any(s.status == DeployStepStatus.FAILED for s in state.steps):
        return 1
    return 0
