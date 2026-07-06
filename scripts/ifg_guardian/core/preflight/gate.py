from __future__ import annotations

from ifg_guardian.core.preflight.models import (
    DeploymentDecision,
    DeploymentDecisionStatus,
    PreflightReport,
    PreflightStatus,
)


class SafetyGate:
    """Evaluate preflight report and return GO / NO_GO decision."""

    def evaluate(self, report: PreflightReport) -> DeploymentDecision:
        blocking: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        for check in report.checks:
            label = f"{check.label}: {check.description}"
            if check.status == PreflightStatus.FAIL:
                blocking.append(label)
            elif check.status == PreflightStatus.WARNING:
                warnings.append(label)

        if blocking:
            recommendations.append("Resolve all FAIL items before LIVE deploy.")
            recommendations.append("Review PRECHECK_REPORT.md for details.")
            return DeploymentDecision(
                status=DeploymentDecisionStatus.NO_GO,
                blocking_items=blocking,
                warnings=warnings,
                recommendations=recommendations,
            )

        if warnings:
            recommendations.append("Review WARNING items — deploy may proceed with caution.")

        return DeploymentDecision(
            status=DeploymentDecisionStatus.GO,
            blocking_items=[],
            warnings=warnings,
            recommendations=recommendations,
        )
