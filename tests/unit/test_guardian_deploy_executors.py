"""Unit tests for deploy executors (Sprint 5C)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.workflow.executors import (  # noqa: E402
    ComposeExecutor,
    DeployExecutorContext,
    DockerExecutor,
    HTTPExecutor,
    IntentExecutor,
    LocalExecutor,
    SSHExecutor,
)
from ifg_guardian.core.workflow.executors.router import (  # noqa: E402
    DeployCommandKind,
    classify_deploy_command,
)
from ifg_guardian.core.workflow.intents import LocalExecIntent  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402


class TestDeployCommandRouter:
    @pytest.mark.parametrize(
        ("command", "kind"),
        [
            ("git pull origin production", DeployCommandKind.LOCAL_GIT),
            ("cd frontend-react && npm run build", DeployCommandKind.LOCAL_NPM),
            ("ifg_guardian_frontend_artifact_gate local", DeployCommandKind.ARTIFACT_GATE_LOCAL),
            ("ifg_guardian_frontend_artifact_gate remote", DeployCommandKind.ARTIFACT_GATE_REMOTE),
            ("python3 scripts/ifg_guardian_frontend_artifact_gate.py local", DeployCommandKind.ARTIFACT_GATE_LOCAL),
            ("python3 scripts/ifg_guardian_frontend_artifact_gate.py remote", DeployCommandKind.ARTIFACT_GATE_REMOTE),
            ("rsync -av dist/ host:/path/", DeployCommandKind.RSYNC),
            ("docker compose -f docker/docker-compose.prod.yml build api worker", DeployCommandKind.DOCKER_BUILD),
            ("docker compose -f docker/docker-compose.prod.yml up -d", DeployCommandKind.COMPOSE_UP),
            ("alembic upgrade head", DeployCommandKind.ALEMBIC),
            ("curl -sS http://127.0.0.1:8000/health", DeployCommandKind.HTTP_CHECK),
            ("docker compose -f docker/docker-compose.prod.yml logs --tail=50 api worker", DeployCommandKind.COMPOSE_LOGS),
        ],
    )
    def test_classify(self, command: str, kind: DeployCommandKind):
        assert classify_deploy_command(command) == kind


class TestDryRunRegression:
    def test_intent_executor_simulates_mutating_intents(self):
        executor = IntentExecutor(root=Path("."))
        intent = LocalExecIntent(command=["/bin/sh", "-c", "docker compose build api"], mutating=True)
        result = executor.execute(intent, ExecutionMode.DRY_RUN)
        assert result.ok
        assert result.simulated
        assert "dry-run" in result.output


class TestLocalExecutor:
    def test_executes_command_in_live_mode(self, tmp_path: Path):
        executor = LocalExecutor(root=tmp_path)
        intent = LocalExecIntent(command=["/bin/echo", "hello"], mutating=True)
        result = executor.execute(intent)
        assert result.ok
        assert result.output == "hello"


class TestSSHExecutor:
    def test_run_remote_success(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="testhost", remote_path="/repo")
        ssh = SSHExecutor(root=tmp_path, deploy_context=ctx)
        with patch("ifg_guardian.core.workflow.executors.ssh_executor.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            result = ssh.run_remote("echo test\n", label="test")
        assert result.ok
        assert result.output == "ok"
        assert "testhost" in ctx.executed_commands[0]


class TestDockerExecutor:
    def test_build_delegates_to_ssh(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        docker = DockerExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "docker compose -f docker/docker-compose.prod.yml build api worker"],
            mutating=True,
        )
        with patch.object(SSHExecutor, "run_remote") as remote:
            remote.return_value = MagicMock(ok=True, output="built", error="", data={}, intent=intent)
            result = docker.execute_build(intent, intent.command[2])
        assert result.ok
        remote.assert_called_once()
        assert "build api worker" in remote.call_args[0][0]


class TestComposeExecutor:
    def test_up_blocked_without_artifacts(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        compose = ComposeExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "docker compose -f docker/docker-compose.prod.yml up -d"],
            mutating=True,
        )
        with patch.object(SSHExecutor, "run_remote") as remote:
            remote.return_value = MagicMock(
                ok=False,
                output="ARTIFACT_GATE_STATUS=NO_GO\n",
                error="exit 1",
                data={},
                intent=intent,
            )
            result = compose.execute_up(intent, intent.command[2])
        assert not result.ok
        assert result.data.get("artifact_gate") == "NO_GO"
        assert remote.call_count == 1

    def test_up_and_ps(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        compose = ComposeExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "docker compose -f docker/docker-compose.prod.yml up -d"],
            mutating=True,
        )
        with patch.object(SSHExecutor, "run_remote") as remote:
            remote.side_effect = [
                MagicMock(ok=True, output="ARTIFACT_GATE_STATUS=GO\n", error="", data={}, intent=intent),
                MagicMock(ok=True, output="up ok", error="", data={}, intent=intent),
                MagicMock(ok=True, output="api running", error="", data={}, intent=intent),
            ]
            result = compose.execute_up(intent, intent.command[2])
        assert result.ok
        assert result.data.get("containers") == "api running"
        assert remote.call_count == 3


class TestHTTPExecutor:
    def test_health_via_ssh(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        http = HTTPExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "curl -sS http://127.0.0.1:8000/health"],
            mutating=True,
        )
        with patch.object(SSHExecutor, "run_remote") as remote:
            remote.return_value = MagicMock(
                ok=True,
                output='{"status":"ok"}',
                error="",
                data={},
                intent=intent,
            )
            result = http.execute_check(intent, intent.command[2])
        assert result.ok
        assert "status" in result.output


class TestIntentExecutorLiveRouting:
    def test_live_docker_build_uses_ssh_not_local_subprocess(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "docker compose -f docker/docker-compose.prod.yml build api worker"],
            mutating=True,
        )
        with patch("ifg_guardian.core.workflow.executors.local_executor.subprocess.run") as run:
            with patch.object(DockerExecutor, "execute_build") as build:
                build.return_value = MagicMock(ok=True, output="built", simulated=False, error="", data={})
                result = executor.execute(intent, ExecutionMode.LIVE)
        run.assert_not_called()
        build.assert_called_once()
        assert result.ok

    def test_live_alembic_runs_backup_first(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        executor = IntentExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(command=["/bin/sh", "-c", "alembic upgrade head"], mutating=True)
        with patch.object(SSHExecutor, "run_backup_before_migration") as backup:
            with patch.object(SSHExecutor, "run_remote") as remote:
                backup.return_value = MagicMock(ok=True, output="backup=ok", error="", data={}, intent=intent)
                remote.return_value = MagicMock(ok=True, output="migrated", error="", data={}, intent=intent)
                result = executor.execute(intent, ExecutionMode.LIVE)
        backup.assert_called_once()
        remote.assert_called_once()
        assert result.ok
