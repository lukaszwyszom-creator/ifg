from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from guardian_platform.core.reporting.debt import finish_markdown
from guardian_platform.profiles.ifg.repo_cleanup.policy import CleanupPlan


class ReportExistsError(Exception):
    """Raised when writing would overwrite an existing report without --force."""


def _reports_dir(root: Path) -> Path:
    return root / "docs" / "reports"


def render_plan_markdown(plan: CleanupPlan, *, root: Path, debt=None) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# IFG Repository Cleanup Plan",
        "",
        f"**Generated:** {now}  ",
        f"**Mode:** {'DRY-RUN' if plan.dry_run else 'LIVE'}  ",
        f"**Phase filter:** {plan.phase if plan.phase is not None else 'ALL'}  ",
        f"**Operations:** {plan.operation_count}  ",
        "",
        "## Summary",
        "",
        f"- Candidates evaluated: {len(plan.candidates)}",
        f"- Operations planned: {plan.operation_count}",
        "",
    ]

    by_phase: dict[int, list] = {}
    for op in plan.operations:
        by_phase.setdefault(op.phase, []).append(op)

    for phase in sorted(by_phase):
        lines.extend([f"## Phase {phase}", ""])
        for op in by_phase[phase]:
            target = f" → `{op.target}`" if op.target else ""
            lines.append(f"- **{op.action.value}** `{op.source}`{target}")
            lines.append(f"  - Confidence: {op.confidence}%")
            lines.append(f"  - Rationale: {op.rationale}")
            lines.append(f"  - Impact: {op.impact or 'n/a'}")
            lines.append(f"  - Rollback: {op.rollback or 'n/a'}")
        lines.append("")

    if plan.rollback_steps:
        lines.extend(["## Rollback plan", ""])
        for step in plan.rollback_steps[:50]:
            lines.append(f"- {step}")
        if len(plan.rollback_steps) > 50:
            lines.append(f"- … and {len(plan.rollback_steps) - 50} more")
        lines.append("")

    sample = [c for c in plan.candidates if c.path.startswith("docs/")][:15]
    if sample:
        lines.extend(["## Advisor samples (documentation)", ""])
        for c in sample:
            lines.extend([
                f"### `{c.path}`",
                "",
                f"- Graph: {c.graph_status} / {c.graph_recommendation} / {c.graph_risk}",
                f"- History: {c.history.value} — {c.history_note}",
                f"- Policy: {c.policy_rule}",
                f"- **Decision:** {c.decision.value} ({c.confidence}%)",
                "",
            ])

    return finish_markdown(lines, debt=debt, state=plan, transaction=None)


def _resolve_output_path(root: Path, output_path: Path) -> Path:
    return output_path if output_path.is_absolute() else (root / output_path)


def write_plan_report(
    root: Path,
    plan: CleanupPlan,
    *,
    output_path: Path,
    force: bool = False,
) -> Path:
    out = _resolve_output_path(root, output_path)
    if out.exists() and not force:
        try:
            rel = out.relative_to(root)
        except ValueError:
            rel = out
        raise ReportExistsError(
            f"Report already exists: {rel} (use --force to overwrite)"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    content = render_plan_markdown(plan, root=root)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(out)
    return out


def write_execution_report(root: Path, plan: CleanupPlan, executed: list[str]) -> Path:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    out = _reports_dir(root) / "repository_cleanup_execution.md"
    lines = [
        "# IFG Repository Cleanup Execution",
        "",
        f"**Executed:** {now}  ",
        f"**Phase:** {plan.phase if plan.phase is not None else 'ALL'}  ",
        f"**Operations run:** {len(executed)}  ",
        "",
        "## Executed",
        "",
    ]
    for item in executed:
        lines.append(f"- {item}")
    lines.extend(["", "## Rollback plan", ""])
    for step in plan.rollback_steps[:50]:
        lines.append(f"- {step}")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def render_terminal_summary(plan: CleanupPlan) -> str:
    lines = [
        "IFG Repository Cleanup Advisor",
        "=" * 40,
        f"Mode: {'DRY-RUN' if plan.dry_run else 'LIVE'}",
        f"Phase: {plan.phase if plan.phase is not None else 'ALL'}",
        f"Operations: {plan.operation_count}",
        "",
    ]
    for op in plan.operations[:30]:
        target = f" -> {op.target}" if op.target else ""
        lines.append(f"[phase {op.phase}] {op.action.value}: {op.source}{target} ({op.confidence}%)")
    if plan.operation_count > 30:
        lines.append(f"... and {plan.operation_count - 30} more")
    lines.extend(["", f"Rollback steps: {len(plan.rollback_steps)}", ""])
    return "\n".join(lines)
