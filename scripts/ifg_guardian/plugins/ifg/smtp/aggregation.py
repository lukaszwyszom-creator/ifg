"""Agregacja statusu workflow SMTP."""
from __future__ import annotations

from ifg_guardian.plugins.ifg.smtp.models import SmtpOverallStatus, SmtpStageStatus, SmtpState


def aggregate_smtp_status(state: SmtpState) -> SmtpOverallStatus:
    from ifg_guardian.plugins.ifg.smtp.models import SmtpEnvironment

    if state.environment == SmtpEnvironment.REMOTE and not state.ssh_ok:
        return SmtpOverallStatus.BLOCKED
    if state.config_has_fail():
        return SmtpOverallStatus.BLOCKED
    if state.connectivity_has_fail():
        return SmtpOverallStatus.BLOCKED
    if state.test_result and state.test_result.status == SmtpStageStatus.FAIL:
        return SmtpOverallStatus.BLOCKED

    has_warn = any(c.status == SmtpStageStatus.WARN for c in state.config_checks)
    has_warn = has_warn or any(c.status == SmtpStageStatus.WARN for c in state.connectivity_checks)
    if has_warn:
        return SmtpOverallStatus.READY_WITH_WARNINGS
    return SmtpOverallStatus.READY


def exit_code_for_smtp(state: SmtpState) -> int:
    if state.overall_status == SmtpOverallStatus.READY:
        return 0
    return 1


def build_operator_actions(state: SmtpState) -> list[str]:
    from ifg_guardian.plugins.ifg.smtp.models import SmtpEnvironment

    actions: list[str] = []
    if state.environment == SmtpEnvironment.REMOTE and not state.ssh_ok:
        actions.append("Fix DS723+ SSH connectivity — cannot read production .env.production.")
    for check in state.config_checks:
        if check.status == SmtpStageStatus.FAIL:
            actions.append(f"Fix config `{check.key}`: {check.message}")
    for check in state.connectivity_checks:
        if check.status == SmtpStageStatus.FAIL:
            actions.append(f"Fix connectivity `{check.stage}`: {check.message}")
    if state.test_result and state.test_result.status == SmtpStageStatus.FAIL:
        actions.append(f"Test mail failed: {state.test_result.message}")
    if not actions:
        if state.mode == "test" and state.test_result and state.test_result.sent:
            actions.append("Verify test mail delivery in recipient inbox.")
        else:
            actions.append("SMTP configuration looks ready — no action required.")
    return actions
