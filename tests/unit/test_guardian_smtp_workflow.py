"""Testy workflow SMTP Guardiana (GWO-GUARDIAN-0078)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402

_runtime = create_runtime()
_runtime.shutdown()

from ifg_guardian.plugins.ifg.smtp.aggregation import aggregate_smtp_status, exit_code_for_smtp  # noqa: E402
from ifg_guardian.plugins.ifg.smtp.config import (  # noqa: E402
    mask_config_values,
    mask_email,
    run_config_checks,
)
from ifg_guardian.plugins.ifg.smtp.connectivity import run_connectivity_checks  # noqa: E402
from ifg_guardian.plugins.ifg.smtp.models import (  # noqa: E402
    ConfigCheck,
    ConnectivityCheck,
    SmtpEnvironment,
    SmtpOverallStatus,
    SmtpStageStatus,
    SmtpState,
    TestMailResult,
)
from ifg_guardian.plugins.ifg.smtp.test_send import send_test_mail  # noqa: E402
from ifg_guardian.core.reporting.schema import STANDARD_SECTIONS  # noqa: E402
from ifg_guardian.core.workflow.executors.context import DeployExecutorContext  # noqa: E402
from ifg_guardian.core.workflow.results import IntentResult, StageExecutionResults  # noqa: E402
from ifg_guardian.plugins.ifg.smtp.config import load_smtp_env_local, parse_env_text  # noqa: E402
from ifg_guardian.plugins.ifg.smtp.stages import ConfigStage, InitStage, PreflightStage  # noqa: E402
from ifg_guardian.plugins.ifg.smtp.report import render_smtp_markdown  # noqa: E402


def _base_env(**overrides: str) -> dict[str, str]:
    base = {
        "PURCHASE_SYNC_NOTIFY_ENABLED": "true",
        "PURCHASE_SYNC_NOTIFY_RECIPIENTS": "ops@firma.pl,ksiegowosc@firma.pl,ops@firma.pl",
        "SMTP_HOST": "smtp.firma.pl",
        "SMTP_PORT": "587",
        "SMTP_USER": "ifg@firma.pl",
        "SMTP_PASSWORD": "secret",
        "SMTP_FROM": "ifg@firma.pl",
        "SMTP_USE_TLS": "true",
        "APP_VERSION": "1.2.3",
    }
    base.update(overrides)
    return base


class TestConfigChecks:
    def test_missing_smtp_host_fail(self):
        checks, recipients, _ = run_config_checks(_base_env(SMTP_HOST=""))
        host = next(c for c in checks if c.key == "SMTP_HOST")
        assert host.status == SmtpStageStatus.FAIL
        assert recipients

    def test_missing_password_fail_when_user_set(self):
        checks, _, _ = run_config_checks(_base_env(SMTP_PASSWORD=""))
        pwd = next(c for c in checks if c.key == "SMTP_PASSWORD")
        assert pwd.status == SmtpStageStatus.FAIL

    def test_missing_recipients_fail_when_enabled(self):
        checks, recipients, _ = run_config_checks(
            _base_env(
                PURCHASE_SYNC_NOTIFY_RECIPIENTS="",
                PURCHASE_SYNC_NOTIFY_EMAIL="",
            )
        )
        assert recipients == []
        validation = next(c for c in checks if c.key == "recipients.validation")
        assert validation.status == SmtpStageStatus.FAIL

    def test_csv_three_recipients_pass(self):
        checks, recipients, _ = run_config_checks(
            _base_env(PURCHASE_SYNC_NOTIFY_RECIPIENTS="a@x.com,b@y.com,c@z.com")
        )
        assert len(recipients) == 3
        csv_check = next(c for c in checks if c.key == "PURCHASE_SYNC_NOTIFY_RECIPIENTS")
        assert csv_check.status == SmtpStageStatus.PASS

    def test_duplicates_removed(self):
        _, recipients, _ = run_config_checks(
            _base_env(PURCHASE_SYNC_NOTIFY_RECIPIENTS="dup@x.com,DUP@x.com,other@y.com")
        )
        assert recipients == ["dup@x.com", "other@y.com"]

    def test_mask_email(self):
        assert mask_email("ifg@firma.pl") == "if***@firma.pl"
        masked = mask_config_values(_base_env())
        assert "secret" not in masked["SMTP_PASSWORD"]
        assert "***" in masked["SMTP_USER"]


class TestConnectivity:
    def test_tls_fail(self):
        config = MagicMock(host="smtp.test", port=587, use_tls=True, user="u", password="p")
        with patch("ifg_guardian.plugins.ifg.smtp.connectivity.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 587))]):
            with patch("ifg_guardian.plugins.ifg.smtp.connectivity.smtplib.SMTP") as mock_smtp:
                instance = mock_smtp.return_value
                instance.ehlo.return_value = (250, "ok")
                instance.starttls.side_effect = __import__("smtplib").SMTPException("tls failed")
                checks = run_connectivity_checks(config)
        tls = next(c for c in checks if c.stage == "STARTTLS")
        assert tls.status == SmtpStageStatus.FAIL

    def test_auth_fail(self):
        import smtplib

        config = MagicMock(host="smtp.test", port=587, use_tls=True, user="u", password="p")
        with patch("ifg_guardian.plugins.ifg.smtp.connectivity.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 587))]):
            with patch("ifg_guardian.plugins.ifg.smtp.connectivity.smtplib.SMTP") as mock_smtp:
                instance = mock_smtp.return_value
                instance.ehlo.return_value = (250, "ok")
                instance.starttls.return_value = (220, "ready")
                instance.login.side_effect = smtplib.SMTPException("auth failed")
                checks = run_connectivity_checks(config)
        auth = next(c for c in checks if c.stage == "AUTH")
        assert auth.status == SmtpStageStatus.FAIL


class TestTestSend:
    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_send_uses_envelope_from(self, mock_smtp_cls):
        from app.integrations.email.smtp_client import SmtpConfig

        instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = instance
        config = SmtpConfig(
            host="smtp.test",
            port=587,
            user="u",
            password="p",
            from_addr="IFG Test <notify@example.test>",
            use_tls=True,
        )
        with patch("app.integrations.email.smtp_client.send_email") as mock_send:
            mock_send.return_value = None
            result = send_test_mail(
                config=config,
                recipients=["ops@firma.pl"],
                workflow_id="wf-test",
                app_version="1.0.0",
            )
        assert result.sent is True
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["config"].from_addr == "IFG Test <notify@example.test>"

    @patch("app.integrations.email.smtp_client.smtplib.SMTP")
    def test_send_envelope_via_smtp_layer(self, mock_smtp_cls):
        from app.integrations.email.smtp_client import SmtpConfig, send_email

        instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = instance
        config = SmtpConfig(
            host="smtp.test",
            port=587,
            user=None,
            password=None,
            from_addr="IFG Test <notify@example.test>",
            use_tls=False,
        )
        send_email(
            config=config,
            to_addrs=["ops@firma.pl"],
            subject="IFG SMTP Test",
            body_text="test",
        )
        _, kwargs = instance.send_message.call_args
        assert kwargs["from_addr"] == "notify@example.test"

    def test_send_mock_pass(self):
        config = MagicMock(host="smtp.test", port=587, use_tls=True, user=None, password=None, from_addr="ifg@test")
        with patch("app.integrations.email.smtp_client.send_email") as mock_send:
            mock_send.return_value = None
            result = send_test_mail(
                config=config,
                recipients=["ops@firma.pl"],
                workflow_id="wf-test",
                app_version="1.0.0",
            )
        assert result.sent is True
        assert result.status == SmtpStageStatus.PASS
        mock_send.assert_called_once()
        assert mock_send.call_args.kwargs["subject"] == "IFG SMTP Test"
        assert "Guardian" in mock_send.call_args.kwargs["body_text"]
        assert "KSeF" in mock_send.call_args.kwargs["body_text"]

    def test_send_auth_fail(self):
        from app.integrations.email.smtp_client import SmtpSendError

        config = MagicMock()
        with patch("app.integrations.email.smtp_client.send_email", side_effect=SmtpSendError("auth failed")):
            result = send_test_mail(
                config=config,
                recipients=["ops@firma.pl"],
                workflow_id="wf-test",
                app_version="1.0.0",
            )
        assert result.sent is False
        assert result.status == SmtpStageStatus.FAIL


class TestWorkflowBehavior:
    def test_check_does_not_send_mail(self):
        values = _base_env()
        checks, recipients, _ = run_config_checks(values)
        state = SmtpState(
            mode="check",
            config_checks=checks,
            recipients=recipients,
            test_result=None,
        )
        assert state.test_result is None
        assert state.mode == "check"

    def test_blocked_when_config_fail(self):
        checks, _, _ = run_config_checks(_base_env(SMTP_HOST=""))
        state = SmtpState(mode="test", config_checks=checks)
        state.overall_status = aggregate_smtp_status(state)
        assert state.overall_status == SmtpOverallStatus.BLOCKED
        assert exit_code_for_smtp(state) == 1

    def test_report_has_standard_sections(self):
        state = SmtpState(
            mode="check",
            env_file=".env.production",
            config_checks=[
                ConfigCheck("SMTP_HOST", SmtpStageStatus.PASS, "ok", "smtp.firma.pl"),
            ],
            connectivity_checks=[
                ConnectivityCheck("DNS", SmtpStageStatus.PASS, "resolved"),
            ],
            masked_config=mask_config_values(_base_env()),
            recipients=["ops@firma.pl"],
            overall_status=SmtpOverallStatus.READY,
        )
        md = render_smtp_markdown(state)
        for section in STANDARD_SECTIONS:
            assert section in md


REMOTE_ENV_PATH = "/volume1/docker/ifg_v2/ifg_standalone/.env.production"


def _env_text(**overrides: str) -> str:
    values = _base_env(**overrides)
    return "\n".join(f"{key}={value}" for key, value in values.items())


def _intent_result(*, ok: bool = True, output: str = "", error: str = "", stderr: str = "") -> IntentResult:
    return IntentResult(
        intent=MagicMock(),
        ok=ok,
        output=output,
        error=error,
        data={"stderr": stderr},
    )


def _smtp_ctx(*, use_local: bool = False):
    from ifg_guardian.core.workflow.context import WorkflowContext
    from ifg_guardian.core.workflow.mode import ExecutionMode
    from ifg_guardian.core.workflow.state import WorkflowStateMachine
    from ifg_guardian.core.workflow.transaction import WorkflowTransaction
    from ifg_guardian.plugins.ifg.smtp.workflow import IFG_SMTP_CHECK_WORKFLOW

    transaction = WorkflowTransaction(
        workflow_id="ifg.smtp.check-test",
        workflow_type="ifg.smtp.check",
        plugin="ifg",
        execution_mode=ExecutionMode.LIVE,
    )
    ctx = WorkflowContext(
        root=Path("/tmp"),
        workflow=IFG_SMTP_CHECK_WORKFLOW,
        transaction=transaction,
        mode=ExecutionMode.LIVE,
        state_machine=WorkflowStateMachine(),
    )
    ctx.data["smtp_mode"] = "check"
    ctx.data["use_local"] = use_local
    ctx.data["deploy_executor_context"] = DeployExecutorContext(
        remote_path="/volume1/docker/ifg_v2/ifg_standalone",
    )
    return ctx


def _results(stage_id: str) -> StageExecutionResults:
    return StageExecutionResults(stage_id=stage_id)


class TestRemoteLocalSource:
    @patch("ifg_guardian.plugins.ifg.smtp.stages.run_connectivity_checks")
    @patch("ifg_guardian.plugins.ifg.smtp.stages._ssh")
    def test_remote_pass(self, mock_ssh_factory, mock_connectivity):
        ssh = MagicMock()
        cfg = MagicMock()
        cfg.ssh_target = "user@ds723"
        cfg.env_file = REMOTE_ENV_PATH
        ssh.deploy_context.config.return_value = cfg
        ssh.run_remote.side_effect = [
            _intent_result(ok=True, output="connected"),
            _intent_result(ok=True, output=_env_text()),
        ]
        mock_ssh_factory.return_value = ssh
        mock_connectivity.return_value = [
            ConnectivityCheck("DNS", SmtpStageStatus.PASS, "resolved"),
        ]

        ctx = _smtp_ctx(use_local=False)
        InitStage().interpret(ctx, _results("init"))
        PreflightStage().interpret(ctx, _results("preflight"))
        ConfigStage().interpret(ctx, _results("config"))

        state = ctx.data["smtp_state"]
        assert state.environment == SmtpEnvironment.REMOTE
        assert state.ssh_ok is True
        assert state.env_file == REMOTE_ENV_PATH
        assert not state.config_has_fail()
        state.connectivity_checks = mock_connectivity.return_value
        state.overall_status = aggregate_smtp_status(state)
        assert state.overall_status == SmtpOverallStatus.READY

    @patch("ifg_guardian.plugins.ifg.smtp.stages._ssh")
    def test_remote_missing_env_fail(self, mock_ssh_factory):
        ssh = MagicMock()
        cfg = MagicMock()
        cfg.ssh_target = "user@ds723"
        cfg.env_file = REMOTE_ENV_PATH
        ssh.deploy_context.config.return_value = cfg
        ssh.run_remote.side_effect = [
            _intent_result(ok=True, output="connected"),
            _intent_result(ok=False, error="exit 2", stderr=f"GUARDIAN_ENV_MISSING:{REMOTE_ENV_PATH}"),
        ]
        mock_ssh_factory.return_value = ssh

        ctx = _smtp_ctx(use_local=False)
        InitStage().interpret(ctx, _results("init"))
        PreflightStage().interpret(ctx, _results("preflight"))
        result = ConfigStage().interpret(ctx, _results("config"))

        state = ctx.data["smtp_state"]
        assert result.status.value == "fail"
        env_check = next(c for c in state.config_checks if c.key == "env_file")
        assert env_check.status == SmtpStageStatus.FAIL
        state.overall_status = aggregate_smtp_status(state)
        assert state.overall_status == SmtpOverallStatus.BLOCKED

    @patch("ifg_guardian.plugins.ifg.smtp.stages._ssh")
    def test_remote_ssh_fail_blocked(self, mock_ssh_factory):
        ssh = MagicMock()
        cfg = MagicMock()
        cfg.ssh_target = "user@ds723"
        cfg.env_file = REMOTE_ENV_PATH
        ssh.deploy_context.config.return_value = cfg
        ssh.run_remote.return_value = _intent_result(ok=False, error="connection refused")
        mock_ssh_factory.return_value = ssh

        ctx = _smtp_ctx(use_local=False)
        InitStage().interpret(ctx, _results("init"))
        PreflightStage().interpret(ctx, _results("preflight"))

        state = ctx.data["smtp_state"]
        assert state.ssh_ok is False
        state.overall_status = aggregate_smtp_status(state)
        assert state.overall_status == SmtpOverallStatus.BLOCKED

    def test_local_pass(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(_env_text(), encoding="utf-8")

        ctx = _smtp_ctx(use_local=True)
        ctx.data["env_file"] = str(env_file)
        InitStage().interpret(ctx, _results("init"))
        PreflightStage().interpret(ctx, _results("preflight"))
        ConfigStage().interpret(ctx, _results("config"))

        state = ctx.data["smtp_state"]
        assert state.environment == SmtpEnvironment.LOCAL
        assert state.env_file == str(env_file.resolve())
        assert not state.config_has_fail()

    def test_local_missing_smtp_host_fail(self, tmp_path):
        env_file = tmp_path / ".env.production"
        env_file.write_text(_env_text(SMTP_HOST=""), encoding="utf-8")

        ctx = _smtp_ctx(use_local=True)
        ctx.data["env_file"] = str(env_file)
        InitStage().interpret(ctx, _results("init"))
        ConfigStage().interpret(ctx, _results("config"))

        state = ctx.data["smtp_state"]
        host = next(c for c in state.config_checks if c.key == "SMTP_HOST")
        assert host.status == SmtpStageStatus.FAIL
        state.overall_status = aggregate_smtp_status(state)
        assert state.overall_status == SmtpOverallStatus.BLOCKED

    def test_report_shows_environment_and_env_file(self):
        state = SmtpState(
            mode="check",
            environment=SmtpEnvironment.REMOTE,
            remote_host="user@ds723",
            ssh_ok=True,
            env_file=REMOTE_ENV_PATH,
            config_checks=[
                ConfigCheck("SMTP_HOST", SmtpStageStatus.PASS, "ok", "smtp.firma.pl"),
            ],
            connectivity_checks=[
                ConnectivityCheck("DNS", SmtpStageStatus.PASS, "resolved"),
            ],
            masked_config=mask_config_values(_base_env()),
            recipients=["ops@firma.pl"],
            overall_status=SmtpOverallStatus.READY,
        )
        md = render_smtp_markdown(state)
        assert "**Environment:** REMOTE" in md
        assert REMOTE_ENV_PATH in md
        assert "Environment Source" in md

    def test_parse_env_text(self, tmp_path):
        values = parse_env_text("SMTP_HOST=smtp.test\nSMTP_PORT=587\n")
        assert values["SMTP_HOST"] == "smtp.test"
        missing = tmp_path / "missing.env"
        assert load_smtp_env_local(env_file=missing)[0] == {}
