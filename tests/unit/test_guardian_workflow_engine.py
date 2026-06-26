"""Unit tests for Guardian Workflow Engine (Sprint 1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.engine import ExecutionEngine
from ifg_guardian.core.workflow.executors import IntentExecutor
from ifg_guardian.core.workflow.intents import LocalExecIntent, NoOpIntent
from ifg_guardian.core.plugins.bootstrap import create_runtime
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.state import InvalidStateTransition, WorkflowState, WorkflowStateMachine
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.core.workflows.ping import CORE_PING_WORKFLOW, InitStage, NoOpStage, SummaryStage


def _resolve_workflow(workflow_id: str):
    runtime = create_runtime()
    try:
        return runtime.resolve_workflow(workflow_id)
    finally:
        runtime.shutdown()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "wf@test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Workflow Test"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


class TestWorkflowStateMachine:
    def test_happy_path_lifecycle(self):
        sm = WorkflowStateMachine()
        assert sm.state == WorkflowState.UNKNOWN

        sm.transition(WorkflowState.READY)
        sm.transition(WorkflowState.RUNNING)
        sm.transition(WorkflowState.VERIFYING)
        sm.transition(WorkflowState.SUCCESS)
        assert sm.state.is_terminal

    def test_abort_from_ready(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowState.READY)
        sm.transition(WorkflowState.ABORTED)
        assert sm.state == WorkflowState.ABORTED

    def test_fail_from_running(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowState.READY)
        sm.transition(WorkflowState.RUNNING)
        sm.transition(WorkflowState.FAILED)
        assert sm.state == WorkflowState.FAILED

    def test_invalid_transition_raises(self):
        sm = WorkflowStateMachine()
        with pytest.raises(InvalidStateTransition):
            sm.transition(WorkflowState.SUCCESS)

    def test_can_transition_helper(self):
        sm = WorkflowStateMachine()
        assert sm.can_transition(WorkflowState.READY)
        assert not sm.can_transition(WorkflowState.RUNNING)


class TestWorkflowTransaction:
    def test_to_dict_schema_v1(self):
        tx = WorkflowTransaction(
            workflow_id="2026-06-26T120000Z_core_ping",
            workflow_type="core.ping",
            plugin=None,
            execution_mode=ExecutionMode.LIVE,
        )
        tx.mark_started()
        tx.mark_ended(state=WorkflowState.SUCCESS)
        data = tx.to_dict()

        assert data["schema"] == "workflow_transaction_v1"
        assert data["workflow_id"] == "2026-06-26T120000Z_core_ping"
        assert data["workflow_type"] == "core.ping"
        assert data["execution_mode"] == "LIVE"
        assert data["lifecycle"]["state"] == "SUCCESS"
        assert data["outcome"] == "SUCCESS"
        assert "git" in data
        assert "docker" in data
        assert "alembic" in data
        assert "frontend" in data

    def test_roundtrip_from_dict(self):
        original = WorkflowTransaction(
            workflow_id="id1",
            workflow_type="core.ping",
            plugin="core",
            execution_mode=ExecutionMode.DRY_RUN,
            commit_before="abc123",
            warnings=["test warning"],
        )
        original.mark_started()
        original.mark_ended(state=WorkflowState.SUCCESS)

        restored = WorkflowTransaction.from_dict(original.to_dict())
        assert restored.workflow_id == "id1"
        assert restored.execution_mode == ExecutionMode.DRY_RUN
        assert restored.commit_before == "abc123"
        assert restored.warnings == ["test warning"]
        assert restored.outcome == "SUCCESS"


class TestDryRun:
    def test_local_exec_simulated_in_dry_run(self, tmp_path: Path):
        executor = IntentExecutor(root=tmp_path)
        intent = LocalExecIntent(command=[sys.executable, "-c", "print('mutate')"])

        result = executor.execute(intent, ExecutionMode.DRY_RUN)

        assert result.ok
        assert result.simulated
        assert "[dry-run] would:" in result.output

    def test_local_exec_runs_in_live(self, tmp_path: Path):
        executor = IntentExecutor(root=tmp_path)
        intent = LocalExecIntent(command=[sys.executable, "-c", "print('live')"])

        result = executor.execute(intent, ExecutionMode.LIVE)

        assert result.ok
        assert not result.simulated
        assert "live" in result.output

    def test_plan_mode_simulates_mutations(self, tmp_path: Path):
        executor = IntentExecutor(root=tmp_path)
        intent = LocalExecIntent(command=[sys.executable, "-c", "print('plan')"])

        result = executor.execute(intent, ExecutionMode.PLAN)

        assert result.ok
        assert result.simulated


class TestExecutionEngine:
    def test_core_ping_success(self, git_repo: Path):
        engine = ExecutionEngine(root=git_repo)
        ctx = engine.run(CORE_PING_WORKFLOW, mode=ExecutionMode.LIVE)

        assert ctx.state_machine.state == WorkflowState.SUCCESS
        assert ctx.transaction.outcome == "SUCCESS"
        assert len(ctx.transaction.stages) == 3
        assert ctx.transaction.stages[0].id == "init"
        assert ctx.transaction.stages[1].id == "noop"
        assert ctx.transaction.stages[2].id == "summary"

    def test_core_ping_dry_run_same_pipeline(self, git_repo: Path):
        live = ExecutionEngine(root=git_repo).run(CORE_PING_WORKFLOW, mode=ExecutionMode.LIVE)
        dry = ExecutionEngine(root=git_repo).run(CORE_PING_WORKFLOW, mode=ExecutionMode.DRY_RUN)

        assert live.state_machine.state == WorkflowState.SUCCESS
        assert dry.state_machine.state == WorkflowState.SUCCESS
        assert [s.id for s in live.transaction.stages] == [s.id for s in dry.transaction.stages]
        assert dry.transaction.execution_mode == ExecutionMode.DRY_RUN

    def test_failed_stage_halts_pipeline(self, tmp_path: Path):
        class FailStage(Stage):
            id = "fail"
            label = "Fail"
            mutating = False

            def build_plan(self, ctx: WorkflowContext) -> StagePlan:
                return StagePlan(intents=[NoOpIntent()])

            def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
                return StageResult(status=StageStatus.FAIL, message="boom")

        workflow = WorkflowDefinition(
            id="test.fail",
            label="fail test",
            stages=[FailStage(), NoOpStage()],
        )
        engine = ExecutionEngine(root=tmp_path)
        ctx = engine.run(workflow, mode=ExecutionMode.LIVE)

        assert ctx.state_machine.state == WorkflowState.FAILED
        assert len(ctx.transaction.stages) == 1
        assert ctx.transaction.stages[0].id == "fail"

    def test_persists_transaction_file(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        from ifg_guardian.core.workflow import engine as engine_mod

        guardian_dir = git_repo / ".guardian" / "workflows"
        monkeypatch.setattr(engine_mod, "ROOT", git_repo)
        monkeypatch.setattr(engine_mod, "GUARDIAN_DIR", git_repo / ".guardian")
        monkeypatch.setattr(engine_mod, "WORKFLOWS_DIR", guardian_dir)

        ctx = ExecutionEngine(root=git_repo).run(CORE_PING_WORKFLOW)
        tx_file = guardian_dir / ctx.transaction.workflow_id / "transaction.json"

        assert tx_file.is_file()
        data = json.loads(tx_file.read_text(encoding="utf-8"))
        assert data["schema"] == "workflow_transaction_v1"
        assert data["workflow_type"] == "core.ping"


class TestNoOpWorkflow:
    def test_registry_contains_core_ping(self):
        wf = _resolve_workflow("core.ping")
        assert wf is not None
        assert wf.id == "core.ping"
        assert len(wf.stages) == 3

    def test_stages_build_and_interpret(self, git_repo: Path):
        tx = WorkflowTransaction(
            workflow_id="test",
            workflow_type="core.ping",
            plugin=None,
            execution_mode=ExecutionMode.LIVE,
        )
        ctx = WorkflowContext(
            root=git_repo,
            workflow=CORE_PING_WORKFLOW,
            transaction=tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(),
        )
        executor = IntentExecutor(root=git_repo)

        for stage in [InitStage(), NoOpStage(), SummaryStage()]:
            plan = stage.build_plan(ctx)
            results = StageExecutionResults(
                stage_id=stage.id,
                intent_results=[executor.execute(i, ctx.mode) for i in plan.intents],
            )
            result = stage.interpret(ctx, results)
            ctx.stage_results.append(result)
            assert result.passed
