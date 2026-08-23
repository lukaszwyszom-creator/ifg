from __future__ import annotations

from pathlib import Path

from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext
from ifg_guardian.core.workflow.executors.ssh_executor import SSHExecutor
from ifg_guardian.core.workflow.intents import NoOpIntent
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import Stage, StagePlan, StageResult, StageStatus
from ifg_guardian.core.workflow.transaction import ArtifactRecord
from ifg_guardian.plugins.ifg.smtp.aggregation import aggregate_smtp_status, build_operator_actions
from ifg_guardian.plugins.ifg.smtp.config import (
    build_smtp_config,
    load_smtp_env_local,
    mask_config_values,
    parse_env_text,
    run_config_checks,
)
from ifg_guardian.plugins.ifg.smtp.connectivity import run_connectivity_checks
from ifg_guardian.plugins.ifg.smtp.models import ConfigCheck, SmtpEnvironment, SmtpStageStatus, SmtpState
from ifg_guardian.plugins.ifg.smtp.remote import env_file_read_script, ssh_probe_script
from ifg_guardian.plugins.ifg.smtp.report import render_smtp_markdown
from ifg_guardian.plugins.ifg.smtp.test_send import send_test_mail
from ifg_guardian.reporting import default_report_path, write_report


def _ssh(ctx: WorkflowContext) -> SSHExecutor:
    deploy_ctx = ctx.data.get("deploy_executor_context")
    if not isinstance(deploy_ctx, DeployExecutorContext):
        deploy_ctx = DeployExecutorContext(
            remote_host=ctx.data.get("remote_host"),
            remote_path=ctx.data.get("remote_path"),
        )
        ctx.data["deploy_executor_context"] = deploy_ctx
    return SSHExecutor(root=ctx.root, deploy_context=deploy_ctx)


class _SmtpStage(Stage):
    mutating = False

    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        return StagePlan(intents=[NoOpIntent(reason=self.id)], on_fail="continue")


def _get_state(ctx: WorkflowContext) -> SmtpState:
    state = ctx.data.get("smtp_state")
    if state is None:
        raise RuntimeError("smtp workflow not initialized")
    return state


class InitStage(_SmtpStage):
    id = "init"
    label = "Initialize SMTP workflow"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        mode = str(ctx.data.get("smtp_mode", "check"))
        use_local = bool(ctx.data.get("use_local"))
        environment = SmtpEnvironment.LOCAL if use_local else SmtpEnvironment.REMOTE
        state = SmtpState(mode=mode, environment=environment)
        if environment == SmtpEnvironment.REMOTE:
            cfg = _ssh(ctx).deploy_context.config()
            state.remote_host = cfg.ssh_target
            state.env_file = cfg.env_file
        ctx.data["smtp_state"] = state
        ctx.data.setdefault("output_format", "terminal")
        label = environment.value.lower()
        return StageResult(status=StageStatus.PASS, message=f"smtp {mode} initialized ({label})")


class PreflightStage(_SmtpStage):
    id = "preflight"
    label = "Verify DS723+ SSH connectivity"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.environment == SmtpEnvironment.LOCAL:
            state.ssh_ok = True
            return StageResult(status=StageStatus.PASS, message="local mode — SSH skipped")

        ssh = _ssh(ctx)
        cfg = ssh.deploy_context.config()
        state.remote_host = cfg.ssh_target
        state.env_file = cfg.env_file

        result = ssh.run_remote(ssh_probe_script(), label="smtp_ssh_probe")
        if result.ok:
            state.ssh_ok = True
            return StageResult(status=StageStatus.PASS, message=f"connected to {cfg.ssh_target}")

        state.ssh_ok = False
        state.config_checks = [
            ConfigCheck(
                key="ssh",
                status=SmtpStageStatus.FAIL,
                message=result.error or result.output or "SSH connection failed",
            )
        ]
        return StageResult(status=StageStatus.FAIL, message="SSH connection failed")


