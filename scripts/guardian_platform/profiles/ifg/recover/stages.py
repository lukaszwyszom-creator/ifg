from __future__ import annotations

from pathlib import Path

from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.context import WorkflowContext
from guardian_platform.core.workflow.intents import NoOpIntent
from guardian_platform.core.workflow.results import StageExecutionResults
from guardian_platform.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from guardian_platform.profiles.ifg.config.defaults import COMPOSE_FILE, DEFAULT_REMOTE_PATH, resolve_remote_host
from guardian_platform.profiles.ifg.infra.compose import compose_services_healthy, parse_compose_service_states, remote_compose_ps
from guardian_platform.profiles.ifg.infra.exec import run_remote
from guardian_platform.profiles.ifg.infra.ssh import remote_git, ssh
from guardian_platform.profiles.ifg.lib.deploy_reporting import recover_report_path, write_report
from guardian_platform.profiles.ifg.recover.models import RecoverState
from guardian_platform.profiles.ifg.recover.report import render_json, render_markdown
from guardian_platform.profiles.ifg.recover.service import get_recover_state


class _RecoverStage(Stage):
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="halt")


class InitStage(_RecoverStage):
    id = "init"
    label = "Initialize prod recover"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        dry_run = ctx.mode != ExecutionMode.LIVE
        assume_yes = bool(ctx.data.get("assume_yes"))
        if not dry_run and not assume_yes:
            return StageResult(status=StageStatus.FAIL, message="LIVE recover requires --yes")

        state = RecoverState(
            dry_run=dry_run,
            assume_yes=assume_yes,
            remote_host=resolve_remote_host(ctx.data.get("remote_host")),
            remote_path=str(ctx.data.get("remote_path") or DEFAULT_REMOTE_PATH),
        )
        ctx.data["recover"] = state
        return StageResult(status=StageStatus.PASS, message="initialized")


class RepositoryValidationStage(_RecoverStage):
    id = "repository_validation"
    label = "Repository validation"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        if state.dry_run:
            state.git_branch = "production"
            state.git_head = "dry-run"
            return StageResult(status=StageStatus.PASS, message="dry-run repo validation")

        try:
            state.git_branch = remote_git(state.remote_host, state.remote_path, "branch --show-current")
            state.git_head = remote_git(state.remote_host, state.remote_path, "rev-parse --short HEAD")
        except RuntimeError as exc:
            state.aborted = True
            state.abort_reason = str(exc)
            return StageResult(status=StageStatus.FAIL, message=str(exc))

        return StageResult(status=StageStatus.PASS, message=f"{state.git_branch} @ {state.git_head}")


class DockerStatusStage(_RecoverStage):
    id = "docker_status"
    label = "Docker status"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        if state.dry_run:
            state.notes.append("[dry-run] would inspect docker compose ps")
            return StageResult(status=StageStatus.PASS, message="dry-run docker status")

        if state.aborted:
            return StageResult(status=StageStatus.SKIP, message="skipped")

        try:
            ps = remote_compose_ps(state.remote_host, state.remote_path)
            states = parse_compose_service_states(ps)
            ok, problems = compose_services_healthy(states)
            if not ok:
                state.notes.append(f"container issues: {'; '.join(problems)}")
        except RuntimeError as exc:
            state.notes.append(f"compose ps: {exc}")

        return StageResult(status=StageStatus.PASS, message="docker status collected")


class RestartServicesStage(_RecoverStage):
    id = "restart_services"
    label = "Restart services"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        compose = f"sudo docker compose -f {COMPOSE_FILE}"

        if state.dry_run:
            state.notes.append(f"[dry-run] {compose} up -d db")
            state.notes.append(f"[dry-run] {compose} up -d api worker")
            return StageResult(status=StageStatus.PASS, message="dry-run restart planned")

        if state.aborted:
            return StageResult(status=StageStatus.SKIP, message="skipped")

        db = run_remote(
            state.remote_host,
            f"{compose} up -d db",
            remote_path=state.remote_path,
            dry_run=False,
        )
        if not db.ok:
            state.aborted = True
            state.abort_reason = db.error or "db restart failed"
            return StageResult(status=StageStatus.FAIL, message=state.abort_reason)
        state.db_ok = True

        api_worker = run_remote(
            state.remote_host,
            f"{compose} up -d api worker",
            remote_path=state.remote_path,
            dry_run=False,
        )
        if not api_worker.ok:
            state.aborted = True
            state.abort_reason = api_worker.error or "api/worker restart failed"
            return StageResult(status=StageStatus.FAIL, message=state.abort_reason)

        return StageResult(status=StageStatus.PASS, message="services restarted")


