"""Guardian Platform workflow engine tests."""
from __future__ import annotations

from pathlib import Path

from guardian_platform.core.registry.workflows import WorkflowDefinition, WorkflowRegistry
from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.engine import ExecutionEngine
from guardian_platform.core.workflow.intents import FsExistsIntent, GitRevParseIntent, GitStatusIntent, NoOpIntent
from guardian_platform.core.workflow.results import IntentResult, StageExecutionResults
from guardian_platform.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from guardian_platform.core.workflow.state import WorkflowState
from guardian_platform.core.workflow.executors import IntentExecutor
from guardian_platform.core.workflow.workflows.ping import build_core_ping_workflow


class _PassStage(Stage):
    id = "pass"
    label = "pass"
    mutating = False

    def build_plan(self, ctx):
        return StagePlan(intents=[NoOpIntent(reason="pass")])

    def interpret(self, ctx, results):
        return StageResult(status=StageStatus.PASS, message="ok")


class TestWorkflowRegistry:
    def test_register_and_get(self):
        reg = WorkflowRegistry()
        wf = WorkflowDefinition(id="test.wf", label="Test", stages=[_PassStage()])
        reg.register(wf)
        assert reg.get("test.wf") is wf

    def test_list_ids_sorted(self):
        reg = WorkflowRegistry()
        reg.register(WorkflowDefinition(id="b.wf", label="B", stages=[]))
        reg.register(WorkflowDefinition(id="a.wf", label="A", stages=[]))
        assert reg.list_ids() == ["a.wf", "b.wf"]


class TestWorkflowEngine:
    def test_run_core_ping_in_git_repo(self, git_repo):
        engine = ExecutionEngine(root=git_repo)
        wf = build_core_ping_workflow()
        ctx = engine.run(wf, mode=ExecutionMode.LIVE)
        assert ctx.state_machine.state == WorkflowState.SUCCESS
        assert ctx.transaction.outcome == "SUCCESS"

    def test_workflow_records_stages(self, git_repo):
        engine = ExecutionEngine(root=git_repo)
        ctx = engine.run(build_core_ping_workflow())
        stage_ids = [s.id for s in ctx.transaction.stages]
        assert "init" in stage_ids
        assert "summary" in stage_ids

    def test_workflow_summary_data(self, git_repo):
        engine = ExecutionEngine(root=git_repo)
        ctx = engine.run(build_core_ping_workflow())
        assert "summary" in ctx.data
        assert ctx.data["summary"]["workflow_type"] == "core.ping"

    def test_dry_run_mode(self, git_repo):
        engine = ExecutionEngine(root=git_repo)
        ctx = engine.run(build_core_ping_workflow(), mode=ExecutionMode.DRY_RUN)
        assert ctx.mode == ExecutionMode.DRY_RUN

    def test_single_stage_workflow(self, git_repo):
        engine = ExecutionEngine(root=git_repo)
        wf = WorkflowDefinition(id="one", label="One", stages=[_PassStage()])
        ctx = engine.run(wf)
        assert ctx.state_machine.state == WorkflowState.SUCCESS


class TestIntentExecutor:
    def test_noop_intent(self, git_repo):
        ex = IntentExecutor(root=git_repo)
        result = ex.execute(NoOpIntent(reason="test"), ExecutionMode.LIVE)
        assert result.ok is True

    def test_fs_exists_intent(self, git_repo):
        ex = IntentExecutor(root=git_repo)
        result = ex.execute(FsExistsIntent(path="README.md"), ExecutionMode.LIVE)
        assert result.ok is True
        assert result.data["exists"] is True

    def test_git_rev_parse(self, git_repo):
        ex = IntentExecutor(root=git_repo)
        result = ex.execute(GitRevParseIntent(ref="HEAD"), ExecutionMode.LIVE)
        assert result.ok is True
        assert len(result.data.get("sha", "")) == 40

    def test_git_status_clean(self, git_repo):
        ex = IntentExecutor(root=git_repo)
        result = ex.execute(GitStatusIntent(porcelain=True), ExecutionMode.LIVE)
        assert result.ok is True
        assert result.data["dirty"] is False

    def test_stage_execution_results_all_ok(self):
        intent = NoOpIntent(reason="x")
        results = StageExecutionResults(
            stage_id="s",
            intent_results=[IntentResult(intent=intent, ok=True)],
        )
        assert results.all_ok is True

    def test_stage_execution_results_first_data(self):
        intent = GitRevParseIntent(ref="HEAD")
        results = StageExecutionResults(
            stage_id="s",
            intent_results=[
                IntentResult(intent=intent, ok=True, data={"sha": "abc", "ref": "HEAD"}),
            ],
        )
        assert results.first_data("git_rev_parse")["sha"] == "abc"
