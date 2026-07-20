from __future__ import annotations

from pathlib import Path

from ifg_guardian.config import DEFAULT_REMOTE_PATH
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.doctor.aggregation import (
    aggregate_overall_status,
    stage_status_from_checks,
)
from ifg_guardian.plugins.ifg.doctor.checks import (
    run_alembic_checks,
    run_backend_checks,
    run_configuration_checks,
    run_database_checks,
    run_docker_checks,
    run_environment_checks,
    run_frontend_checks,
    run_health_checks,
    run_repository_checks,
)
from ifg_guardian.plugins.ifg.doctor.models import CheckStatus, DoctorState
from ifg_guardian.plugins.ifg.doctor.report import render_json, render_markdown
from ifg_guardian.plugins.ifg.doctor.service import add_checks, get_doctor_state
from ifg_guardian.reporting import default_report_path, write_report


class _DoctorStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")


class InitStage(_DoctorStage):
    id = "init"
    label = "Initialize IFG doctor"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = DoctorState(
            remote_host=str(ctx.data.get("remote_host") or ""),
            remote_path=str(ctx.data.get("remote_path") or DEFAULT_REMOTE_PATH),
            dry_run=ctx.mode in (ExecutionMode.DRY_RUN, ExecutionMode.PLAN),
            do_fetch=bool(ctx.data.get("do_fetch", False)) and ctx.mode == ExecutionMode.LIVE,
        )
        ctx.data["doctor"] = state
        ctx.data.setdefault("output_format", "terminal")
        return StageResult(status=StageStatus.PASS, message="doctor initialized")


class EnvironmentStage(_DoctorStage):
    id = "environment"
    label = "Environment checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_environment_checks(do_fetch=state.do_fetch)
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} environment check(s)",
        )


class RepositoryStage(_DoctorStage):
    id = "repository"
    label = "Repository checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        from ifg_guardian.modules.repo_audit import collect_audit

        state = get_doctor_state(ctx)
        try:
            audit = collect_audit(do_fetch=state.do_fetch)
            ctx.data["repo_audit"] = audit
        except RuntimeError as exc:
            ctx.data["repo_audit"] = None
            from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus

            checks = [
                CheckResult(
                    "repo.audit",
                    "repository",
                    "repo audit",
                    CheckStatus.CRITICAL,
                    str(exc),
                )
            ]
            add_checks(state, checks)
            return StageResult(status=StageStatus.FAIL, message=str(exc))

        checks = run_repository_checks(ctx.data.get("repo_audit"))
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} repository check(s)",
        )


class FrontendStage(_DoctorStage):
    id = "frontend"
    label = "Frontend checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_frontend_checks()
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} frontend check(s)",
        )


class BackendStage(_DoctorStage):
    id = "backend"
    label = "Backend checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_backend_checks(
            ctx.data.get("repo_audit"),
            remote_host=state.remote_host or None,
            remote_path=state.remote_path or None,
            defer_remote_image_verify=True,
        )
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} backend check(s)",
        )


class DockerStage(_DoctorStage):
    id = "docker"
    label = "Docker checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_docker_checks(
            remote_host=state.remote_host,
            remote_path=state.remote_path,
            dry_run=state.dry_run,
        )
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} docker check(s)",
        )


class DatabaseStage(_DoctorStage):
    id = "database"
    label = "Database checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_database_checks(dry_run=state.dry_run)
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} database check(s)",
        )


class AlembicStage(_DoctorStage):
    id = "alembic"
    label = "Alembic checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_alembic_checks(
            remote_host=state.remote_host,
            remote_path=state.remote_path,
            dry_run=state.dry_run,
        )
        add_checks(state, checks)
        ctx.data["alembic_snapshot"] = checks
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} alembic check(s)",
        )


class ConfigurationStage(_DoctorStage):
    id = "configuration"
    label = "Configuration checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_configuration_checks()
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} configuration check(s)",
        )


class HealthStage(_DoctorStage):
    id = "health"
    label = "Health checks"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        checks = run_health_checks(
            remote_host=state.remote_host,
            remote_path=state.remote_path,
            dry_run=state.dry_run,
        )
        add_checks(state, checks)
        return StageResult(
            status=stage_status_from_checks(checks),
            message=f"{len(checks)} health check(s)",
        )


class RiskAggregationStage(_DoctorStage):
    id = "risk_aggregation"
    label = "Aggregate overall status"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        state.overall_status = aggregate_overall_status(state)
        ctx.transaction.recommended_actions = [
            f"Overall: {state.overall_status.value}",
            "Doctor is read-only — no automatic fixes applied.",
        ]
        return StageResult(
            status=StageStatus.PASS,
            message=f"overall status: {state.overall_status.value}",
        )


class SummaryStage(_DoctorStage):
    id = "summary"
    label = "Summarize IFG doctor"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_doctor_state(ctx)
        pass_count = sum(1 for c in state.checks if c.status == CheckStatus.PASS)
        warn_count = sum(1 for c in state.checks if c.status == CheckStatus.WARN)
        fail_count = sum(1 for c in state.checks if c.status == CheckStatus.FAIL)
        crit_count = sum(1 for c in state.checks if c.status == CheckStatus.CRITICAL)

        state.summary = {
            "overall_status": state.overall_status.value,
            "checks_total": len(state.checks),
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "critical": crit_count,
        }
        ctx.transaction.doctor = state.to_dict()

        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")
        markdown = render_markdown(state, transaction=ctx.transaction)
        json_report = render_json(state, transaction=ctx.transaction)
        ctx.data["report_markdown"] = markdown
        ctx.data["report_json"] = json_report

        if output_format in ("markdown", "terminal") or report_path:
            if output_format != "json" or report_path:
                out = Path(report_path) if report_path else default_report_path("IFG_DOCTOR")
                write_report(out, markdown)
                ctx.data["report_file"] = str(out)
                ctx.transaction.artifacts.append(
                    ArtifactRecord(type="ifg_doctor_report", path=str(out))
                )

        ctx.data["summary"] = dict(state.summary)
        return StageResult(status=StageStatus.PASS, message="summary complete")