class ConfigStage(_SmtpStage):
    id = "config"
    label = "Validate SMTP configuration"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.environment == SmtpEnvironment.REMOTE and not state.ssh_ok:
            return StageResult(status=StageStatus.FAIL, message="blocked — SSH failed")

        env_path = ctx.data.get("env_file")
        env_file = Path(env_path) if env_path else None

        if state.environment == SmtpEnvironment.LOCAL:
            values, resolved = load_smtp_env_local(env_file=env_file)
            state.env_file = resolved
            if not values and not Path(resolved).is_file():
                state.config_checks = [
                    ConfigCheck(
                        key="env_file",
                        status=SmtpStageStatus.FAIL,
                        message=f"env file not found: {resolved}",
                    )
                ]
                return StageResult(status=StageStatus.FAIL, message="env file missing")
        else:
            ssh = _ssh(ctx)
            cfg = ssh.deploy_context.config()
            state.env_file = cfg.env_file
            read_result = ssh.run_remote(env_file_read_script(cfg), label="smtp_env_read")
            if not read_result.ok:
                missing = cfg.env_file
                stderr = (read_result.data.get("stderr") or read_result.error or "").strip()
                if "GUARDIAN_ENV_MISSING" in stderr or "GUARDIAN_ENV_MISSING" in (read_result.output or ""):
                    missing = stderr.split("GUARDIAN_ENV_MISSING:", 1)[-1].strip() or cfg.env_file
                state.config_checks = [
                    ConfigCheck(
                        key="env_file",
                        status=SmtpStageStatus.FAIL,
                        message=f"env file not found: {missing}",
                    )
                ]
                return StageResult(status=StageStatus.FAIL, message="remote env file missing")
            values = parse_env_text(read_result.output)

        checks, recipients, notify_enabled = run_config_checks(values)
        state.config_checks = checks
        state.recipients = recipients
        state.notify_enabled = notify_enabled
        state.masked_config = mask_config_values(values)
        ctx.data["smtp_env_values"] = values

        status = StageStatus.FAIL if state.config_has_fail() else StageStatus.PASS
        return StageResult(status=status, message=f"{len(checks)} config check(s)")


class ConnectivityStage(_SmtpStage):
    id = "connectivity"
    label = "Probe SMTP connectivity"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.environment == SmtpEnvironment.REMOTE and not state.ssh_ok:
            return StageResult(status=StageStatus.FAIL, message="blocked — SSH failed")
        if state.config_has_fail():
            return StageResult(status=StageStatus.WARN, message="skipped — config FAIL")

        values = ctx.data.get("smtp_env_values", {})
        config = build_smtp_config(values)
        if config is None:
            state.connectivity_checks = []
            return StageResult(status=StageStatus.FAIL, message="cannot build SMTP config")

        state.connectivity_checks = run_connectivity_checks(config)
        status = StageStatus.FAIL if state.connectivity_has_fail() else StageStatus.PASS
        return StageResult(status=status, message=f"{len(state.connectivity_checks)} connectivity probe(s)")


class TestSendStage(_SmtpStage):
    id = "test_send"
    label = "Send diagnostic test mail"
    mutating = True

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        if state.mode != "test":
            return StageResult(status=StageStatus.PASS, message="skipped in check mode")

        if state.environment == SmtpEnvironment.REMOTE and not state.ssh_ok:
            state.test_result = None
            return StageResult(status=StageStatus.FAIL, message="blocked — SSH failed")
        if state.config_has_fail() or state.connectivity_has_fail():
            state.test_result = None
            return StageResult(status=StageStatus.FAIL, message="blocked — SMTP check failed")

        values = ctx.data.get("smtp_env_values", {})
        config = build_smtp_config(values)
        if config is None or not state.recipients:
            return StageResult(status=StageStatus.FAIL, message="missing SMTP config or recipients")

        app_version = (values.get("APP_VERSION") or "0.1.0").strip()
        state.test_result = send_test_mail(
            config=config,
            recipients=state.recipients,
            workflow_id=ctx.transaction.workflow_id,
            app_version=app_version,
        )
        status = StageStatus.PASS if state.test_result.status == SmtpStageStatus.PASS else StageStatus.FAIL
        return StageResult(status=status, message=state.test_result.message)


class SummaryStage(_SmtpStage):
    id = "summary"
    label = "Summarize SMTP workflow"

    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        state = _get_state(ctx)
        state.operator_actions = build_operator_actions(state)
        state.overall_status = aggregate_smtp_status(state)
        state.summary = {
            "overall_status": state.overall_status.value,
            "environment": state.environment.value,
            "env_file": state.env_file,
            "config_checks": len(state.config_checks),
            "connectivity_checks": len(state.connectivity_checks),
            "recipients": len(state.recipients),
            "test_sent": bool(state.test_result and state.test_result.sent),
        }
        ctx.transaction.smtp = state.to_dict()

        markdown = render_smtp_markdown(state, transaction=ctx.transaction)
        ctx.data["report_markdown"] = markdown

        output_format = ctx.data.get("output_format", "terminal")
        report_path = ctx.data.get("report_path")
        prefix = "IFG_SMTP_TEST" if state.mode == "test" else "IFG_SMTP_CHECK"
        if output_format in ("markdown", "terminal") or report_path:
            out = Path(report_path) if report_path else default_report_path(prefix)
            write_report(out, markdown)
            ctx.data["report_file"] = str(out)
            ctx.transaction.artifacts.append(
                ArtifactRecord(type=f"ifg_smtp_{state.mode}_report", path=str(out))
            )

        ctx.data["summary"] = dict(state.summary)
        return StageResult(status=StageStatus.PASS, message=state.overall_status.value)
