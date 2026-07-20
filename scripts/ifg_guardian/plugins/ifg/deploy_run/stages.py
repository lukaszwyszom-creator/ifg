from __future__ import annotations

from pathlib import Path
from time import perf_counter

from ifg_guardian.config import DEFAULT_REMOTE_PATH, TARGET_BRANCH
from ifg_guardian.core.git import git, porcelain_is_dirty
from ifg_guardian.core.preflight.checks import DIRTY_TREE_BLOCK_MESSAGE, DIRTY_TREE_OVERRIDE_WARNING
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.intents import LocalExecIntent, NoOpIntent
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import BuildReason, Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState, DeployStepStatus, RollbackPoint
from ifg_guardian.plugins.ifg.deploy_run.pipeline import build_deploy_pipeline, compose_blocked_by_step_failure
from ifg_guardian.plugins.ifg.deploy_run.report import render_json, render_markdown
from ifg_guardian.plugins.ifg.deploy_run.service import (
    get_deploy_state,
    get_release_evaluate_dependency,
    get_release_plan_dependency,
)
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseDecisionStatus
from ifg_guardian.reporting import default_report_path, write_report


class _DeployStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")


class InitStage(_DeployStage):
    id = "init"
    label = "Initialize deploy run"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        dry_run = ctx.mode in (ExecutionMode.DRY_RUN, ExecutionMode.PLAN)
        assume_yes = bool(ctx.data.get("assume_yes"))
        ctx.data["deploy_run"] = DeployRunState(dry_run=dry_run)
        ctx.data.setdefault("output_format", "terminal")
        ctx.data.setdefault("remote_path", DEFAULT_REMOTE_PATH)

        if not dry_run and not assume_yes:
            return StageResult(
                status=StageStatus.FAIL,
                message="LIVE deploy requires --yes",
            )

        state = get_deploy_state(ctx)
        allow_dirty = bool(ctx.data.get("allow_dirty_build"))
        state.allow_dirty_build_override = allow_dirty

        if not dry_run:
            try:
                porcelain = git("status", "--porcelain")
            except RuntimeError as exc:
                return StageResult(status=StageStatus.FAIL, message=f"cannot read git status: {exc}")

            if porcelain_is_dirty(porcelain):
                if allow_dirty:
                    state.warnings.append(DIRTY_TREE_OVERRIDE_WARNING)
                else:
                    state.blockers = [DIRTY_TREE_BLOCK_MESSAGE]
                    return StageResult(
                        status=StageStatus.FAIL,
                        message=DIRTY_TREE_BLOCK_MESSAGE,
                    )

        if not dry_run:
            try:
                local_commit = git("rev-parse", "--short", "HEAD")
            except RuntimeError as exc:
                return StageResult(status=StageStatus.FAIL, message=f"cannot read local commit: {exc}")

            rollback = RollbackPoint(commit_before=local_commit)
            deploy_ctx = ctx.data.get("deploy_executor_context")
            if isinstance(deploy_ctx, DeployExecutorContext):
                from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor

                ssh = SSHExecutor(root=ctx.root, deploy_context=deploy_ctx)
                snapshot = ssh.capture_rollback_snapshot()
                rollback = RollbackPoint(
                    commit_before=local_commit,
                    images_before=snapshot.get("images_before", ""),
                    alembic_before=snapshot.get("alembic_before", ""),
                )
            state.rollback_point = rollback
            ctx.transaction.commit_before = rollback.commit_before
            ctx.transaction.image_before = rollback.images_before
            ctx.transaction.alembic_before = rollback.alembic_before
            ctx.transaction.branch = TARGET_BRANCH
            ctx.transaction.host_remote = str(ctx.data.get("remote_host") or "")
            ctx.transaction.remote_path = str(ctx.data.get("remote_path", DEFAULT_REMOTE_PATH))
            ctx.transaction.rollback_possible = True

        message = "deploy dry-run initialized" if dry_run else "deploy LIVE initialized"
        return StageResult(status=StageStatus.PASS, message=message)


