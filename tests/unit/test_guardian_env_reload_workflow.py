"""Testy workflow env reload Guardiana (GWO-GUARDIAN-0079)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402

_runtime = create_runtime()
_runtime.shutdown()

from ifg_guardian.core.reporting.schema import STANDARD_SECTIONS  # noqa: E402
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.results import IntentResult, StageExecutionResults  # noqa: E402
from ifg_guardian.plugins.ifg.env_reload.aggregation import (  # noqa: E402
    aggregate_env_reload_status,
    build_operator_actions,
    exit_code_for_env_reload,
    summarize_startup_logs,
)
from ifg_guardian.plugins.ifg.env_reload.models import (  # noqa: E402
    EnvReloadOverallStatus,
    EnvReloadStageStatus,
    EnvReloadState,
    PreflightCheck,
    ServiceStatus,
)
from ifg_guardian.plugins.ifg.env_reload.report import render_env_reload_markdown  # noqa: E402
from ifg_guardian.plugins.ifg.env_reload.stages import (  # noqa: E402
    HealthStage,
    InitStage,
    PreflightStage,
    ReloadStage,
    SummaryStage,
    VerifyStage,
)


def _intent_result(*, ok: bool = True, output: str = "", error: str = "") -> IntentResult:
    return IntentResult(intent=MagicMock(), ok=ok, output=output, error=error)


def _ctx(*, dry_run: bool = False, assume_yes: bool = True):
    from ifg_guardian.core.workflow.context import WorkflowContext
    from ifg_guardian.core.workflow.state import WorkflowStateMachine
    from ifg_guardian.core.workflow.transaction import WorkflowTransaction
    from ifg_guardian.plugins.ifg.env_reload.workflow import IFG_ENV_RELOAD_WORKFLOW

    transaction = WorkflowTransaction(
        workflow_id="ifg.env.reload-test",
        workflow_type="ifg.env.reload",
        plugin="ifg",
        execution_mode=ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE,
    )
    ctx = WorkflowContext(
        root=Path("/tmp"),
        workflow=IFG_ENV_RELOAD_WORKFLOW,
        transaction=transaction,
        mode=ExecutionMode.DRY_RUN if dry_run else ExecutionMode.LIVE,
        state_machine=WorkflowStateMachine(),
    )
    ctx.data["assume_yes"] = assume_yes
    ctx.data["deploy_executor_context"] = DeployExecutorContext(remote_path="/volume1/docker/ifg_v2/ifg_standalone")
    return ctx


class TestAggregation:
    def test_health_fail_blocked(self):
        state = EnvReloadState(
            compose_up_executed=True,
            service_statuses=[
                ServiceStatus("api", True, "running"),
                ServiceStatus("worker", True, "running"),
            ],
            health_ok=False,
        )
        assert aggregate_env_reload_status(state) == EnvReloadOverallStatus.BLOCKED
        assert exit_code_for_env_reload(
            EnvReloadState(overall_status=EnvReloadOverallStatus.BLOCKED)
        ) == 1

    def test_ready_when_all_pass(self):
        state = EnvReloadState(
            compose_up_executed=True,
            service_statuses=[
                ServiceStatus("api", True, "running"),
                ServiceStatus("worker", True, "running"),
            ],
            health_ok=True,
        )
        assert aggregate_env_reload_status(state) == EnvReloadOverallStatus.READY

    def test_dry_run_ready(self):
        state = EnvReloadState(dry_run=True, preflight_checks=[])
        assert aggregate_env_reload_status(state) == EnvReloadOverallStatus.READY

    def test_summarize_logs(self):
        raw = "line1\nline2\nerror: boom\n"
        summary = summarize_startup_logs(raw)
        assert len(summary) == 3


def _results(stage_id: str = "test") -> StageExecutionResults:
    return StageExecutionResults(stage_id=stage_id)


class TestStages:
    def test_init_requires_yes(self):
        ctx = _ctx(dry_run=False, assume_yes=False)
        result = InitStage().interpret(ctx, _results("init"))
        assert result.status.value == "fail"

    def test_preflight_dry_run_warn(self):
        ctx = _ctx(dry_run=True)
        InitStage().interpret(ctx, _results("init"))
        result = PreflightStage().interpret(ctx, _results("preflight"))
        assert result.status.value == "pass"
        state = ctx.data["env_reload_state"]
        assert all(c.status == EnvReloadStageStatus.WARN for c in state.preflight_checks)

    def test_reload_dry_run_simulated(self):
        ctx = _ctx(dry_run=True)
        InitStage().interpret(ctx, _results("init"))
        PreflightStage().interpret(ctx, _results("preflight"))
        result = ReloadStage().interpret(ctx, _results("reload"))
        assert result.status.value == "pass"
        assert "[dry-run]" in ctx.data["env_reload_state"].compose_up_output

    @patch("ifg_guardian.plugins.ifg.env_reload.stages._ssh")
    def test_preflight_live_ssh_fail(self, mock_ssh_factory):
        ssh = MagicMock()
        cfg = MagicMock()
        cfg.ssh_target = "user@ds723"
        cfg.env_file = "/volume1/docker/ifg_v2/ifg_standalone/.env.production"
        cfg.compose_file = "docker/docker-compose.prod.yml"
        ssh.deploy_context.config.return_value = cfg
        ssh.run_remote.side_effect = [
            _intent_result(ok=False, error="connection refused"),
            _intent_result(ok=False, error="missing"),
            _intent_result(ok=False, error="missing"),
        ]
        mock_ssh_factory.return_value = ssh

        ctx = _ctx(dry_run=False)
        InitStage().interpret(ctx, _results("init"))
        result = PreflightStage().interpret(ctx, _results("preflight"))
        assert result.status.value == "fail"
        state = ctx.data["env_reload_state"]
        assert state.preflight_has_fail()

    @patch("ifg_guardian.plugins.ifg.env_reload.stages._ssh")
    def test_reload_live_compose_up(self, mock_ssh_factory):
        ssh = MagicMock()
        cfg = MagicMock()
        cfg.ssh_target = "user@ds723"
        cfg.env_file = "/volume1/docker/ifg_v2/ifg_standalone/.env.production"
        cfg.compose_file = "docker/docker-compose.prod.yml"
        cfg.repo = "/volume1/docker/ifg_v2/ifg_standalone"
        ssh.deploy_context.config.return_value = cfg
        ssh.run_remote.return_value = _intent_result(ok=True, output="Container ifg-api-1 Started")
        mock_ssh_factory.return_value = ssh

        ctx = _ctx(dry_run=False)
        state = EnvReloadState()
        state.preflight_checks = [PreflightCheck("ssh", EnvReloadStageStatus.PASS, "ok")]
        ctx.data["env_reload_state"] = state

        result = ReloadStage().interpret(ctx, _results("reload"))
        assert result.status.value == "pass"
        assert state.compose_up_executed is True
        assert state.containers_restarted == ["api", "worker"]

    @patch("ifg_guardian.plugins.ifg.env_reload.stages._ssh")
    def test_health_fail(self, mock_ssh_factory):
        ssh = MagicMock()
        ssh.deploy_context.config.return_value = MagicMock()
        ssh.run_remote.return_value = _intent_result(ok=False, error="HTTP 502")
        mock_ssh_factory.return_value = ssh

        ctx = _ctx(dry_run=False)
        state = EnvReloadState(compose_up_executed=True)
        ctx.data["env_reload_state"] = state

        result = HealthStage().interpret(ctx, _results("health"))
        assert result.status.value == "fail"
        assert state.health_ok is False

    @patch("ifg_guardian.plugins.ifg.env_reload.stages._ssh")
    def test_verify_services(self, mock_ssh_factory):
        ssh = MagicMock()
        cfg = MagicMock()
        cfg.compose_file = "docker/docker-compose.prod.yml"
        cfg.env_file = ".env.production"
        ssh.deploy_context.config.return_value = cfg
        ssh.run_remote.return_value = _intent_result(
            ok=True,
            output="api\trunning\nworker\trunning\n",
        )
        mock_ssh_factory.return_value = ssh

        ctx = _ctx(dry_run=False)
        state = EnvReloadState(compose_up_executed=True)
        ctx.data["env_reload_state"] = state

        result = VerifyStage().interpret(ctx, _results("verify"))
        assert result.status.value == "pass"
        assert state.services_running()


class TestReport:
    def test_report_has_standard_sections(self):
        state = EnvReloadState(
            remote_host="user@ds723",
            remote_path="/volume1/docker/ifg_v2/ifg_standalone",
            env_file="/volume1/docker/ifg_v2/ifg_standalone/.env.production",
            env_file_exists=True,
            compose_file="docker/docker-compose.prod.yml",
            compose_up_executed=True,
            containers_restarted=["api", "worker"],
            service_statuses=[
                ServiceStatus("api", True, "running"),
                ServiceStatus("worker", True, "running"),
            ],
            preflight_checks=[
                PreflightCheck("ssh", EnvReloadStageStatus.PASS, "connected"),
            ],
            health_ok=True,
            health_detail='{"status":"ok"}',
            startup_logs_summary=["`api started`"],
            overall_status=EnvReloadOverallStatus.READY,
            operator_actions=build_operator_actions(
                EnvReloadState(compose_up_executed=True, health_ok=True, service_statuses=[
                    ServiceStatus("api", True, "running"),
                    ServiceStatus("worker", True, "running"),
                ])
            ),
        )
        md = render_env_reload_markdown(state)
        for section in STANDARD_SECTIONS:
            assert section in md
        assert "Containers restarted" in md
        assert "Environment reloaded" in md
        assert "Health" in md
        assert "Startup logs summary" in md

    def test_workflow_registered(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.env.reload")
            assert wf is not None
            assert wf.mutating is True
            assert wf.requires_yes is True
        finally:
            runtime.shutdown()
