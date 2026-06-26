from __future__ import annotations

import json
from datetime import UTC, datetime

from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.profiles.ifg.recover.models import RecoverState


def render_markdown(state: RecoverState, *, transaction: WorkflowTransaction | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    mode = "DRY-RUN" if state.dry_run else "LIVE"
    lines = [
        "# IFG Guardian — Prod Recover",
        "",
        f"**Generated:** {ts}  ",
        f"**Mode:** {mode}  ",
        f"**Host:** `{state.remote_host}`  ",
    ]
    if transaction:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")

    lines.extend([
        "",
        "## Status",
        "",
        f"- branch: `{state.git_branch}`",
        f"- HEAD: `{state.git_head}`",
        f"- db: {'OK' if state.db_ok else 'FAIL'}",
        f"- api: {'OK' if state.api_ok else 'FAIL'}",
        f"- worker: {'OK' if state.worker_ok else 'FAIL'}",
        f"- health: {'OK' if state.health_ok else 'FAIL'}",
        f"- ksef: {'OK' if state.ksef_ok else 'FAIL'}",
    ])

    if state.aborted:
        lines.extend(["", "## Aborted", "", state.abort_reason])

    if state.notes:
        lines.extend(["", "## Notes", ""])
        for note in state.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def render_json(state: RecoverState, *, transaction: WorkflowTransaction) -> str:
    return json.dumps(
        {"schema": "ifg_prod_recover_v1", "workflow": transaction.to_dict(), "recover": state.to_dict()},
        indent=2,
    )


def render_terminal(state: RecoverState, *, transaction: WorkflowTransaction) -> str:
    mode = "DRY-RUN" if state.dry_run else "LIVE"
    lines = [
        f"IFG Guardian — Prod Recover ({mode})",
        "=" * 40,
        f"Workflow ID: {transaction.workflow_id}",
        f"branch: {state.git_branch}",
        f"HEAD: {state.git_head}",
        f"db/api/worker/health/ksef: {state.db_ok}/{state.api_ok}/{state.worker_ok}/{state.health_ok}/{state.ksef_ok}",
        "",
        "=" * 40,
    ]
    if state.dry_run and not state.aborted:
        lines.append("Status: DRY-RUN COMPLETE")
    elif state.aborted or not state.health_ok:
        lines.append("Status: FAILED")
    else:
        lines.append("Status: RECOVER COMPLETE")
    return "\n".join(lines)


def exit_code_for_recover(state: RecoverState) -> int:
    if state.dry_run and not state.aborted:
        return 0
    if state.aborted or not state.health_ok:
        return 1
    return 0