class DependencyStage(_DeployStage):
    id = "dependency"
    label = "Verify workflow dependencies"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        deps = ctx.data.get("dependency_contexts", {})
        expected = list(ctx.workflow.depends_on)
        missing = [dep for dep in expected if dep not in deps]
        if missing:
            return StageResult(status=StageStatus.FAIL, message=f"missing dependencies: {', '.join(missing)}")

        reasons: list[BuildReason] = []
        for dep_id in expected:
            dep_ctx = deps[dep_id]
            reasons.append(
                BuildReason(
                    decision="dependency_resolved",
                    because=[dep_id, dep_ctx.transaction.outcome],
                    source_stage=self.id,
                )
            )
            if dep_ctx.state_machine.state != WorkflowState.SUCCESS:
                return StageResult(
                    status=StageStatus.FAIL,
                    message=f"dependency {dep_id} failed: {dep_ctx.transaction.outcome}",
                    reasons=reasons,
                )

        return StageResult(
            status=StageStatus.PASS,
            message=f"{len(expected)} dependency(ies) satisfied",
            reasons=reasons,
        )


class ReleasePlanStage(_DeployStage):
    id = "release_plan"
    label = "Load release plan from dependency"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        plan = get_release_plan_dependency(ctx)
        dep_ctx = ctx.data["dependency_contexts"]["ifg.release.plan"]

        state.release_plan_workflow_id = dep_ctx.transaction.workflow_id
        state.deployment_risk = plan.deployment_risk.value
        state.doctor_status = plan.doctor_overall_status
        ctx.data["release_plan_state"] = plan

        return StageResult(
            status=StageStatus.PASS,
            message=f"release plan loaded (risk={plan.deployment_risk.value})",
        )


class ReleaseEvaluateStage(_DeployStage):
    id = "release_evaluate"
    label = "Load release evaluate decision"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        evaluate = get_release_evaluate_dependency(ctx)
        dep_ctx = ctx.data["dependency_contexts"]["ifg.release.evaluate"]
        state.release_evaluate_workflow_id = dep_ctx.transaction.workflow_id
        state.release_decision = evaluate.status.value
        ctx.data["release_evaluate_state"] = evaluate
        if evaluate.status == ReleaseDecisionStatus.READY_WITH_OVERRIDE:
            state.allow_dirty_build_override = bool(ctx.data.get("allow_dirty_build"))
        return StageResult(
            status=StageStatus.PASS,
            message=f"release evaluate loaded (decision={evaluate.status.value})",
        )


class BlockerStage(_DeployStage):
    id = "blocker"
    label = "Detect deployment blockers"

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        on_fail = "halt" if ctx.mode == ExecutionMode.LIVE else "continue"
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail=on_fail)

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        evaluate = ctx.data["release_evaluate_state"]
        # Single source of deployment decision: release evaluate / policy engine.
        if evaluate.status == ReleaseDecisionStatus.PRODUCTION_BLOCKED:
            state.blockers = [
                f"Release decision is {evaluate.status.value}",
                *[f"Policy blocker: {b}" for b in evaluate.blockers[:5]],
            ]
        elif evaluate.status == ReleaseDecisionStatus.STAGING_ONLY:
            state.blockers = [
                "Release decision requires STAGING_ONLY before deploy run",
            ]
        elif evaluate.status == ReleaseDecisionStatus.READY_WITH_OVERRIDE:
            if not bool(ctx.data.get("allow_dirty_build")):
                state.blockers = [
                    "Release decision requires explicit --allow-dirty-build for dirty working tree",
                ]
            else:
                state.allow_dirty_build_override = True
                state.warnings.append(DIRTY_TREE_OVERRIDE_WARNING)
        else:
            state.blockers = []

        # Hard gate: image-context vs deployed image (never SKIP on ambiguity).
        from ifg_guardian.plugins.ifg.deploy_decision.image_gate_resolve import resolve_image_rebuild_gate
        from ifg_guardian.plugins.ifg.deploy_decision.image_rebuild_gate import ImageRebuildDecision

        gate = resolve_image_rebuild_gate(
            remote_host=str(ctx.data.get("remote_host") or None),
            remote_path=str(ctx.data.get("remote_path") or None),
            defer_remote_verify=False,
        )
        ctx.data["image_rebuild_gate"] = gate
        if gate.decision == ImageRebuildDecision.FAIL:
            state.blockers.append(f"Image rebuild gate FAIL: {gate.reason}")
        elif gate.decision == ImageRebuildDecision.REQUIRE_REBUILD:
            state.warnings.append(f"Image rebuild gate: {gate.reason}")

        if evaluate.required_actions:
            state.warnings.extend(
                [f"ACTION_REQUIRED: {item}" for item in evaluate.required_actions]
            )

        if state.blockers:
            status = StageStatus.FAIL if ctx.mode == ExecutionMode.LIVE else StageStatus.WARN
            return StageResult(
                status=status,
                message=f"{len(state.blockers)} blocker(s)",
                reasons=[
                    BuildReason(decision="blocker", because=[b], source_stage=self.id)
                    for b in state.blockers
                ],
            )
        return StageResult(status=StageStatus.PASS, message="no blockers")


