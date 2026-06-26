from __future__ import annotations

from pathlib import Path

from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.context import WorkflowContext
from guardian_platform.core.workflow.intents import NoOpIntent
from guardian_platform.core.workflow.results import StageExecutionResults
from guardian_platform.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from guardian_platform.profiles.ifg.config.defaults import DEFAULT_REMOTE_PATH, TARGET_BRANCH, resolve_remote_host
from guardian_platform.profiles.ifg.deploy.models import DeployRunState, DeployStep, RollbackPoint, StepStatus
from guardian_platform.profiles.ifg.deploy.pipeline import build_deploy_pipeline
from guardian_platform.profiles.ifg.deploy.service import get_deploy_state
from guardian_platform.profiles.ifg.infra.exec import run_local
from guardian_platform.profiles.ifg.infra.git import git, porcelain_is_dirty, short_sha
from guardian_platform.profiles.ifg.lib.deploy_reporting import deploy_report_path, write_report
from guardian_platform.profiles.ifg.deploy.report import render_json, render_markdown


class _DeployStage(Stage):
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")


class InitStage(_DeployStage):
    id = "init"
    label = "Initialize deploy run"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        dry_run = ctx.mode != ExecutionMode.LIVE
        assume_yes = bool(ctx.data.get("assume_yes"))
        if not dry_run and not assume_yes:
            return StageResult(status=StageStatus.FAIL, message="LIVE deploy requires --yes")

        state = DeployRunState(
            dry_run=dry_run,
            assume_yes=assume_yes,
            remote_host=resolve_remote_host(ctx.data.get("remote_host")),
            remote_path=str(ctx.data.get("remote_path") or DEFAULT_REMOTE_PATH),
            rollback_available=True,
        )
        ctx.data["deploy_run"] = state
        ctx.transaction.profile_data["rollback_available"] = True
        return StageResult(status=StageStatus.PASS, message="initialized")


class RepositoryStage(_DeployStage):
    id = "repository"
    label = "Repository validation"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        try:
            branch = git("branch", "--show-current")
            head = git("rev-parse", "HEAD")
            state.rollback_point.commit_before = short_sha(head)
        except RuntimeError as exc:
            state.blockers.append(str(exc))
            return StageResult(status=StageStatus.FAIL, message=str(exc))

        if branch != TARGET_BRANCH:
            msg = f"expected branch {TARGET_BRANCH}, on {branch}"
            state.blockers.append(msg)
            return StageResult(status=StageStatus.FAIL, message=msg)

        ctx.transaction.branch = branch
        ctx.transaction.commit_before = state.rollback_point.commit_before
        return StageResult(status=StageStatus.PASS, message=f"on {branch} @ {state.rollback_point.commit_before}")


class GitValidationStage(_DeployStage):
    id = "git_validation"
    label = "Git validation"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        try:
            porcelain = git("status", "--porcelain")
        except RuntimeError as exc:
            return StageResult(status=StageStatus.FAIL, message=str(exc))

        if porcelain_is_dirty(porcelain):
            state.warnings.append("working tree dirty — review before LIVE deploy")
            if ctx.mode == ExecutionMode.LIVE:
                state.blockers.append("dirty working tree blocks LIVE deploy")
                return StageResult(status=StageStatus.FAIL, message="dirty working tree")

        return StageResult(status=StageStatus.PASS, message="git validation ok")


class ExecutionStage(_DeployStage):
    id = "execution"
    label = "Execute deploy pipeline"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        if state.blockers:
            return StageResult(status=StageStatus.SKIP, message="skipped due to blockers")

        dry_run = state.dry_run
        pipeline = build_deploy_pipeline(
            remote_host=state.remote_host,
            remote_path=state.remote_path,
        )
        state.steps = []
        failed = False

        for order, (action, command, mutating) in enumerate(pipeline, start=1):
            step = DeployStep(order=order, action=action, command=command, required=True)
            result = run_local(command, dry_run=dry_run, mutating=mutating)
            step.output = result.output
            step.error = result.error

            if result.simulated:
                step.status = StepStatus.SIMULATED
            elif result.ok:
                step.status = StepStatus.EXECUTED
                if action == "health verification":
                    state.health = result.output
                if action == "smoke tests":
                    state.smoke_ok = result.simulated or (
                        "openapi" in result.output.lower() or result.output.strip().startswith("{")
                    )
            else:
                step.status = StepStatus.FAILED
                failed = True
                if action in ("health verification", "smoke tests"):
                    state.halted = True
                    state.halt_reason = f"{action} failed: {result.error or result.output}"
                    state.steps.append(step)
                    break

            state.steps.append(step)

        if failed and not state.halted:
            state.halt_reason = "pipeline step failed"
            state.halted = True

        if state.halted:
            return StageResult(status=StageStatus.FAIL, message=state.halt_reason)

        label = "simulated" if dry_run else "executed"
        return StageResult(status=StageStatus.PASS, message=f"pipeline {label}")


class DeployReportStage(_DeployStage):
    id = "deploy_report"
    label = "Deploy report"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        state.summary = {
            "mode": "DRY-RUN" if state.dry_run else "LIVE",
            "steps": len(state.steps),
            "rollback_available": state.rollback_available,
            "smoke_ok": state.smoke_ok,
            "halted": state.halted,
        }
        ctx.transaction.profile_data["deploy_run"] = state.to_dict()

        report_path = ctx.data.get("report_path")
        out = Path(report_path) if report_path else deploy_report_path()
        markdown = render_markdown(state, transaction=ctx.transaction)
        write_report(out, markdown)
        ctx.data["report_file"] = str(out)
        ctx.data["report_json"] = render_json(state, transaction=ctx.transaction)

        return StageResult(status=StageStatus.PASS, message=f"report: {out.name}")
