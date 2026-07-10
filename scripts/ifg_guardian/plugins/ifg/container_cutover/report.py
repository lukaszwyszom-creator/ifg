from __future__ import annotations

from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.progress.report import render_timeline_section
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.container_cutover.models import CutoverRunState


def render_markdown(
    state: CutoverRunState,
    *,
    transaction: WorkflowTransaction,
    debt=None,
) -> str:
    lines = [
        "# IFG Container Manager Cutover — Guardian Report",
        "",
        f"**Workflow ID:** `{transaction.workflow_id}`  ",
        f"**Mode:** {'DRY-RUN' if state.dry_run else 'LIVE'}  ",
        f"**Outcome:** {transaction.outcome}  ",
        "",
        "## Runbook",
        "",
        "Source: `docs/runbooks/RUNBOOK_IFG_CONTAINER_MANAGER_CUTOVER.md`",
        "",
        "## Results",
        "",
        "| Step | Status |",
        "|------|--------|",
        f"| SQL backup | {state.backup_file or 'n/a'} |",
        f"| Compose config gate | {'PASS' if state.compose_config_ok else 'FAIL'} |",
        f"| Safety Gate | {state.safety_gate or 'n/a'} |",
        f"| Artifact Verification Gate | {state.artifact_gate_status or ('GO' if state.frontend_artifacts_ok else 'n/a')} |",
        f"| Cutover (compose up) | {'yes' if state.cutover_executed else 'no/simulated'} |",
        f"| Post-health | {'PASS' if state.health_ok else 'FAIL'} |",
        f"| Guardian verify | {'PASS' if state.guardian_verify_ok else 'FAIL'} |",
        f"| Functional attestation | {'yes' if state.functional_confirmed else 'pending'} |",
        f"| Legacy cleanup | {'yes' if state.cleanup_executed else 'skipped'} |",
        "",
        "## Stages",
        "",
        "| Stage | Status | Message |",
        "|-------|--------|---------|",
    ]
    for stage in transaction.stages:
        lines.append(f"| {stage.id} | {stage.status} | {stage.message[:80]} |")

    if state.warnings:
        lines.extend(["", "## Warnings", ""])
        for w in state.warnings:
            lines.append(f"- {w}")

    lines.extend([
        "",
        "## Rollback",
        "",
        "```bash",
        state.rollback_command,
        "```",
        "",
        "Or:",
        "",
        "```bash",
        "python3 scripts/guardian.py ifg cutover rollback --yes",
        "```",
        "",
    ])
    lines.extend(render_timeline_section(transaction.audit.get("progress_timeline")))
    return finish_markdown(lines, debt=debt, state=state, transaction=transaction)
