from __future__ import annotations

from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.intents import (
    FsExistsIntent,
    GitRevParseIntent,
    GitStatusIntent,
    NoOpIntent,
)
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import (
    BuildReason,
    Stage,
    StagePlan,
    StageResult,
    StageStatus,
)


class InitStage(Stage):
    id = "init"
    label = "Initialize workflow context"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(
            intents=[
                GitRevParseIntent(ref="HEAD"),
                GitStatusIntent(porcelain=True),
                FsExistsIntent(path="README.md"),
            ],
            reasons=[
                BuildReason(
                    decision="init_snapshot",
                    because=["HEAD", "git status", "README.md"],
                    source_stage=self.id,
                )
            ],
        )

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        if not results.all_ok:
            return StageResult(status=StageStatus.FAIL, message="init checks failed")

        head = results.first_data("git_rev_parse")
        if head:
            ctx.transaction.commit_before = head.get("sha", "")
            ctx.transaction.commit_after = head.get("sha", "")

        status = results.first_data("git_status")
        if status and status.get("dirty"):
            ctx.transaction.warnings.append("working tree is dirty")

        readme = results.first_data("fs_exists")
        if readme and not readme.get("exists"):
            return StageResult(status=StageStatus.WARN, message="README.md not found")

        ctx.data["init_ok"] = True
        return StageResult(status=StageStatus.PASS, message="init complete")


class NoOpStage(Stage):
    id = "noop"
    label = "No-op stage"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(
            intents=[NoOpIntent(reason="core.ping heartbeat")],
            reasons=[
                BuildReason(
                    decision="noop",
                    because=["core.ping"],
                    source_stage=self.id,
                )
            ],
        )

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        if not results.all_ok:
            return StageResult(status=StageStatus.FAIL, message="noop failed")
        return StageResult(status=StageStatus.PASS, message="noop ok")


class SummaryStage(Stage):
    id = "summary"
    label = "Summarize workflow"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason="summary")])

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        passed = sum(1 for r in ctx.stage_results if r.status == StageStatus.PASS)
        ctx.data["summary"] = {
            "stages_passed": passed,
            "stages_total": len(ctx.stage_results),
            "workflow_type": ctx.workflow_type,
        }
        return StageResult(
            status=StageStatus.PASS,
            message=f"summary: {passed} stage(s) passed before summary",
            data=ctx.data["summary"],
        )


CORE_PING_WORKFLOW = WorkflowDefinition(
    id="core.ping",
    label="Core ping workflow",
    plugin="core",
    mutating=False,
    stages=[InitStage(), NoOpStage(), SummaryStage()],
)
