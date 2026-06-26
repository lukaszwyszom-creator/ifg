from __future__ import annotations

from ifg_guardian.core.workflow.stage import StageStatus
from ifg_guardian.plugins.ifg.doctor.models import (
    CHECK_SEVERITY,
    CheckResult,
    CheckStatus,
    DoctorState,
    OverallStatus,
)


def worst_check_status(checks: list[CheckResult]) -> CheckStatus:
    if not checks:
        return CheckStatus.PASS
    return max(checks, key=lambda c: CHECK_SEVERITY[c.status]).status


def stage_status_from_checks(checks: list[CheckResult]) -> StageStatus:
    worst = worst_check_status(checks)
    if worst == CheckStatus.PASS:
        return StageStatus.PASS
    if worst == CheckStatus.WARN:
        return StageStatus.WARN
    return StageStatus.FAIL


def aggregate_overall_status(state: DoctorState) -> OverallStatus:
    if any(c.status == CheckStatus.CRITICAL for c in state.checks):
        return OverallStatus.BLOCKED
    if any(c.status == CheckStatus.FAIL for c in state.checks):
        return OverallStatus.BLOCKED
    if any(c.status == CheckStatus.WARN for c in state.checks):
        return OverallStatus.READY_WITH_WARNINGS
    return OverallStatus.READY


def exit_code_for_status(status: OverallStatus) -> int:
    if status == OverallStatus.READY:
        return 0
    return 1
