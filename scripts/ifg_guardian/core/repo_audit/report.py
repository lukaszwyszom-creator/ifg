from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ifg_guardian.config import TARGET_BRANCH
from ifg_guardian.core.git import short_sha
from ifg_guardian.core.repo_audit.models import RepoAuditState
from ifg_guardian.core.risk import FileCategory, RiskLevel
from ifg_guardian.core.workflow.transaction import WorkflowTransaction


def audit_from_transaction(transaction: WorkflowTransaction) -> RepoAuditState:
    payload = transaction.audit or {}
    return RepoAuditState.from_dict(payload)


def render_markdown(audit: RepoAuditState, *, transaction: WorkflowTransaction | None = None) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# IFG Guardian — Repo Audit",
        "",
        f"**Generated:** {ts}  ",
        f"**Branch:** `{audit.branch}`  ",
        f"**HEAD:** `{short_sha(audit.head)}`  ",
        f"**Overall risk:** `{audit.overall_risk.value}`  ",
    ]
    if transaction is not None:
        lines.append(f"**Workflow ID:** `{transaction.workflow_id}`  ")
        lines.append(f"**Duration:** {transaction.duration_ms} ms  ")
    lines.extend([
        "",
        "## Repo status",
        "",
        f"- Working tree: {'dirty' if audit.dirty else 'clean'}",
        f"- Ahead of origin/{TARGET_BRANCH}: {audit.ahead}",
        f"- Behind origin/{TARGET_BRANCH}: {audit.behind}",
        f"- `.gitignore`: {'present' if audit.gitignore_exists else 'MISSING'}",
        f"- `.gitattributes`: {'present' if audit.gitattributes_exists else 'MISSING'}",
        "",
        "## File classification",
        "",
        "| Path | Status | Category | Risk | Confidence | Note |",
        "|------|--------|----------|------|------------|------|",
    ])
    for f in sorted(audit.files, key=lambda x: (x.risk.value, x.path)):
        conf = f.confidence.value if f.confidence else "—"
        lines.append(f"| `{f.path}` | {f.status} | {f.category.value} | {f.risk.value} | {conf} | {f.note} |")

    if not audit.files:
        lines.append("| _(clean)_ | | | | | |")

    eol_files = [
        f for f in audit.files
        if f.category in (FileCategory.CRLF_ONLY, FileCategory.UNKNOWN_LINE_ENDINGS)
        and f.verification
    ]
    if eol_files:
        lines.extend(["", "## Verification", ""])
        for f in eol_files:
            lines.append(
                f"### `{f.path}` — {f.category.value} "
                f"(Confidence: {f.confidence.value if f.confidence else '—'})"
            )
            if f.restore_recommended:
                lines.append("- Restore recommended: **yes** (simulation: index ≠ worktree)")
            else:
                lines.append("- Restore recommended: **no**")
            for step in f.verification:
                lines.append(f"- {step}")
            lines.append("")

    lines.extend(["", "## RECOMMENDED ACTION", ""])
    for i, action in enumerate(audit.recommended_actions, 1):
        lines.append(f"{i}. {action}")
    lines.append("")
    return "\n".join(lines)


def render_json(audit: RepoAuditState, *, transaction: WorkflowTransaction) -> str:
    payload: dict[str, Any] = {
        "schema": "repo_audit_report_v1",
        "workflow": transaction.to_dict(),
        "audit": audit.to_dict(),
    }
    return json.dumps(payload, indent=2)


def render_terminal(audit: RepoAuditState, *, transaction: WorkflowTransaction) -> str:
    lines = [
        "IFG Guardian — Repo Audit",
        "=" * 40,
        f"Workflow ID: {transaction.workflow_id}",
        f"Branch: {audit.branch}",
        f"HEAD: {short_sha(audit.head)}",
        f"Overall risk: {audit.overall_risk.value}",
        f"Classified files: {len(audit.files)}",
        f"Duration: {transaction.duration_ms} ms",
        "",
        "## RECOMMENDED ACTION",
        "",
    ]
    for i, action in enumerate(audit.recommended_actions, 1):
        lines.append(f"{i}. {action}")
    lines.extend(["", "=" * 40])
    status = exit_status_for_audit(audit)
    if status == 0:
        lines.append("Status: OK")
    elif status == 1:
        lines.append("Status: WARNING")
    else:
        lines.append("Status: ERROR")
    return "\n".join(lines)


def exit_status_for_audit(audit: RepoAuditState) -> int:
    if audit.overall_risk in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        return 1
    if audit.overall_risk == RiskLevel.MEDIUM or audit.dirty:
        return 1
    return 0
