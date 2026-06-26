"""Unit tests for IFG release plan workflow (Sprint 5A)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402
from ifg_guardian.core.workflow.context import WorkflowContext  # noqa: E402
from ifg_guardian.core.workflow.definition import WorkflowDefinition  # noqa: E402
from ifg_guardian.core.workflow.engine import ExecutionEngine  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.state import WorkflowState, WorkflowStateMachine  # noqa: E402
from ifg_guardian.core.workflow.transaction import WorkflowTransaction  # noqa: E402
from ifg_guardian.modules.ifg_release_plan import execute_ifg_release_plan, plan_from_context  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.build_detector import detect_build_decisions  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.execution_plan import build_execution_plan  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.models import (  # noqa: E402
    BuildDecision,
    DeploymentRisk,
    ReleasePlanState,
    RepositorySnapshot,
)
from ifg_guardian.plugins.ifg.release_plan.report import render_json, render_markdown, render_terminal  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.risk import aggregate_deployment_risk  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.stages import DependencyStage  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.artifacts import build_artifacts  # noqa: E402


def _run_git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _run_git(["init"], cwd=tmp_path)
    _run_git(["config", "user.email", "plan@test"], cwd=tmp_path)
    _run_git(["config", "user.name", "Plan Test"], cwd=tmp_path)
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=x\n", encoding="utf-8")
    (tmp_path / ".env.production.template").write_text("APP_ENV=production\n", encoding="utf-8")
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.prod.yml").write_text("services:\n  api:\n  worker:\n  db:\n", encoding="utf-8")
    _run_git(["add", "."], cwd=tmp_path)
    _run_git(["commit", "-m", "init"], cwd=tmp_path)
    return tmp_path


def _patch_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    import ifg_guardian.config as config_mod
    import ifg_guardian.core.git as git_mod
    import ifg_guardian.core.line_endings as le_mod
    import ifg_guardian.modules.frontend as frontend_mod

    monkeypatch.setattr(config_mod, "ROOT", root)
    monkeypatch.setattr(git_mod, "ROOT", root)
    monkeypatch.setattr(le_mod, "ROOT", root)
    monkeypatch.setattr(frontend_mod, "ROOT", root)


def _sample_doctor(*, blocked: bool = False) -> DoctorState:
    checks = [
        CheckResult("env.branch", "environment", "branch", CheckStatus.PASS, "on production"),
        CheckResult("env.git_status", "environment", "git status", CheckStatus.PASS, "clean"),
        CheckResult("env.ahead_behind", "environment", "ahead/behind", CheckStatus.PASS, "ahead=0, behind=0"),
        CheckResult("frontend.build_required", "frontend", "npm run build", CheckStatus.PASS, "ok"),
        CheckResult("frontend.dist_freshness", "frontend", "dist", CheckStatus.PASS, "ok"),
        CheckResult("backend.changes", "backend", "changes", CheckStatus.PASS, "none"),
        CheckResult("backend.build_required", "backend", "build", CheckStatus.PASS, "none"),
        CheckResult("alembic.pending", "alembic", "pending", CheckStatus.PASS, "schema at head"),
        CheckResult("alembic.current", "alembic", "current", CheckStatus.PASS, "abc123"),
    ]
    if blocked:
        checks.append(
            CheckResult("repo.deploy_blockers", "repository", "blockers", CheckStatus.CRITICAL, ".env")
        )
    return DoctorState(
        checks=checks,
        overall_status=OverallStatus.BLOCKED if blocked else OverallStatus.READY,
    )


class TestWorkflowRegistry:
    def test_release_plan_registered_with_dependency(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.release.plan")
            assert wf is not None
            assert wf.plugin == "ifg"
            assert wf.depends_on == ["ifg.doctor"]
            assert len(wf.stages) == 10
        finally:
            runtime.shutdown()


class TestDependencyExecution:
    def test_dependency_stage_requires_engine_context(self):
        wf = WorkflowDefinition(id="test", label="test", depends_on=["ifg.doctor"])
        tx = WorkflowTransaction(
            workflow_id="t",
            workflow_type="ifg.release.plan",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        ctx = WorkflowContext(
            root=Path("."),
            workflow=wf,
            transaction=tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(),
        )
        ctx.data["release_plan"] = ReleasePlanState()
        stage = DependencyStage()
        result = stage.interpret(ctx, None)
        assert result.status.value == "fail"


class TestBuildDetector:
    def test_detects_frontend_build_required(self):
        doctor = _sample_doctor()
        doctor.checks = [
            c if c.check_id != "frontend.build_required" else CheckResult(
                "frontend.build_required", "frontend", "npm run build", CheckStatus.FAIL, "dist stale"
            )
            for c in doctor.checks
        ]
        repo = RepositorySnapshot(frontend_changes=["frontend-react/src/App.jsx"])
        decisions = detect_build_decisions(doctor, repo)
        frontend = next(d for d in decisions if d.name == "Frontend Build")
        assert frontend.required is True
        assert frontend.confidence == "HIGH"

    def test_no_backend_build_when_clean(self):
        doctor = _sample_doctor()
        repo = RepositorySnapshot()
        decisions = detect_build_decisions(doctor, repo)
        backend = next(d for d in decisions if d.name == "Backend Build")
        assert backend.required is False


class TestArtifactGeneration:
    def test_builds_artifact_list(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)
        state = ReleasePlanState(repository=RepositorySnapshot(head_sha="abc", head_short="abc"))
        doctor = _sample_doctor()
        artifacts = build_artifacts(state, doctor)
        types = {a.artifact_type for a in artifacts}
        assert "Git SHA" in types
        assert "Docker image API" in types
        assert "Alembic revision" in types
        assert "Compose service" in types


class TestExecutionPlan:
    def test_full_plan_has_eight_steps(self):
        decisions = [
            BuildDecision("Frontend Build", True, "dist stale", "HIGH"),
            BuildDecision("Backend Build", True, "app changed", "HIGH"),
            BuildDecision("Worker Build", True, "worker", "HIGH"),
            BuildDecision("Compose Restart", True, "restart", "HIGH"),
            BuildDecision("Migration Required", True, "pending", "HIGH"),
            BuildDecision("Static Files", True, "static", "HIGH"),
        ]
        steps = build_execution_plan(decisions)
        assert len(steps) == 8
        assert steps[0].action == "git pull"
        assert steps[-1].action == "log verification"
        assert all(step.simulated for step in steps)

    def test_skip_optional_steps_when_not_required(self):
        decisions = detect_build_decisions(_sample_doctor(), RepositorySnapshot())
        steps = build_execution_plan(decisions)
        required = [s for s in steps if s.required]
        assert len(required) < 8


class TestRiskAggregation:
    def test_blocked_doctor_critical(self):
        doctor = _sample_doctor(blocked=True)
        state = ReleasePlanState(build_decisions=detect_build_decisions(doctor, RepositorySnapshot()))
        risk, rationale = aggregate_deployment_risk(doctor, state)
        assert risk == DeploymentRisk.CRITICAL
        assert rationale

    def test_ready_doctor_low_risk(self):
        doctor = _sample_doctor()
        state = ReleasePlanState(build_decisions=detect_build_decisions(doctor, RepositorySnapshot()))
        risk, _ = aggregate_deployment_risk(doctor, state)
        assert risk == DeploymentRisk.LOW


class TestReportRendering:
    def _sample_plan(self) -> tuple[ReleasePlanState, WorkflowTransaction]:
        state = ReleasePlanState(
            doctor_overall_status="READY",
            deployment_risk=DeploymentRisk.LOW,
            build_decisions=[BuildDecision("Frontend Build", False, "ok", "HIGH")],
            execution_plan=build_execution_plan([BuildDecision("Frontend Build", False, "ok", "HIGH")]),
            risk_rationale=["Doctor READY"],
        )
        tx = WorkflowTransaction(
            workflow_id="2026-05-22T120000Z_ifg_release_plan",
            workflow_type="ifg.release.plan",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
            dependencies={"ifg.doctor": {"workflow_id": "doc1", "outcome": "SUCCESS"}},
        )
        tx.mark_started()
        tx.mark_ended(state=WorkflowState.SUCCESS)
        tx.release_plan = state.to_dict()
        return state, tx

    def test_markdown_report(self):
        state, tx = self._sample_plan()
        md = render_markdown(state, transaction=tx)
        assert "# IFG Guardian — Release Plan" in md
        assert "ifg.doctor" in md

    def test_json_report(self):
        state, tx = self._sample_plan()
        data = json.loads(render_json(state, transaction=tx))
        assert data["schema"] == "ifg_release_plan_report_v1"

    def test_terminal_report(self):
        state, tx = self._sample_plan()
        text = render_terminal(state, transaction=tx)
        assert "Release Plan" in text
        assert "LOW RISK" in text


class TestReleasePlanWorkflow:
    def test_workflow_with_mocked_doctor_dependency(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)

        doctor_state = _sample_doctor()
        fake_doctor_tx = WorkflowTransaction(
            workflow_id="dep-doctor",
            workflow_type="ifg.doctor",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        fake_doctor_tx.doctor = doctor_state.to_dict()
        fake_doctor_tx.mark_started()
        fake_doctor_tx.mark_ended(state=WorkflowState.SUCCESS)

        fake_doctor_ctx = WorkflowContext(
            root=git_repo,
            workflow=WorkflowDefinition(id="ifg.doctor", label="doctor"),
            transaction=fake_doctor_tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(initial=WorkflowState.SUCCESS),
        )

        original_deps = ExecutionEngine._run_dependencies

        def fake_deps(self, ctx, workflow, *, mode, initial_data, _stack=None):
            if workflow.id != "ifg.release.plan":
                return original_deps(self, ctx, workflow, mode=mode, initial_data=initial_data, _stack=_stack)
            ctx.data["dependency_contexts"] = {"ifg.doctor": fake_doctor_ctx}
            ctx.transaction.dependencies["ifg.doctor"] = {
                "workflow_id": fake_doctor_tx.workflow_id,
                "workflow_type": "ifg.doctor",
                "outcome": "SUCCESS",
                "state": "SUCCESS",
            }

        with (
            patch.object(ExecutionEngine, "_run_dependencies", fake_deps),
            patch("ifg_guardian.plugins.ifg.release_plan.stages.git", side_effect=lambda *a, **k: {
                ("rev-parse", "HEAD"): "abc123def456",
                ("branch", "--show-current"): "production",
                ("rev-list", "--left-right", "--count", "HEAD...origin/production"): "0\t0",
            }.get(tuple(a), "")),
        ):
            ctx = execute_ifg_release_plan(output_format="none", root=git_repo)

        assert ctx.state_machine.state == WorkflowState.SUCCESS
        assert "ifg.doctor" in ctx.transaction.dependencies
        plan = plan_from_context(ctx)
        assert plan.deployment_risk == DeploymentRisk.LOW
        assert len(plan.execution_plan) == 8
        assert len(plan.build_decisions) == 6