class HealthStage(_RecoverStage):
    id = "health"
    label = "Health check"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        if state.dry_run:
            state.notes.append("[dry-run] curl http://127.0.0.1:8000/health")
            state.health_ok = True
            return StageResult(status=StageStatus.PASS, message="dry-run health")

        if state.aborted:
            return StageResult(status=StageStatus.SKIP, message="skipped")

        try:
            body = ssh(state.remote_host, "curl -sS -m 10 http://127.0.0.1:8000/health")
            state.health_body = body
            state.health_ok = bool(body) and ("ok" in body.lower() or '"status"' in body.lower())
        except RuntimeError as exc:
            state.health_ok = False
            state.abort_reason = str(exc)
            state.aborted = True
            return StageResult(status=StageStatus.FAIL, message=str(exc))

        if not state.health_ok:
            state.aborted = True
            state.abort_reason = "health check failed"
            return StageResult(status=StageStatus.FAIL, message=state.abort_reason)

        return StageResult(status=StageStatus.PASS, message="health ok")


class WorkerVerificationStage(_RecoverStage):
    id = "worker_verification"
    label = "Worker verification"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        if state.dry_run:
            state.worker_ok = True
            return StageResult(status=StageStatus.PASS, message="dry-run worker ok")

        if state.aborted:
            return StageResult(status=StageStatus.SKIP, message="skipped")

        try:
            ps = remote_compose_ps(state.remote_host, state.remote_path)
            states = parse_compose_service_states(ps)
            worker = states.get("worker", "")
            state.worker_ok = "running" in worker.lower() or "up" in worker.lower()
            api = states.get("api", "")
            state.api_ok = state.health_ok and ("running" in api.lower() or "up" in api.lower())
        except RuntimeError as exc:
            state.notes.append(f"worker check: {exc}")

        return StageResult(status=StageStatus.PASS, message=f"worker_ok={state.worker_ok}")


class KSeFVerificationStage(_RecoverStage):
    id = "ksef_verification"
    label = "KSeF verification"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        if state.dry_run:
            state.ksef_ok = True
            state.notes.append("[dry-run] verify KSeF openapi endpoint")
            return StageResult(status=StageStatus.PASS, message="dry-run ksef ok")

        if state.aborted:
            return StageResult(status=StageStatus.SKIP, message="skipped")

        try:
            body = ssh(state.remote_host, "curl -sS -m 10 http://127.0.0.1:8000/openapi.json")
            state.ksef_ok = "/api/v1/ksef-sessions" in body
        except RuntimeError:
            state.ksef_ok = False

        return StageResult(status=StageStatus.PASS, message=f"ksef_ok={state.ksef_ok}")


class RecoveryReportStage(_RecoverStage):
    id = "recovery_report"
    label = "Recovery report"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = get_recover_state(ctx)
        state.summary = {
            "mode": "DRY-RUN" if state.dry_run else "LIVE",
            "aborted": state.aborted,
            "health_ok": state.health_ok,
        }
        ctx.transaction.profile_data["recover"] = state.to_dict()

        report_path = ctx.data.get("report_path")
        out = Path(report_path) if report_path else recover_report_path()
        write_report(out, render_markdown(state, transaction=ctx.transaction))
        ctx.data["report_file"] = str(out)
        ctx.data["report_json"] = render_json(state, transaction=ctx.transaction)

        return StageResult(status=StageStatus.PASS, message=f"report: {out.name}")
