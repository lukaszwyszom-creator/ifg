from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.preflight.engine import PreflightEngine
from ifg_guardian.core.preflight.gate import SafetyGate
from ifg_guardian.core.preflight.report import render_precheck_markdown
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.deploy_run.service import get_deploy_state
from ifg_guardian.reporting import default_report_path, write_report


class PreflightStage(Stage):
    """Read-only preflight + Safety Gate before deploy execution."""

    id = "preflight"
    label = "Preflight and safety gate"
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        on_fail = "halt" if ctx.mode == ExecutionMode.LIVE else "halt"
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail=on_fail)

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        if ctx.data.get("skip_preflight"):
            return StageResult(status=StageStatus.PASS, message="preflight skipped")

        if ctx.mode in (ExecutionMode.DRY_RUN, ExecutionMode.PLAN):
            return StageResult(status=StageStatus.PASS, message="preflight skipped in dry-run/plan")

        state = get_deploy_state(ctx)
        if state.blockers and ctx.mode == ExecutionMode.LIVE:
            return StageResult(status=StageStatus.SKIP, message="preflight skipped due to blockers")

        engine = PreflightEngine()
        preflight_ctx = PreflightEngine.context_from_workflow(
            root=ctx.root,
            mode=ctx.mode,
            remote_host=ctx.data.get("remote_host"),
            remote_path=ctx.data.get("remote_path"),
            skip_remote=bool(ctx.data.get("skip_preflight_remote")),
            allow_dirty_build=bool(ctx.data.get("allow_dirty_build")),
        )
        report = engine.run(preflight_ctx)
        report.workflow_id = ctx.transaction.workflow_id

        decision = SafetyGate().evaluate(report)
        ctx.data["preflight_report"] = report
        ctx.data["deployment_decision"] = decision

        markdown = render_precheck_markdown(
            report,
            decision=decision,
            workflow_id=ctx.transaction.workflow_id,
        )
        ctx.data["precheck_report_markdown"] = markdown

        report_path = ctx.data.get("precheck_report_path")
        out = Path(report_path) if report_path else default_report_path("PRECHECK_REPORT")
        write_report(out, markdown)
        ctx.data["precheck_report_file"] = str(out)
        ctx.transaction.artifacts.append(
            ArtifactRecord(type="precheck_report", path=str(out))
        )

        ctx.transaction.recommended_actions.append(
            f"Preflight decision: {decision.status.value}"
        )
        for item in decision.blocking_items[:5]:
            ctx.transaction.recommended_actions.append(f"BLOCK: {item}")
        for item in decision.warnings[:3]:
            ctx.transaction.warnings.append(f"Preflight: {item}")

        if not decision.is_go:
            return StageResult(
                status=StageStatus.FAIL,
                message=f"Safety Gate NO_GO ({len(decision.blocking_items)} blocking item(s))",
            )

        warn_suffix = f", {len(decision.warnings)} warning(s)" if decision.warnings else ""
        return StageResult(
            status=StageStatus.PASS,
            message=f"Safety Gate GO{warn_suffix}",
        )
