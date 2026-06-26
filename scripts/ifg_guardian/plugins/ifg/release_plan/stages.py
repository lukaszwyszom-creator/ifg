from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH, TARGET_BRANCH
from ifg_guardian.core.git import git, short_sha
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import BuildReason, Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.state import WorkflowState
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.release_plan.artifacts import build_artifacts
from ifg_guardian.plugins.ifg.release_plan.build_detector import (
    analyze_repository_from_doctor,
    detect_build_decisions,
)
from ifg_guardian.plugins.ifg.release_plan.execution_plan import build_execution_plan
from ifg_guardian.plugins.ifg.release_plan.models import ReleasePlanState
from ifg_guardian.plugins.ifg.release_plan.report import render_json, render_markdown
from ifg_guardian.plugins.ifg.release_plan.risk import aggregate_deployment_risk
from ifg_guardian.plugins.ifg.release_plan.service import get_doctor_dependency, get_plan_state
from ifg_guardian.reporting import default_report_path, write_report


class _PlanStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")


class InitStage(_PlanStage):
    id = "init"
    label = "Initialize release plan"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        ctx.data["release_plan"] = ReleasePlanState()
        ctx.data.setdefault("output_format", "terminal")
        ctx.data.setdefault("remote_path", DEFAULT_REMOTE_PATH)
        return StageResult(status=StageStatus.PASS, message="release plan initialized")


class DependencyStage(_PlanStage):
    id = "dependency"
    label = "Verify workflow dependencies"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        deps = ctx.data.get("dependency_contexts", {})
        expected = list(ctx.workflow.depends_on)
        reasons: list[BuildReason] = []
        missing = [dep for dep in expected if dep not in deps]
        if missing:
            return StageResult(
                status=StageStatus.FAIL,
                message=f"missing dependencies: {', '.join(missing)}",
            )

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


class DoctorStage(_PlanStage):
    id = "doctor"
    label = "Consume doctor dependency"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        doctor = get_doctor_dependency(ctx)
        dep_ctx = ctx.data["dependency_contexts"]["ifg.doctor"]

        state.doctor_overall_status = doctor.overall_status.value
        state.doctor_workflow_id = dep_ctx.transaction.workflow_id
        ctx.data["doctor_state"] = doctor

        return StageResult(
            status=StageStatus.PASS,
            message=f"doctor: {doctor.overall_status.value}",
            reasons=[
                BuildReason(
                    decision="doctor_status",
                    because=[doctor.overall_status.value],
                    source_stage=self.id,
                )
            ],
        )


class RepositoryAnalysisStage(_PlanStage):
    id = "repository_analysis"
    label = "Analyze repository state"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        doctor = ctx.data["doctor_state"]

        snapshot = analyze_repository_from_doctor(doctor)
        try:
            snapshot.head_sha = git("rev-parse", "HEAD")
            snapshot.head_short = short_sha(snapshot.head_sha)
            snapshot.branch = git("branch", "--show-current")
            counts = git("rev-list", "--left-right", "--count", f"HEAD...origin/{TARGET_BRANCH}")
            ahead_s, behind_s = counts.split("\t", 1)
            snapshot.ahead = int(ahead_s)
            snapshot.behind = int(behind_s)
        except RuntimeError:
            pass

        state.repository = snapshot
        ctx.transaction.commit_before = snapshot.head_sha
        ctx.transaction.commit_after = snapshot.head_sha
        ctx.transaction.branch = snapshot.branch

        return StageResult(
            status=StageStatus.PASS,
            message=f"HEAD {snapshot.head_short} on {snapshot.branch}",
        )


class BuildDecisionStage(_PlanStage):
    id = "build_decision"
    label = "Determine build requirements"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        doctor = ctx.data["doctor_state"]
        state.build_decisions = detect_build_decisions(doctor, state.repository)

        reasons = [
            BuildReason(
                decision=d.name.replace(" ", "_").lower(),
                because=[d.reason],
                confidence=d.confidence,
                source_stage=self.id,
            )
            for d in state.build_decisions
            if d.required
        ]
        required = sum(1 for d in state.build_decisions if d.required)
        return StageResult(
            status=StageStatus.PASS,
            message=f"{required} build decision(s) required",
            reasons=reasons,
        )


class MigrationStage(_PlanStage):
    id = "migration"
    label = "Plan migration step"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        migration = next((d for d in state.build_decisions if d.name == "Migration Required"), None)
        if migration and migration.required:
            ctx.transaction.alembic_after = "head (planned)"
            return StageResult(status=StageStatus.PASS, message=f"migration planned: {migration.reason}")
        return StageResult(status=StageStatus.PASS, message="no migration required")


class ArtifactStage(_PlanStage):
    id = "artifact"
    label = "Build artifact list"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        doctor = ctx.data["doctor_state"]
        state.artifacts = build_artifacts(state, doctor)
        return StageResult(
            status=StageStatus.PASS,
            message=f"{len(state.artifacts)} artifact(s) planned",
        )


class ExecutionPlanStage(_PlanStage):
    id = "execution_plan"
    label = "Build execution plan"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        state.execution_plan = build_execution_plan(state.build_decisions)
        required = sum(1 for s in state.execution_plan if s.required)
        return StageResult(
            status=StageStatus.PASS,
            message=f"{len(state.execution_plan)} steps ({required} required)",
        )


class RiskStage(_PlanStage):
    id = "risk"
    label = "Aggregate deployment risk"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        doctor = ctx.data["doctor_state"]
        risk, rationale = aggregate_deployment_risk(doctor, state)
        state.deployment_risk = risk
        state.risk_rationale = rationale
        return StageResult(
            status=StageStatus.PASS,
            message=f"deployment risk: {risk.value}",
            reasons=[
                BuildReason(
                    decision="deployment_risk",
                    because=rationale[:3] or [risk.value],
                    source_stage=self.id,
                )
            ],
        )


class SummaryStage(_PlanStage):
    id = "summary"
    label = "Summarize release plan"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_plan_state(ctx)
        state.summary = {
            "deployment_risk": state.deployment_risk.value,
            "doctor_status": state.doctor_overall_status,
            "build_steps_required": sum(1 for d in state.build_decisions if d.required),
            "execution_steps": len(state.execution_plan),
            "artifacts": len(state.artifacts),
        }
        ctx.transaction.release_plan = state.to_dict()

        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")
        markdown = render_markdown(state, transaction=ctx.transaction)
        json_report = render_json(state, transaction=ctx.transaction)
        ctx.data["report_markdown"] = markdown
        ctx.data["report_json"] = json_report

        if output_format in ("markdown", "terminal") or report_path:
            if output_format != "json" or report_path:
                out = Path(report_path) if report_path else default_report_path("IFG_RELEASE_PLAN")
                write_report(out, markdown)
                ctx.data["report_file"] = str(out)
                ctx.transaction.artifacts.append(
                    ArtifactRecord(type="ifg_release_plan_report", path=str(out))
                )

        ctx.data["summary"] = dict(state.summary)
        return StageResult(status=StageStatus.PASS, message="summary complete")
