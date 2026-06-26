"""IFG deploy run workflow tests (M3)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.engine import ExecutionEngine
from guardian_platform.core.workflow.state import WorkflowState
from guardian_platform.profiles.ifg.deploy.models import DeployRunState, StepStatus
from guardian_platform.profiles.ifg.deploy.pipeline import build_deploy_pipeline
from guardian_platform.profiles.ifg.deploy.report import exit_code_for_deploy, render_markdown, render_terminal
from guardian_platform.profiles.ifg.deploy.runner import execute_deploy_run, run_deploy_run
from guardian_platform.profiles.ifg.deploy.service import get_deploy_state
from guardian_platform.profiles.ifg.infra.exec import ExecResult, run_local
from guardian_platform.profiles.ifg.lib.deploy_reporting import deploy_report_path
from guardian_platform.profiles.ifg.workflows.deploy_run import IFG_DEPLOY_RUN_WORKFLOW
from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.core.runtime.mode import ExecutionMode as EM
from tests.guardian_platform.conftest import run_main


class TestDeployWorkflowDefinition:
    def test_workflow_id(self):
        assert IFG_DEPLOY_RUN_WORKFLOW.id == "ifg.deploy.run"

    def test_workflow_mutating(self):
        assert IFG_DEPLOY_RUN_WORKFLOW.mutating is True

    def test_workflow_requires_yes(self):
        assert IFG_DEPLOY_RUN_WORKFLOW.requires_yes is True

    def test_stage_ids(self):
        ids = [s.id for s in IFG_DEPLOY_RUN_WORKFLOW.stages]
        assert ids == ["init", "repository", "git_validation", "execution", "deploy_report"]

    def test_registered_in_runtime(self, platform_runtime):
        assert platform_runtime.workflows.get("ifg.deploy.run") is not None


class TestDeployPipeline:
    def test_pipeline_has_eight_steps(self):
        steps = build_deploy_pipeline(remote_host="ds723", remote_path="/remote")
        assert len(steps) == 8

    def test_pipeline_includes_backup(self):
        actions = [a for a, _, _ in build_deploy_pipeline(remote_host="h", remote_path="/r")]
        assert "backup database" in actions

    def test_pipeline_includes_alembic(self):
        actions = [a for a, _, _ in build_deploy_pipeline(remote_host="h", remote_path="/r")]
        assert "alembic upgrade" in actions

    def test_pipeline_includes_frontend_build(self):
        actions = [a for a, _, _ in build_deploy_pipeline(remote_host="h", remote_path="/r")]
        assert "frontend build" in actions

    def test_pipeline_includes_health(self):
        actions = [a for a, _, _ in build_deploy_pipeline(remote_host="h", remote_path="/r")]
        assert "health verification" in actions

    def test_pipeline_includes_smoke(self):
        actions = [a for a, _, _ in build_deploy_pipeline(remote_host="h", remote_path="/r")]
        assert "smoke tests" in actions


class TestExecHelpers:
    def test_run_local_dry_run_simulates(self):
        r = run_local(["git", "status"], dry_run=True)
        assert r.simulated is True
        assert r.ok is True

    def test_run_local_live_runs(self, git_repo, monkeypatch):
        monkeypatch.chdir(git_repo)
        r = run_local(["git", "status", "--short"], dry_run=False, mutating=False)
        assert r.simulated is False


class TestDeployModels:
    def test_deploy_state_defaults(self):
        s = DeployRunState()
        assert s.dry_run is True
        assert s.rollback_available is False

    def test_exit_code_blocked(self):
        s = DeployRunState(blockers=["x"])
        assert exit_code_for_deploy(s) == 1

    def test_exit_code_ok(self):
        s = DeployRunState()
        assert exit_code_for_deploy(s) == 0

    def test_report_markdown(self):
        s = DeployRunState(rollback_available=True)
        tx = WorkflowTransaction("id", "ifg.deploy.run", "ifg", EM.LIVE)
        out = render_markdown(s, transaction=tx)
        assert "Deploy Run" in out


class TestDeployRunner:
    def test_live_without_yes_returns_2(self):
        assert run_deploy_run(dry_run=False, assume_yes=False) == 2

    @patch("guardian_platform.profiles.ifg.deploy.stages.run_local")
    def test_dry_run_completes(self, mock_run, production_git_repo, monkeypatch):
        monkeypatch.chdir(production_git_repo)
        mock_run.return_value = ExecResult(ok=True, simulated=True, output="sim")
        code = run_deploy_run(dry_run=True, output_format="terminal")
        assert code == 0

    def test_execute_dry_run_in_git_repo(self, production_git_repo, monkeypatch, tmp_path):
        monkeypatch.chdir(production_git_repo)
        with patch("guardian_platform.profiles.ifg.deploy.stages.run_local") as mock_run:
            mock_run.return_value = ExecResult(ok=True, simulated=True, output="sim")
            with patch("guardian_platform.profiles.ifg.deploy.stages.deploy_report_path") as rp:
                rp.return_value = tmp_path / "report.md"
                ctx = execute_deploy_run(dry_run=True, assume_yes=False)
        assert ctx.state_machine.state == WorkflowState.SUCCESS
        state = get_deploy_state(ctx)
        assert state.rollback_available is True


class TestDeployCLI:
    def test_deploy_run_dry_run_cli(self, production_git_repo, monkeypatch):
        monkeypatch.chdir(production_git_repo)
        with patch("guardian_platform.profiles.ifg.deploy.stages.run_local") as mock_run:
            mock_run.return_value = ExecResult(ok=True, simulated=True, output="sim")
            code, out = run_main(["--dry-run", "ifg", "deploy", "run"])
        assert code == 0
        assert "DRY-RUN" in out

    def test_deploy_run_blocked_without_yes(self):
        code, out = run_main(["ifg", "deploy", "run"])
        assert code == 2
        assert "requires --yes" in out

    def test_deploy_run_yes_with_mock(self, production_git_repo, monkeypatch):
        monkeypatch.chdir(production_git_repo)
        with patch("guardian_platform.profiles.ifg.deploy.stages.run_local") as mock_run:
            mock_run.return_value = ExecResult(ok=True, simulated=False, output='{"status":"ok"}')
            code, _ = run_main(["--yes", "ifg", "deploy", "run"])
        assert code in (0, 1)

    def test_deploy_report_path_format(self):
        p = deploy_report_path()
        assert p.name.startswith("guardian_deploy_")
        assert p.suffix == ".md"


class TestDeployHaltOnFailure:
    @patch("guardian_platform.profiles.ifg.deploy.stages.run_local")
    def test_health_failure_halts(self, mock_run, production_git_repo, monkeypatch, tmp_path):
        monkeypatch.chdir(production_git_repo)

        def side_effect(cmd, **kwargs):
            if "health" in str(cmd):
                return ExecResult(ok=False, simulated=False, error="health fail")
            return ExecResult(ok=True, simulated=True, output="ok")

        mock_run.side_effect = side_effect
        with patch("guardian_platform.profiles.ifg.deploy.stages.deploy_report_path") as rp:
            rp.return_value = tmp_path / "report.md"
            ctx = execute_deploy_run(dry_run=True)
        state = get_deploy_state(ctx)
        assert state.halted is True
