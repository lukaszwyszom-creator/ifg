"""Unit tests for frontend Artifact Verification Gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.frontend_artifacts import (  # noqa: E402
    build_rsync_dist_command,
    parse_artifact_gate_output,
    remote_artifact_verify_script,
    verify_local_dist,
)
from ifg_guardian.core.workflow.executors.compose_executor import ComposeExecutor  # noqa: E402
from ifg_guardian.core.workflow.executors import DeployExecutorContext, IntentExecutor  # noqa: E402
from ifg_guardian.core.workflow.executors.router import DeployCommandKind, classify_deploy_command  # noqa: E402
from ifg_guardian.core.workflow.intents import LocalExecIntent  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402


class TestVerifyLocalDist:
    def test_go_when_index_and_assets_present(self, tmp_path: Path):
        dist = tmp_path / "frontend-react" / "dist"
        assets = dist / "assets"
        assets.mkdir(parents=True)
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        (assets / "index-abc.js").write_text("console.log(1)", encoding="utf-8")

        result = verify_local_dist(tmp_path)
        assert result.is_go
        assert result.js_count == 1

    def test_no_go_missing_index_html(self, tmp_path: Path):
        dist = tmp_path / "frontend-react" / "dist" / "assets"
        dist.mkdir(parents=True)
        (dist / "index-abc.js").write_text("x", encoding="utf-8")

        result = verify_local_dist(tmp_path)
        assert not result.is_go
        assert "index.html" in result.message

    def test_no_go_missing_assets_js(self, tmp_path: Path):
        dist = tmp_path / "frontend-react" / "dist"
        dist.mkdir(parents=True)
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")

        result = verify_local_dist(tmp_path)
        assert not result.is_go


class TestParseArtifactGateOutput:
    def test_parses_go(self):
        output = (
            "ARTIFACT_GATE_STATUS=GO\n"
            "ARTIFACT_GATE_MESSAGE=frontend artifacts OK\n"
            "ARTIFACT_JS_COUNT=2\n"
        )
        gate = parse_artifact_gate_output(output)
        assert gate.is_go

    def test_parses_no_go(self):
        output = (
            "ARTIFACT_GATE_STATUS=NO_GO\n"
            "ARTIFACT_GATE_MESSAGE=missing index.html\n"
        )
        gate = parse_artifact_gate_output(output)
        assert not gate.is_go
        assert gate.status == "NO_GO"


class TestCommandRouting:
    def test_classify_artifact_gate_commands(self):
        assert classify_deploy_command("ifg_guardian_frontend_artifact_gate local") == DeployCommandKind.ARTIFACT_GATE_LOCAL
        assert classify_deploy_command("ifg_guardian_frontend_artifact_gate remote") == DeployCommandKind.ARTIFACT_GATE_REMOTE

    def test_rsync_includes_ssh(self):
        cmd = build_rsync_dist_command()
        assert "rsync" in cmd
        assert "ssh -p" in cmd


class TestIntentExecutorArtifactGate:
    def test_local_gate_no_go_without_dist(self, tmp_path: Path):
        executor = IntentExecutor(root=tmp_path)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "ifg_guardian_frontend_artifact_gate local"],
            mutating=True,
        )
        result = executor.execute(intent, ExecutionMode.LIVE)
        assert not result.ok
        assert result.data.get("artifact_gate") == "NO_GO"

    def test_compose_up_blocked_when_remote_gate_fails(self, tmp_path: Path):
        ctx = DeployExecutorContext(remote_host="ds723", remote_path="/volume1/repo")
        compose = ComposeExecutor(root=tmp_path, deploy_context=ctx)
        intent = LocalExecIntent(
            command=["/bin/sh", "-c", "docker compose -f docker/docker-compose.prod.yml up -d"],
            mutating=True,
        )
        with patch.object(compose._ssh, "run_remote") as remote:
            remote.return_value = MagicMock(
                ok=False,
                output="ARTIFACT_GATE_STATUS=NO_GO\nARTIFACT_GATE_MESSAGE=missing index.html\n",
                error="exit 1",
                data={},
                intent=intent,
            )
            result = compose.execute_up(intent, intent.command[2])
        assert not result.ok
        assert result.data.get("artifact_gate") == "NO_GO"
        assert remote.call_count == 1

    def test_remote_verify_script_checks_index_and_assets(self):
        script = remote_artifact_verify_script("/repo")
        assert "index.html" in script
        assert "assets" in script
        assert "ARTIFACT_GATE_STATUS=GO" in script
