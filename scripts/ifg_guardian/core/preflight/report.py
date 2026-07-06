from __future__ import annotations

from datetime import datetime

from ifg_guardian.core.time_compat import UTC

from ifg_guardian.core.preflight.models import DeploymentDecision, PreflightReport, PreflightStatus


def render_precheck_markdown(
    report: PreflightReport,
    *,
    decision: DeploymentDecision,
    workflow_id: str = "",
) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# Guardian Preflight — PRECHECK_REPORT",
        "",
        f"**Generated:** {ts}  ",
        f"**Workflow:** `{workflow_id or report.workflow_id or 'n/a'}`  ",
        f"**Mode:** `{report.mode}`  ",
        f"**Decision:** **{decision.status.value}**  ",
        f"**Duration:** {report.duration_ms} ms  ",
        "",
        "## Summary",
        "",
        f"| PASS | WARNING | FAIL |",
        f"|------|---------|------|",
        f"| {report.passed} | {report.warnings} | {report.failures} |",
        "",
    ]

    if decision.blocking_items:
        lines.extend(["## Blocking items (NO_GO)", ""])
        for item in decision.blocking_items:
            lines.append(f"- {item}")
        lines.append("")

    if decision.warnings:
        lines.extend(["## Warnings", ""])
        for item in decision.warnings:
            lines.append(f"- {item}")
        lines.append("")

    if decision.recommendations:
        lines.extend(["## Recommendations", ""])
        for item in decision.recommendations:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend([
        "## Check results",
        "",
        "| Status | Check | Description | Duration |",
        "|--------|-------|-------------|----------|",
    ])

    for check in report.checks:
        icon = check.status.value
        lines.append(
            f"| {icon} | {check.label} | {check.description} | {check.duration_ms} ms |"
        )

    lines.extend([
        "",
        "## Details",
        "",
    ])

    for check in report.checks:
        if not check.details:
            continue
        lines.append(f"### {check.check_id} ({check.status.value})")
        lines.append("")
        for key, value in check.details.items():
            lines.append(f"- **{key}:** `{value}`")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Read-only preflight — no environment mutations.*")
    return "\n".join(lines)
