"""Unit tests for IFG deploy run workflow (Sprint 5B)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402
from ifg_guardian.core.workflow.context import WorkflowContext  # noqa: E402
from ifg_guardian.core.workflow.definition import WorkflowDefinition  # noqa: E402
from ifg_guardian.core.workflow.engine import ExecutionEngine  # noqa: E402
from ifg_guardian.core.workflow.executors import IntentExecutor, SSHExecutor  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.state import WorkflowState, WorkflowStateMachine  # noqa: E402
from ifg_guardian.core.workflow.transaction import WorkflowTransaction  # noqa: E402
from ifg_guardian.modules.ifg_deploy_run import (  # noqa: E402
    deploy_from_context,
    execute_ifg_deploy_run,
    run_ifg_deploy_run,
)
from ifg_guardian.plugins.ifg.deploy_run.models import DeployStepStatus  # noqa: E402
from ifg_guardian.plugins.ifg.deploy_run.pipeline import build_deploy_pipeline, compose_blocked_by_step_failure, detect_blockers  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.execution_plan import build_execution_plan  # noqa: E402
from ifg_guardian.plugins.ifg.release_evaluate.models import (  # noqa: E402
    ReleaseDecisionStatus,
    ReleaseEvaluateState,
)
from ifg_guardian.plugins.ifg.release_plan.models import (  # noqa: E402
    BuildDecision,
    DeploymentRisk,
    ReleasePlanState,
)
from ifg_guardian.plugins.ifg.deploy_run.report import (  # noqa: E402
    render_json,
    render_markdown,
    render_terminal,
)


def _sample_release_plan(*, critical: bool = False) -> ReleasePlanState:
    decisions = [
        BuildDecision("Frontend Build", True, "dist stale", "HIGH"),
        BuildDecision("Backend Build", True, "app changed", "HIGH"),
        BuildDecision("Worker Build", True, "worker", "HIGH"),
        BuildDecision("Compose Restart", True, "restart needed", "HIGH"),
        BuildDecision("Migration Required", False, "at head", "HIGH"),
        BuildDecision("Static Files", True, "sync dist", "HIGH"),
    ]
    plan = ReleasePlanState(
        doctor_overall_status="BLOCKED" if critical else "READY",
        doctor_workflow_id="doc-wf-1",
        deployment_risk=DeploymentRisk.CRITICAL if critical else DeploymentRisk.MEDIUM,
        build_decisions=decisions,
        risk_rationale=["test rationale"] if not critical else ["CRITICAL: blocked"],
    )
    plan.execution_plan = build_execution_plan(decisions)
    return plan


def _sample_release_evaluate(
    *,
    decision: ReleaseDecisionStatus = ReleaseDecisionStatus.READY_WITH_WARNINGS,
) -> ReleaseEvaluateState:
    return ReleaseEvaluateState(
        status=decision,
        required_actions=["backup", "rebuild"],
        warnings=["warn"],
    )


class TestWorkflowRegistry:
    def test_deploy_run_registered(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.deploy.run")
            assert wf is not None
            assert wf.plugin == "ifg"
            assert wf.mutating is True
            assert wf.depends_on == ["ifg.release.plan", "ifg.release.evaluate"]
            assert len(wf.stages) == 9
        finally:
            runtime.shutdown()


class TestPipelineBuilder:
    def test_pipeline_aligns_with_release_plan(self):
        plan = _sample_release_plan()
        pipeline = build_deploy_pipeline(plan)
        actions = [s.action for s in pipeline]
        assert actions == [
            "git pull",
            "frontend build",
            "artifact verify local",
            "dist sync",
            "artifact verify",
            "docker build",
            "alembic upgrade",
            "compose up",
            "health check",
            "log verification",
        ]
        required = [s.action for s in pipeline if s.required and not s.skipped]
        assert "git pull" in required
        assert "frontend build" in required
        assert "artifact verify local" in required
        assert "dist sync" in required
        assert "artifact verify" in required
        assert "docker build" in required
        assert "alembic upgrade" not in required

    def test_frontend_artifacts_mandatory_even_when_doctor_skips(self):
        decisions = [
            BuildDecision("Frontend Build", False, "skipped by doctor", "LOW"),
            BuildDecision("Backend Build", False, "none", "LOW"),
            BuildDecision("Worker Build", False, "none", "LOW"),
            BuildDecision("Compose Restart", False, "none", "LOW"),
            BuildDecision("Migration Required", False, "at head", "LOW"),
            BuildDecision("Static Files", False, "unchanged", "LOW"),
        ]
        plan = ReleasePlanState(build_decisions=decisions)
        plan.execution_plan = build_execution_plan(decisions)
        pipeline = build_deploy_pipeline(plan)
        for action in ("frontend build", "artifact verify local", "dist sync", "artifact verify"):
            step = next(s for s in pipeline if s.action == action)
            assert step.required and not step.skipped

    def test_compose_blocked_on_gate_failure(self):
        assert compose_blocked_by_step_failure("artifact verify")
        assert compose_blocked_by_step_failure("frontend build")
        assert not compose_blocked_by_step_failure("health check")

    def test_blockers_on_critical_risk(self):
        plan = _sample_release_plan(critical=True)
        blockers = detect_blockers(plan)
        assert any("CRITICAL" in b or "BLOCKED" in b for b in blockers)


class TestDryRunSafety:
    def test_intent_executor_simulates_without_subprocess(self):
        from ifg_guardian.core.workflow.executors import IntentExecutor
        from ifg_guardian.core.workflow.intents import LocalExecIntent

        called = {"count": 0}
        original = subprocess.run

        def spy_run(*args, **kwargs):
            called["count"] += 1
            return original(*args, **kwargs)

        executor = IntentExecutor(root=Path("."))
        intent = LocalExecIntent(command=["git", "pull"], mutating=True)
        with patch("ifg_guardian.core.workflow.executors.local_executor.subprocess.run", spy_run):
            result = executor.execute(intent, ExecutionMode.DRY_RUN)
        assert called["count"] == 0
        assert result.ok
        assert result.simulated

    def test_refuses_live_deploy_without_yes(self, capsys):
        code = run_ifg_deploy_run(dry_run=False, assume_yes=False)
        assert code == 2
        assert "--yes" in capsys.readouterr().out


class TestReportRendering:
    def _sample_deploy(self) -> tuple:
        from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState, DeployStep

        state = DeployRunState(
            release_plan_workflow_id="plan-1",
            deployment_risk="MEDIUM",
            doctor_status="READY",
            dry_run=True,
            steps=[
                DeployStep(1, "git pull", "sync", "required", True, command="git pull"),
            ],
            summary={"steps_simulated": 1},
        )
        tx = WorkflowTransaction(
            workflow_id="deploy-1",
            workflow_type="ifg.deploy.run",
            plugin="ifg",
            execution_mode=ExecutionMode.DRY_RUN,
            dependencies={
                "ifg.release.plan": {"outcome": "SUCCESS"},
                "ifg.release.evaluate": {"outcome": "SUCCESS"},
            },
        )
        tx.mark_started()
        tx.mark_ended(state=WorkflowState.SUCCESS)
        tx.deploy_run = state.to_dict()
        return state, tx

    def test_markdown_report(self):
        state, tx = self._sample_deploy()
        md = render_markdown(state, transaction=tx)
        assert "Deploy Run" in md
        assert "ifg.release.plan" in md

    def test_json_report(self):
        state, tx = self._sample_deploy()
        data = json.loads(render_json(state, transaction=tx))
        assert data["schema"] == "ifg_deploy_run_report_v1"

    def test_terminal_report(self):
        state, tx = self._sample_deploy()
        text = render_terminal(state, transaction=tx)
        assert "DRY-RUN" in text


class TestDeployWorkflowIntegration:
    def test_dry_run_workflow_with_mocked_release_plan(self, tmp_path: Path):
        plan = _sample_release_plan()
        plan_tx = WorkflowTransaction(
            workflow_id="plan-wf",
            workflow_type="ifg.release.plan",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        plan_tx.release_plan = plan.to_dict()
        plan_tx.mark_started()
        plan_tx.mark_ended(state=WorkflowState.SUCCESS)

        plan_ctx = WorkflowContext(
            root=tmp_path,
            workflow=WorkflowDefinition(id="ifg.release.plan", label="plan"),
            transaction=plan_tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(initial=WorkflowState.SUCCESS),
        )
        evaluate = _sample_release_evaluate()
        eval_tx = WorkflowTransaction(
            workflow_id="eval-wf",
            workflow_type="ifg.release.evaluate",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        eval_tx.release_evaluate = evaluate.to_dict()
        eval_tx.mark_started()
        eval_tx.mark_ended(state=WorkflowState.SUCCESS)
        eval_ctx = WorkflowContext(
            root=tmp_path,
            workflow=WorkflowDefinition(id="ifg.release.evaluate", label="evaluate"),
            transaction=eval_tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(initial=WorkflowState.SUCCESS),
        )

        original_deps = ExecutionEngine._run_dependencies

        def fake_deps(self, ctx, workflow, *, mode, initial_data, _stack=None):
            if workflow.id != "ifg.deploy.run":
                return original_deps(self, ctx, workflow, mode=mode, initial_data=initial_data, _stack=_stack)
            ctx.data["dependency_contexts"] = {
                "ifg.release.plan": plan_ctx,
                "ifg.release.evaluate": eval_ctx,
            }
            ctx.transaction.dependencies["ifg.release.plan"] = {
                "workflow_id": "plan-wf",
                "workflow_type": "ifg.release.plan",
                "outcome": "SUCCESS",
                "state": "SUCCESS",
            }
            ctx.transaction.dependencies["ifg.release.evaluate"] = {
                "workflow_id": "eval-wf",
                "workflow_type": "ifg.release.evaluate",
                "outcome": "SUCCESS",
                "state": "SUCCESS",
            }

        subprocess_calls: list = []

        def block_mutations(*args, **kwargs):
            subprocess_calls.append(args)
            raise AssertionError("mutating command must not execute in dry-run")

        with (
            patch.object(ExecutionEngine, "_run_dependencies", fake_deps),
            patch("ifg_guardian.core.workflow.executors.local_executor.subprocess.run", block_mutations),
            patch("ifg_guardian.core.workflow.executors.ssh_executor.subprocess.run", block_mutations),
        ):
            ctx = execute_ifg_deploy_run(dry_run=True, output_format="none", root=tmp_path)

        assert ctx.state_machine.state == WorkflowState.SUCCESS
        assert "ifg.release.plan" in ctx.transaction.dependencies
        assert "ifg.release.evaluate" in ctx.transaction.dependencies
        assert len(subprocess_calls) == 0

        deploy = deploy_from_context(ctx)
        assert deploy.dry_run is True
        assert len(deploy.steps) == 10
        simulated = [s for s in deploy.steps if s.status == DeployStepStatus.SIMULATED]
        assert len(simulated) >= 6


class TestLiveDeploy:
    def _mock_deps(self, plan: ReleasePlanState):
        is_blocked = plan.deployment_risk == DeploymentRisk.CRITICAL
        plan_tx = WorkflowTransaction(
            workflow_id="plan-wf",
            workflow_type="ifg.release.plan",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        plan_tx.release_plan = plan.to_dict()
        plan_tx.mark_started()
        plan_tx.mark_ended(state=WorkflowState.SUCCESS)

        plan_ctx = WorkflowContext(
            root=Path("."),
            workflow=WorkflowDefinition(id="ifg.release.plan", label="plan"),
            transaction=plan_tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(initial=WorkflowState.SUCCESS),
        )
        evaluate = _sample_release_evaluate(
            decision=ReleaseDecisionStatus.READY_WITH_WARNINGS
            if not is_blocked
            else ReleaseDecisionStatus.PRODUCTION_BLOCKED
        )
        eval_tx = WorkflowTransaction(
            workflow_id="eval-wf",
            workflow_type="ifg.release.evaluate",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        eval_tx.release_evaluate = evaluate.to_dict()
        eval_tx.mark_started()
        eval_tx.mark_ended(state=WorkflowState.SUCCESS)
        eval_ctx = WorkflowContext(
            root=Path("."),
            workflow=WorkflowDefinition(id="ifg.release.evaluate", label="evaluate"),
            transaction=eval_tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(initial=WorkflowState.SUCCESS),
        )

        original_deps = ExecutionEngine._run_dependencies

        def fake_deps(self, ctx, workflow, *, mode, initial_data, _stack=None):
            if workflow.id != "ifg.deploy.run":
                return original_deps(self, ctx, workflow, mode=mode, initial_data=initial_data, _stack=_stack)
            ctx.data["dependency_contexts"] = {
                "ifg.release.plan": plan_ctx,
                "ifg.release.evaluate": eval_ctx,
            }
            ctx.transaction.dependencies["ifg.release.plan"] = {
                "workflow_id": "plan-wf",
                "workflow_type": "ifg.release.plan",
                "outcome": "SUCCESS",
                "state": "SUCCESS",
            }
            ctx.transaction.dependencies["ifg.release.evaluate"] = {
                "workflow_id": "eval-wf",
                "workflow_type": "ifg.release.evaluate",
                "outcome": "SUCCESS",
                "state": "SUCCESS",
            }

        return fake_deps

    def test_live_blocked_when_doctor_blocked(self, tmp_path: Path):
        plan = _sample_release_plan(critical=True)
        with patch.object(ExecutionEngine, "_run_dependencies", self._mock_deps(plan)):
            ctx = execute_ifg_deploy_run(
                dry_run=False,
                assume_yes=True,
                skip_preflight=True,
                output_format="none",
                root=tmp_path,
            )

        assert ctx.state_machine.state == WorkflowState.FAILED
        deploy = deploy_from_context(ctx)
        assert deploy.blockers
        assert deploy.release_decision == ReleaseDecisionStatus.PRODUCTION_BLOCKED.value
        assert deploy.dry_run is False

    def test_live_executes_with_mocked_executors(self, tmp_path: Path):
        plan = _sample_release_plan()
        fake_result = MagicMock(ok=True, output="ok", simulated=False, error="", data={})

        def git_side_effect(*args: str) -> str:
            if len(args) >= 2 and args[0] == "status" and args[1] == "--porcelain":
                return ""
            if args[:2] == ("rev-parse", "--short") or args[:1] == ("rev-parse",):
                return "abc1234"
            return ""

        with (
            patch.object(ExecutionEngine, "_run_dependencies", self._mock_deps(plan)),
            patch("ifg_guardian.plugins.ifg.deploy_run.stages.git", side_effect=git_side_effect),
            patch.object(SSHExecutor, "capture_rollback_snapshot", return_value={"images_before": "img:1", "alembic_before": "rev1"}),
            patch.object(IntentExecutor, "execute", return_value=fake_result),
        ):
            ctx = execute_ifg_deploy_run(
                dry_run=False,
                assume_yes=True,
                skip_preflight=True,
                output_format="none",
                root=tmp_path,
            )

        assert ctx.state_machine.state == WorkflowState.SUCCESS
        deploy = deploy_from_context(ctx)
        assert deploy.dry_run is False
        assert deploy.release_decision == ReleaseDecisionStatus.READY_WITH_WARNINGS.value
        executed = [s for s in deploy.steps if s.status == DeployStepStatus.EXECUTED]
        assert len(executed) >= 5
        assert deploy.rollback_point.commit_before == "abc1234"