class BuildPipelineStage(_DeployStage):
    id = "build_pipeline"
    label = "Build deployment execution pipeline"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        if state.blockers and ctx.mode == ExecutionMode.LIVE:
            return StageResult(status=StageStatus.SKIP, message="pipeline skipped due to blockers")

        plan = ctx.data["release_plan_state"]
        remote_path = str(ctx.data.get("remote_path", DEFAULT_REMOTE_PATH))
        gate = ctx.data.get("image_rebuild_gate")
        force_rebuild = False
        rebuild_reason = None
        if gate is not None:
            from ifg_guardian.plugins.ifg.deploy_decision.image_rebuild_gate import ImageRebuildDecision

            if gate.decision == ImageRebuildDecision.REQUIRE_REBUILD:
                force_rebuild = True
                rebuild_reason = gate.reason
            elif gate.decision == ImageRebuildDecision.FAIL:
                # Should already be in blockers; keep pipeline empty of SKIP ambiguity
                force_rebuild = True
                rebuild_reason = gate.reason
        state.steps = build_deploy_pipeline(
            plan,
            remote_path=remote_path,
            force_docker_rebuild=force_rebuild,
            docker_rebuild_reason=rebuild_reason,
        )
        required = sum(1 for s in state.steps if s.required and not s.skipped)
        return StageResult(
            status=StageStatus.PASS,
            message=f"{len(state.steps)} steps ({required} required)",
        )


class SimulateExecutionStage(Stage):
    id = "simulate_execution"
    label = "Simulate deployment steps"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        state = get_deploy_state(ctx)
        if state.blockers and ctx.mode == ExecutionMode.LIVE:
            return StagePlan(intents=[], on_fail="halt")

        intents = []
        for step in state.steps:
            if step.skipped or not step.required:
                continue
            if step.command:
                meta = None
                if step.action == "image verify":
                    docker_step = next((s for s in state.steps if s.action == "docker build"), None)
                    rebuild_required = bool(
                        docker_step and docker_step.required and not docker_step.skipped
                    )
                    meta = {"rebuild_was_required": rebuild_required}
                intents.append(
                    LocalExecIntent(
                        command=["/bin/sh", "-c", step.command],
                        mutating=True,
                        meta=meta,
                    )
                )
        on_fail = "halt" if ctx.mode == ExecutionMode.LIVE else "continue"
        return StagePlan(intents=intents, on_fail=on_fail)

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        if state.blockers and ctx.mode == ExecutionMode.LIVE:
            return StageResult(status=StageStatus.SKIP, message="execution skipped due to blockers")

        dry_run = ctx.mode != ExecutionMode.LIVE
        simulated_count = 0
        executed_count = 0
        failed_count = 0
        intent_index = 0
        block_compose = False
        state.failed_step = {}

        for step in state.steps:
            if step.skipped or not step.required:
                step.status = DeployStepStatus.SKIPPED
                continue

            if block_compose and step.action == "compose up":
                step.status = DeployStepStatus.BLOCKED
                step.error = "blocked — Artifact Verification Gate or prior step failed"
                state.warnings.append("compose up blocked by artifact gate")
                continue

            if step.command and intent_index < len(results.intent_results):
                started = perf_counter()
                result = results.intent_results[intent_index]
                intent_index += 1
                step.duration_ms = int((perf_counter() - started) * 1000)
                step.output = result.output
                step.error = result.error
                step.exit_code = result.data.get("exit_code")
                step.stdout = str(result.data.get("stdout", ""))
                step.stderr = str(result.data.get("stderr", ""))

                if result.simulated or dry_run:
                    step.status = DeployStepStatus.SIMULATED
                    step.simulated = True
                    simulated_count += 1
                elif result.ok:
                    step.status = DeployStepStatus.EXECUTED
                    executed_count += 1
                    if step.action == "health check":
                        state.health = result.output
                    if step.action == "compose up" and result.data.get("containers"):
                        state.containers = str(result.data.get("containers", ""))
                else:
                    step.status = DeployStepStatus.FAILED
                    failed_count += 1
                    step.failure_reason = result.error or "step command failed"
                    state.warnings.append(f"{step.action} failed: {result.error or result.output}")
                    if not state.failed_step:
                        state.failed_step = {
                            "step": step.action,
                            "command": step.command,
                            "exit_code": step.exit_code,
                            "stdout": step.stdout,
                            "stderr": step.stderr,
                            "failure_reason": step.failure_reason,
                            "root_cause": (step.stderr or step.error or step.output or "unknown").strip(),
                            "duration_ms": step.duration_ms,
                        }
                    if compose_blocked_by_step_failure(step.action):
                        block_compose = True
            else:
                step.status = DeployStepStatus.SKIPPED

        deploy_ctx = ctx.data.get("deploy_executor_context")
        if isinstance(deploy_ctx, DeployExecutorContext):
            state.executed_commands = list(deploy_ctx.executed_commands)

        if failed_count:
            return StageResult(
                status=StageStatus.FAIL,
                message=f"failed {failed_count} step(s)",
            )

        label = "simulated" if dry_run else "executed"
        count = simulated_count if dry_run else executed_count
        return StageResult(
            status=StageStatus.PASS,
            message=f"{label} {count} step(s)",
        )


