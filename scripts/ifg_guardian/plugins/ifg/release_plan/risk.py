from __future__ import annotations

from ifg_guardian.plugins.ifg.doctor.models import CheckStatus, DoctorState, OverallStatus
from ifg_guardian.plugins.ifg.release_plan.models import BuildDecision, DeploymentRisk, ReleasePlanState


def aggregate_deployment_risk(
    doctor: DoctorState,
    state: ReleasePlanState,
) -> tuple[DeploymentRisk, list[str]]:
    rationale: list[str] = []

    if doctor.overall_status == OverallStatus.BLOCKED:
        rationale.append(f"Doctor status: {doctor.overall_status.value}")
        return DeploymentRisk.CRITICAL, rationale

    critical_checks = [c for c in doctor.checks if c.status == CheckStatus.CRITICAL]
    fail_checks = [c for c in doctor.checks if c.status == CheckStatus.FAIL]

    if critical_checks:
        for check in critical_checks[:3]:
            rationale.append(f"CRITICAL: {check.name} — {check.message}")
        return DeploymentRisk.CRITICAL, rationale

    required_builds = [d for d in state.build_decisions if d.required]
    if fail_checks:
        for check in fail_checks[:3]:
            rationale.append(f"FAIL: {check.name} — {check.message}")
        if len(fail_checks) > 2 or state.repository.dirty:
            return DeploymentRisk.HIGH, rationale
        return DeploymentRisk.MEDIUM, rationale

    if doctor.overall_status == OverallStatus.READY_WITH_WARNINGS:
        rationale.append(f"Doctor status: {doctor.overall_status.value}")
        if state.repository.ahead > 0 or state.repository.behind > 0:
            rationale.append(
                f"Repo out of sync: ahead={state.repository.ahead}, behind={state.repository.behind}"
            )
        if len(required_builds) >= 3:
            return DeploymentRisk.MEDIUM, rationale
        return DeploymentRisk.MEDIUM, rationale

    if len(required_builds) >= 4:
        rationale.append(f"{len(required_builds)} build/restart steps required")
        return DeploymentRisk.MEDIUM, rationale

    if state.repository.dirty:
        rationale.append("Working tree dirty — deploy should use committed state only")
        return DeploymentRisk.MEDIUM, rationale

    rationale.append("Doctor READY and minimal planned changes")
    return DeploymentRisk.LOW, rationale


def exit_code_for_risk(risk: DeploymentRisk) -> int:
    if risk == DeploymentRisk.LOW:
        return 0
    return 1
