"""Etapy workflow przeładowania środowiska IFG (GWO-GUARDIAN-0079)."""
from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.compose import parse_compose_service_states, service_state_is_running
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.env_reload.aggregation import (
    aggregate_env_reload_status,
    build_operator_actions,
    summarize_startup_logs,
)
from ifg_guardian.plugins.ifg.env_reload.models import (
    EnvReloadStageStatus,
    EnvReloadState,
    PreflightCheck,
    ServiceStatus,
)
from ifg_guardian.plugins.ifg.env_reload.remote import (
    compose_config_script,
    compose_ps_script,
    compose_reload_script,
    env_file_check_script,
    health_probe_script,
    ssh_probe_script,
    startup_logs_script,
)
from ifg_guardian.plugins.ifg.env_reload.report import default_env_reload_report_path, render_env_reload_markdown


def _ssh(ctx: WorkflowContext) -> SSHExecutor:
    deploy_ctx = ctx.data.get("deploy_executor_context")
    if not isinstance(deploy_ctx, DeployExecutorContext):
        deploy_ctx = DeployExecutorContext(
            remote_host=ctx.data.get("remote_host"),
            remote_path=ctx.data.get("remote_path"),
        )
        ctx.data["deploy_executor_context"] = deploy_ctx
    return SSHExecutor(root=ctx.root, deploy_context=deploy_ctx)


def _dry_run(ctx: WorkflowContext) -> bool:
    return ctx.mode in (ExecutionMode.DRY_RUN, ExecutionMode.PLAN)


def _get_state(ctx: WorkflowContext) -> EnvReloadState:
    state = ctx.data.get("env_reload_state")
    if state is None:
        raise RuntimeError("env reload workflow not initialized")
    return state


class _EnvReloadStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")


class InitStage(_EnvReloadStage):
    id = "init"
    label = "Initialize env reload workflow"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        dry_run = _dry_run(ctx)
        assume_yes = bool(ctx.data.get("assume_yes"))
        if not dry_run and not assume_yes:
            return StageResult(status=StageStatus.FAIL, message="LIVE env reload requires --yes")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        state = EnvReloadState(
            dry_run=dry_run,
            remote_host=cfg.ssh_target,
            remote_path=cfg.repo,
            env_file=cfg.env_file,
            compose_file=cfg.compose_file,
        )
        ctx.data["env_reload_state"] = state
        ctx.data.setdefault("output_format", "terminal")
        ctx.transaction.host_remote = cfg.ssh_target
        ctx.transaction.remote_path = cfg.repo
        message = "env reload dry-run initialized" if dry_run else "env reload LIVE initialized"
        return StageResult(status=StageStatus.PASS, message=message)


class PreflightStage(_EnvReloadStage):
    id = "preflight"
    label = "Verify DS723+ connection and environment files"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        checks: list[PreflightCheck] = []

        if _dry_run(ctx):
            checks.append(
                PreflightCheck(
                    "ssh",
                    EnvReloadStageStatus.WARN,
                    "skipped in dry-run (would probe DS723+ SSH)",
                )
            )
            checks.append(
                PreflightCheck(
                    "env_file",
                    EnvReloadStageStatus.WARN,
                    f"skipped in dry-run (would check {cfg.env_file})",
                )
            )
            checks.append(
                PreflightCheck(
                    "compose_file",
                    EnvReloadStageStatus.WARN,
                    f"skipped in dry-run (would check {cfg.compose_file})",
                )
            )
            state.preflight_checks = checks
            return StageResult(status=StageStatus.PASS, message="preflight simulated")

        probe = ssh.run_remote(ssh_probe_script(), label="ssh_probe")
        if probe.ok:
            checks.append(PreflightCheck("ssh", EnvReloadStageStatus.PASS, f"connected to {cfg.ssh_target}"))
        else:
            checks.append(
                PreflightCheck(
                    "ssh",
                    EnvReloadStageStatus.FAIL,
                    probe.error or probe.output or "SSH connection failed",
                )
            )

        env_result = ssh.run_remote(env_file_check_script(cfg), label="env_file_check")
        if env_result.ok and "exists:" in env_result.output:
            state.env_file_exists = True
            checks.append(PreflightCheck("env_file", EnvReloadStageStatus.PASS, cfg.env_file))
        else:
            state.env_file_exists = False
            checks.append(
                PreflightCheck(
                    "env_file",
                    EnvReloadStageStatus.FAIL,
                    env_result.error or env_result.output or f"missing {cfg.env_file}",
                )
            )

        compose_result = ssh.run_remote(compose_config_script(cfg), label="compose_config_check")
        if compose_result.ok and "compose:" in compose_result.output:
            checks.append(PreflightCheck("compose_file", EnvReloadStageStatus.PASS, cfg.compose_file))
        else:
            checks.append(
                PreflightCheck(
                    "compose_file",
                    EnvReloadStageStatus.FAIL,
                    compose_result.error or compose_result.output or f"missing {cfg.compose_file}",
                )
            )

        state.preflight_checks = checks
        status = StageStatus.FAIL if state.preflight_has_fail() else StageStatus.PASS
        return StageResult(status=status, message=f"{len(checks)} preflight check(s)")


