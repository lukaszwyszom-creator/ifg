from __future__ import annotations

from ifg_guardian.core.reporting.adapters_precheck import build_precheck_report
from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.reporting.renderer import render_guardian_report
from ifg_guardian.core.preflight.models import DeploymentDecision, PreflightReport


def render_precheck_markdown(
    report: PreflightReport,
    *,
    decision: DeploymentDecision,
    workflow_id: str = "",
    debt=None,
) -> str:
    standard = build_precheck_report(
        report,
        decision=decision,
        workflow_id=workflow_id,
    )
    lines = render_guardian_report(standard)
    return finish_markdown(lines, debt=debt, state=report, transaction=None)
