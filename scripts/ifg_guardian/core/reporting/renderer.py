"""Generator markdown ze wspólnego modelu raportów Guardiana."""
from __future__ import annotations

from ifg_guardian.core.reporting.schema import (
    STANDARD_BUILD_ACTIONS,
    STANDARD_SECTIONS,
    BuildActionRow,
    GuardianReport,
    ImpactRow,
)


def _render_bullets(items: list[str], *, empty: str = "Brak.") -> list[str]:
    if not items:
        return [empty]
    return [f"- {item}" for item in items]


def render_guardian_report(report: GuardianReport) -> list[str]:
    summary = report.executive_summary
    lines = [
        f"# {report.title}",
        "",
        f"**Generated:** {report.generated_at}  ",
        "",
        STANDARD_SECTIONS[0],
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Status** | `{summary.status}` |",
        f"| **Decision** | `{summary.decision}` |",
        f"| **Risk** | `{summary.risk}` |",
        f"| **Workflow** | `{summary.workflow}` |",
        f"| **Duration** | {summary.duration_ms} ms |",
    ]
    for key, value in summary.extras.items():
        lines.append(f"| **{key}** | `{value}` |")
    lines.append("")

    lines.extend([STANDARD_SECTIONS[1], ""])
    if report.decision_matrix:
        lines.extend([
            "| Component | Decision | Confidence | Reason | Trigger files | Impact |",
            "|-----------|----------|------------|--------|---------------|--------|",
        ])
        for row in report.decision_matrix:
            triggers = ", ".join(f"`{p}`" for p in row.trigger_files[:4])
            if len(row.trigger_files) > 4:
                triggers += f" (+{len(row.trigger_files) - 4})"
            reason = row.reason.replace("\n", " / ")
            lines.append(
                f"| {row.component} | {row.decision} | {row.confidence} | {reason} | {triggers or '—'} | {row.impact or '—'} |"
            )
    else:
        lines.append("Brak decyzji do wyświetlenia.")
    lines.append("")

    lines.extend([STANDARD_SECTIONS[2], ""])
    if report.trigger_files:
        for group in report.trigger_files:
            lines.append(f"**{group.category}**")
            lines.append("")
            if group.files:
                lines.extend(f"- `{path}`" for path in group.files)
            else:
                lines.append("- Brak.")
            lines.append("")
    else:
        lines.append("Brak.")
    lines.append("")

    lines.extend([STANDARD_SECTIONS[3], "", "### LOCAL", ""])
    if report.local_checks:
        lines.extend([
            "| Status | Check | Name | Message |",
            "|--------|-------|------|---------|",
        ])
        for check in report.local_checks:
            lines.append(
                f"| `{check.status}` | `{check.check_id}` | {check.name} | {check.message} |"
            )
    else:
        lines.append("Brak checków lokalnych.")
    lines.extend(["", "### REMOTE", ""])
    if report.remote_checks:
        lines.extend([
            "| Status | Check | Name | Message |",
            "|--------|-------|------|---------|",
        ])
        for check in report.remote_checks:
            lines.append(
                f"| `{check.status}` | `{check.check_id}` | {check.name} | {check.message} |"
            )
    else:
        lines.append("Brak checków zdalnych.")
    lines.append("")

    lines.extend([STANDARD_SECTIONS[4], ""])
    if report.impact:
        lines.extend([
            "| Component | Decision | Reason |",
            "|-----------|----------|--------|",
        ])
        for row in report.impact:
            lines.append(f"| {row.component} | {row.decision} | {row.reason} |")
    else:
        lines.append("Brak wpływu na komponenty.")
    lines.append("")

    lines.extend([STANDARD_SECTIONS[5], ""])
    action_map = {row.action: row for row in report.build_actions}
    lines.extend([
        "| Action | Decision | Reason | Command |",
        "|--------|----------|--------|---------|",
    ])
    for action_name in STANDARD_BUILD_ACTIONS:
        row = action_map.get(action_name)
        if row is None:
            lines.append(f"| {action_name} | NO | not applicable | — |")
            continue
        lines.append(
            f"| {row.action} | {row.decision} | {row.reason} | `{row.command or '—'}` |"
        )
    lines.append("")

    lines.extend([STANDARD_SECTIONS[6], ""])
    lines.extend(_render_bullets(report.operator_actions))
    lines.append("")

    for section in report.detail_sections:
        lines.extend(["", f"## {section.title}", ""])
        lines.extend(section.lines)
        lines.append("")

    lines.extend([STANDARD_SECTIONS[7], ""])
    lines.extend(_render_bullets(report.generated_reports))
    lines.append("")

    lines.extend([STANDARD_SECTIONS[8], ""])
    lines.extend(_render_bullets(report.generated_handoffs))
    lines.append("")

    return lines


def build_standard_impact_rows(mapping: dict[str, tuple[str, str]]) -> list[ImpactRow]:
    from ifg_guardian.core.reporting.schema import IMPACT_COMPONENTS

    rows: list[ImpactRow] = []
    for component in IMPACT_COMPONENTS:
        decision, reason = mapping.get(component, ("NO", "no impact detected"))
        rows.append(ImpactRow(component=component, decision=decision, reason=reason))
    return rows


def build_standard_build_actions(
    actions: dict[str, tuple[str, str, str]],
) -> list[BuildActionRow]:
    rows: list[BuildActionRow] = []
    for action_name in STANDARD_BUILD_ACTIONS:
        payload = actions.get(action_name)
        if payload is None:
            rows.append(BuildActionRow(action=action_name, decision="NO", reason="not applicable"))
            continue
        decision, reason, command = payload
        rows.append(
            BuildActionRow(
                action=action_name,
                decision=decision,
                reason=reason,
                command=command,
            )
        )
    return rows
