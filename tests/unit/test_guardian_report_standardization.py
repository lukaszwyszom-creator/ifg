"""Testy standaryzacji raportów Guardiana (GWO-GUARDIAN-0077)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402

_runtime = create_runtime()
_runtime.shutdown()

from ifg_guardian.core.preflight.models import (  # noqa: E402
    DeploymentDecision,
    DeploymentDecisionStatus,
    PreflightCheckResult,
    PreflightReport,
    PreflightStatus,
)
from ifg_guardian.core.preflight.report import render_precheck_markdown  # noqa: E402
from ifg_guardian.core.reporting.schema import IMPACT_COMPONENTS, STANDARD_BUILD_ACTIONS, STANDARD_SECTIONS  # noqa: E402
from ifg_guardian.core.reporting.status import (  # noqa: E402
    ConfidenceLevel,
    ReportLevel,
    STANDARD_CONFIDENCE,
    STANDARD_LEVELS,
    normalize_check_status,
    normalize_confidence,
    normalize_deployment_gate,
    normalize_overall_status,
    normalize_preflight_status,
    normalize_release_decision,
)
from ifg_guardian.core.workflow.state import WorkflowState  # noqa: E402
from ifg_guardian.core.workflow.transaction import WorkflowTransaction  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.report import render_json as doctor_json, render_markdown as doctor_md  # noqa: E402
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState  # noqa: E402
from ifg_guardian.plugins.ifg.deploy_run.report import render_markdown as deploy_md  # noqa: E402
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseDecisionStatus, ReleaseEvaluateState  # noqa: E402
from ifg_guardian.plugins.ifg.release_evaluate.report import render_markdown as evaluate_md  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.models import (  # noqa: E402
    BuildDecision,
    DeploymentRisk,
    ReleasePlanState,
    RepositorySnapshot,
)
from ifg_guardian.plugins.ifg.release_plan.report import render_markdown as plan_md  # noqa: E402


REQUIRED_SECTIONS = list(STANDARD_SECTIONS) + ["## Decyzje dla ChatGPT"]


from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402


def _tx(workflow_type: str) -> WorkflowTransaction:
    tx = WorkflowTransaction(
        workflow_id=f"2026-07-11T000000Z_{workflow_type.replace('.', '_')}",
        workflow_type=workflow_type,
        plugin="ifg",
        execution_mode=ExecutionMode.LIVE,
    )
    tx.mark_started()
    tx.mark_ended(state=WorkflowState.SUCCESS)
    return tx


def assert_standard_sections(md: str) -> None:
    for section in REQUIRED_SECTIONS:
        assert section in md, f"missing section: {section}"


class TestStatusEnums:
    def test_standard_levels_complete(self):
        assert ReportLevel.PASS.value in STANDARD_LEVELS
        assert ReportLevel.BLOCKED.value in STANDARD_LEVELS
        assert ReportLevel.READY_WITH_OVERRIDE.value in STANDARD_LEVELS

    def test_confidence_levels_complete(self):
        assert ConfidenceLevel.UNKNOWN.value in STANDARD_CONFIDENCE

    def test_normalize_check_status(self):
        assert normalize_check_status(CheckStatus.PASS) == ReportLevel.PASS
        assert normalize_check_status(CheckStatus.CRITICAL) == ReportLevel.BLOCKED

    def test_normalize_overall_status(self):
        assert normalize_overall_status(OverallStatus.READY_WITH_WARNINGS) == ReportLevel.READY_WITH_WARNINGS

    def test_normalize_preflight_status_warning_maps_to_warn(self):
        assert normalize_preflight_status(PreflightStatus.WARNING) == ReportLevel.WARN

    def test_normalize_deployment_gate(self):
        assert normalize_deployment_gate(DeploymentDecisionStatus.GO) == ReportLevel.READY
        assert normalize_deployment_gate(DeploymentDecisionStatus.NO_GO) == ReportLevel.BLOCKED

    def test_normalize_release_decision(self):
        assert normalize_release_decision(ReleaseDecisionStatus.READY_WITH_OVERRIDE) == ReportLevel.READY_WITH_OVERRIDE

    def test_normalize_confidence_never_empty(self):
        assert normalize_confidence(None) == ConfidenceLevel.UNKNOWN.value
        assert normalize_confidence("") == ConfidenceLevel.UNKNOWN.value
        assert normalize_confidence("HIGH") == ConfidenceLevel.HIGH.value


class TestDoctorReport:
    def _state(self) -> DoctorState:
        return DoctorState(
            overall_status=OverallStatus.READY_WITH_WARNINGS,
            checks=[
                CheckResult("alembic.current", "alembic", "local current", CheckStatus.WARN, "no DATABASE_URL", scope="local"),
                CheckResult("alembic.remote_revision", "alembic", "remote", CheckStatus.PASS, "abc123", scope="remote"),
            ],
            summary={"checks_total": 2},
        )

    def test_sections_complete(self):
        md = doctor_md(self._state(), transaction=_tx("ifg.doctor"))
        assert_standard_sections(md)

    def test_executive_summary_fields(self):
        md = doctor_md(self._state(), transaction=_tx("ifg.doctor"))
        assert "| **Status** | `READY_WITH_WARNINGS` |" in md
        assert "| **Workflow** |" in md

    def test_local_remote_separated(self):
        md = doctor_md(self._state(), transaction=_tx("ifg.doctor"))
        assert "### LOCAL" in md
        assert "### REMOTE" in md
        assert "alembic.current" in md
        assert "alembic.remote_revision" in md

    def test_json_has_standard_schema(self):
        payload = json.loads(doctor_json(self._state(), transaction=_tx("ifg.doctor")))
        assert payload["standard_schema"] == "guardian_standard_report_v1"


class TestReleasePlanReport:
    def _state(self) -> ReleasePlanState:
        return ReleasePlanState(
            doctor_overall_status="BLOCKED",
            deployment_risk=DeploymentRisk.HIGH,
            repository=RepositorySnapshot(
                backend_changes=["app/services/foo.py"],
                frontend_changes=["frontend-react/src/App.jsx"],
            ),
            build_decisions=[
                BuildDecision("Backend Build", True, "required", "HIGH", trigger_files=["app/services/foo.py"]),
                BuildDecision("Frontend Build", False, "none", "MEDIUM"),
            ],
            execution_plan=[],
            risk_rationale=["Doctor status: BLOCKED"],
        )

    def test_sections_complete(self):
        md = plan_md(self._state(), transaction=_tx("ifg.release.plan"))
        assert_standard_sections(md)

    def test_decision_matrix_and_triggers(self):
        md = plan_md(self._state(), transaction=_tx("ifg.release.plan"))
        assert "## Decision Matrix" in md
        assert "app/services/foo.py" in md
        assert "frontend-react/src/App.jsx" in md

    def test_impact_and_build_actions(self):
        md = plan_md(self._state(), transaction=_tx("ifg.release.plan"))
        for component in IMPACT_COMPONENTS:
            assert component in md
        for action in STANDARD_BUILD_ACTIONS:
            assert action in md


class TestReleaseEvaluateReport:
    def _state(self) -> ReleaseEvaluateState:
        return ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_WITH_WARNINGS,
            rationale="warnings only",
            warnings=["warn1"],
            required_actions=["verify config"],
            next_step="Run deploy plan",
            release_score=80,
            impact={"API Image": __import__("ifg_guardian.plugins.ifg.release_evaluate.models", fromlist=["ImpactLevel"]).ImpactLevel.HIGH},
        )

    def test_sections_complete(self):
        md = evaluate_md(self._state(), transaction=_tx("ifg.release.evaluate"))
        assert_standard_sections(md)

    def test_executive_summary_decision(self):
        md = evaluate_md(self._state(), transaction=_tx("ifg.release.evaluate"))
        assert "READY_WITH_WARNINGS" in md


class TestDeployRunReport:
    def _state(self) -> DeployRunState:
        return DeployRunState(
            dry_run=True,
            deployment_risk="HIGH",
            doctor_status="BLOCKED",
            release_decision="READY_WITH_WARNINGS",
            steps=[],
            blockers=["doctor blocked"],
        )

    def test_sections_complete(self):
        md = deploy_md(self._state(), transaction=_tx("ifg.deploy.run"))
        assert_standard_sections(md)

    def test_operator_actions_present(self):
        md = deploy_md(self._state(), transaction=_tx("ifg.deploy.run"))
        assert "doctor blocked" in md


class TestPrecheckReport:
    def test_sections_complete(self):
        report = PreflightReport(mode="DRY_RUN", duration_ms=12)
        report.add(PreflightCheckResult("x", "Git clean", PreflightStatus.PASS, "ok", duration_ms=3))
        decision = DeploymentDecision(status=DeploymentDecisionStatus.GO)
        md = render_precheck_markdown(report, decision=decision, workflow_id="wf-test")
        assert_standard_sections(md)
        assert "| **Decision** | `GO` |" in md
        assert "### LOCAL" in md


class TestReportConsistency:
    @pytest.mark.parametrize(
        "renderer,state,workflow",
        [
            (doctor_md, DoctorState(overall_status=OverallStatus.READY), "ifg.doctor"),
            (
                plan_md,
                ReleasePlanState(deployment_risk=DeploymentRisk.LOW),
                "ifg.release.plan",
            ),
            (
                evaluate_md,
                ReleaseEvaluateState(status=ReleaseDecisionStatus.READY_FOR_DEPLOY),
                "ifg.release.evaluate",
            ),
            (deploy_md, DeployRunState(), "ifg.deploy.run"),
        ],
    )
    def test_all_workflows_share_core_sections(self, renderer, state, workflow):
        md = renderer(state, transaction=_tx(workflow))
        for section in STANDARD_SECTIONS:
            assert section in md
