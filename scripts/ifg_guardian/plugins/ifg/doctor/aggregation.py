from __future__ import annotations

from ifg_guardian.core.workflow.stage import StageStatus
from ifg_guardian.plugins.ifg.doctor.models import (
    CHECK_SEVERITY,
    CheckResult,
    CheckStatus,
    DoctorState,
    OverallStatus,
)

# Pre-build signals: pipeline always runs npm ci + build + artifact gate.
_BUILD_REQUIRED_CHECK_IDS = frozenset({
    "frontend.build_required",
    "frontend.dist_freshness",
})

_IMAGE_REBUILD_REQUIRED_IDS = frozenset({
    "backend.build_required",
})


def _is_build_required_message(check: CheckResult) -> bool:
    msg = (check.message or "").upper()
    return "BUILD_REQUIRED" in msg


def _is_image_rebuild_required_message(check: CheckResult) -> bool:
    msg = (check.message or "").upper()
    return "IMAGE_REBUILD_REQUIRED" in msg or "REQUIRE_REBUILD" in msg


def effective_check_status(check: CheckResult) -> CheckStatus:
    if check.status == CheckStatus.CRITICAL:
        return CheckStatus.CRITICAL
    if check.check_id in _BUILD_REQUIRED_CHECK_IDS and check.status == CheckStatus.FAIL:
        return CheckStatus.WARN
    if check.check_id in _IMAGE_REBUILD_REQUIRED_IDS and check.status == CheckStatus.FAIL:
        if _is_image_rebuild_required_message(check):
            return CheckStatus.WARN
    if check.status == CheckStatus.FAIL and (
        _is_build_required_message(check) or _is_image_rebuild_required_message(check)
    ):
        return CheckStatus.WARN
    return check.status


def worst_check_status(checks: list[CheckResult]) -> CheckStatus:
    if not checks:
        return CheckStatus.PASS
    return max(
        (effective_check_status(c) for c in checks),
        key=lambda status: CHECK_SEVERITY[status],
    )


def stage_status_from_checks(checks: list[CheckResult]) -> StageStatus:
    worst = worst_check_status(checks)
    if worst == CheckStatus.PASS:
        return StageStatus.PASS
    if worst == CheckStatus.WARN:
        return StageStatus.WARN
    return StageStatus.FAIL


def aggregate_overall_status(state: DoctorState) -> OverallStatus:
    if any(effective_check_status(c) == CheckStatus.CRITICAL for c in state.checks):
        return OverallStatus.BLOCKED
    if any(effective_check_status(c) == CheckStatus.FAIL for c in state.checks):
        return OverallStatus.BLOCKED
    if any(effective_check_status(c) == CheckStatus.WARN for c in state.checks):
        return OverallStatus.READY_WITH_WARNINGS
    return OverallStatus.READY


def exit_code_for_status(status: OverallStatus) -> int:
    if status == OverallStatus.READY:
        return 0
    return 1