class SummaryStage(_DeployStage):
    id = "summary"
    label = "Summarize deploy run"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_deploy_state(ctx)
        state.summary = {
            "mode": "DRY-RUN" if state.dry_run else "LIVE",
            "release_decision": state.release_decision,
            "deployment_risk": state.deployment_risk,
            "blockers": len(state.blockers),
            "steps_total": len(state.steps),
            "steps_required": sum(1 for s in state.steps if s.required and not s.skipped),
            "steps_skipped": sum(1 for s in state.steps if s.skipped),
            "steps_simulated": sum(1 for s in state.steps if s.status == DeployStepStatus.SIMULATED),
            "steps_executed": sum(1 for s in state.steps if s.status == DeployStepStatus.EXECUTED),
            "steps_failed": sum(1 for s in state.steps if s.status == DeployStepStatus.FAILED),
        }
        ctx.transaction.deploy_run = state.to_dict()
        ctx.transaction.warnings.extend(state.warnings)
        if state.health:
            ctx.transaction.recommended_actions.append(f"Health: {state.health[:120]}")
        if state.containers:
            ctx.transaction.recommended_actions.append("Containers verified via compose ps")

        if state.dry_run:
            ctx.transaction.recommended_actions.insert(
                0,
                "Deploy dry-run complete — no mutations executed.",
            )
        else:
            ctx.transaction.recommended_actions.insert(0, "Deploy LIVE complete.")
            ctx.transaction.frontend_built = any(
                s.action == "frontend build" and s.status == DeployStepStatus.EXECUTED
                for s in state.steps
            )
            ctx.transaction.frontend_synced = any(
                s.action == "dist sync" and s.status == DeployStepStatus.EXECUTED
                for s in state.steps
            )
            ctx.transaction.containers_restarted = ["api", "worker"]
            if state.executed_commands:
                ctx.transaction.recommended_actions.append(
                    f"Executed {len(state.executed_commands)} command(s)"
                )

        ctx.transaction.recommended_actions.extend([f"Blocker: {b}" for b in state.blockers[:3]])

        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")
        markdown = render_markdown(state, transaction=ctx.transaction)
        json_report = render_json(state, transaction=ctx.transaction)
        ctx.data["report_markdown"] = markdown
        ctx.data["report_json"] = json_report

        if output_format in ("markdown", "terminal") or report_path:
            if output_format != "json" or report_path:
                out = Path(report_path) if report_path else default_report_path("IFG_DEPLOY_RUN")
                write_report(out, markdown)
                ctx.data["report_file"] = str(out)
                ctx.transaction.artifacts.append(
                    ArtifactRecord(type="ifg_deploy_run_report", path=str(out))
                )

        ctx.data["summary"] = dict(state.summary)
        return StageResult(status=StageStatus.PASS, message="summary complete")