class ReloadStage(Stage):
    id = "reload"
    label = "Reload api and worker via docker compose up"
    mutating = True

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.preflight_has_fail():
            return StageResult(status=StageStatus.FAIL, message="blocked — preflight failed")

        if _dry_run(ctx):
            state.compose_up_output = "[dry-run] docker compose up -d api worker"
            return StageResult(status=StageStatus.PASS, message="[dry-run] compose up simulated")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        result = ssh.run_remote(compose_reload_script(cfg), label="compose_env_reload")
        state.compose_up_output = result.output or result.error or ""
        if not result.ok:
            return StageResult(
                status=StageStatus.FAIL,
                message=result.error or "compose up failed",
            )

        state.compose_up_executed = True
        state.containers_restarted = ["api", "worker"]
        ctx.transaction.containers_restarted = ["api", "worker"]
        return StageResult(status=StageStatus.PASS, message="compose up -d api worker")


class VerifyStage(_EnvReloadStage):
    id = "verify"
    label = "Verify api and worker containers are running"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.preflight_has_fail():
            return StageResult(status=StageStatus.FAIL, message="skipped — preflight failed")
        if _dry_run(ctx):
            state.service_statuses = [
                ServiceStatus("api", True, "[dry-run] running"),
                ServiceStatus("worker", True, "[dry-run] running"),
            ]
            return StageResult(status=StageStatus.PASS, message="[dry-run] service verify simulated")

        if not state.compose_up_executed:
            return StageResult(status=StageStatus.FAIL, message="skipped — compose up did not run")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        ps_result = ssh.run_remote(compose_ps_script(cfg), label="compose_ps_post_reload")
        if not ps_result.ok:
            return StageResult(status=StageStatus.FAIL, message=ps_result.error or "compose ps failed")

        states = parse_compose_service_states(ps_result.output)
        service_statuses: list[ServiceStatus] = []
        for svc in ("api", "worker"):
            raw = states.get(svc, "")
            running = service_state_is_running(raw)
            service_statuses.append(ServiceStatus(svc, running, raw or "not found"))
        state.service_statuses = service_statuses

        status = StageStatus.PASS if state.services_running() else StageStatus.FAIL
        return StageResult(status=status, message=f"api/worker running={state.services_running()}")


class HealthStage(_EnvReloadStage):
    id = "health"
    label = "Probe IFG health endpoint"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.preflight_has_fail() or _dry_run(ctx):
            state.health_detail = "skipped in dry-run" if _dry_run(ctx) else "skipped — preflight failed"
            return StageResult(
                status=StageStatus.WARN if _dry_run(ctx) else StageStatus.FAIL,
                message=state.health_detail,
            )
        if not state.compose_up_executed:
            state.health_detail = "skipped — compose up did not run"
            return StageResult(status=StageStatus.FAIL, message=state.health_detail)

        ssh = _ssh(ctx)
        result = ssh.run_remote(health_probe_script(), label="health_probe")
        body = (result.output or "").strip()
        state.health_detail = body[:200] if body else (result.error or "empty response")
        ok = result.ok and bool(body) and ("ok" in body.lower() or '"status"' in body.lower())
        state.health_ok = ok
        status = StageStatus.PASS if ok else StageStatus.FAIL
        return StageResult(status=status, message=state.health_detail or "health probe")


class LogsStage(_EnvReloadStage):
    id = "logs"
    label = "Collect startup logs (last 30 lines)"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if _dry_run(ctx):
            state.startup_logs = "[dry-run] logs not collected"
            state.startup_logs_summary = ["Dry-run — logi niepobrane."]
            return StageResult(status=StageStatus.PASS, message="[dry-run] logs simulated")

        if not state.compose_up_executed:
            state.startup_logs_summary = ["Compose up nie wykonany — brak logów."]
            return StageResult(status=StageStatus.WARN, message="logs skipped")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        result = ssh.run_remote(startup_logs_script(cfg, tail=30), label="startup_logs")
        state.startup_logs = result.output if result.ok else (result.error or "")
        state.startup_logs_summary = summarize_startup_logs(state.startup_logs)
        status = StageStatus.PASS if result.ok else StageStatus.WARN
        return StageResult(status=status, message=f"{len(state.startup_logs_summary)} log line(s) summarized")


class SummaryStage(_EnvReloadStage):
    id = "summary"
    label = "Summarize env reload workflow"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        state.operator_actions = build_operator_actions(state)
        state.overall_status = aggregate_env_reload_status(state)
        state.summary = {
            "overall_status": state.overall_status.value,
            "dry_run": state.dry_run,
            "env_file": state.env_file,
            "compose_file": state.compose_file,
            "containers_restarted": list(state.containers_restarted),
            "health_ok": state.health_ok,
        }
        ctx.transaction.env_reload = state.to_dict()

        markdown = render_env_reload_markdown(state, transaction=ctx.transaction)
        ctx.data["report_markdown"] = markdown

        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")
        if output_format in ("markdown", "terminal") or report_path:
            out = Path(report_path) if report_path else default_env_reload_report_path()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(markdown, encoding="utf-8")
            ctx.data["report_file"] = str(out)
            ctx.transaction.artifacts.append(
                ArtifactRecord(type="ifg_env_reload_report", path=str(out))
            )

        ctx.data["summary"] = dict(state.summary)
        final = StageStatus.PASS if state.overall_status.value == "READY" else StageStatus.FAIL
        return StageResult(status=final, message=state.overall_status.value)
