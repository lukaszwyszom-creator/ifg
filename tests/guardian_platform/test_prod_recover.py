"""IFG prod recover workflow tests (M3)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from guardian_platform.core.runtime.mode import ExecutionMode as EM
from guardian_platform.core.workflow.context import WorkflowTransaction
from guardian_platform.core.workflow.state import WorkflowState
from guardian_platform.profiles.ifg.infra.exec import ExecResult
from guardian_platform.profiles.ifg.lib.deploy_reporting import recover_report_path
from guardian_platform.profiles.ifg.recover.models import RecoverState
from guardian_platform.profiles.ifg.recover.report import exit_code_for_recover, render_markdown, render_terminal
from guardian_platform.profiles.ifg.recover.runner import execute_prod_recover, run_prod_recover
from guardian_platform.profiles.ifg.recover.service import get_recover_state
from guardian_platform.profiles.ifg.workflows.prod_recover import IFG_PROD_RECOVER_WORKFLOW
from tests.guardian_platform.conftest import run_main


class TestRecoverWorkflowDefinition:
    def test_workflow_id(self):
        assert IFG_PROD_RECOVER_WORKFLOW.id == "ifg.prod.recover"

    def test_workflow_mutating(self):
        assert IFG_PROD_RECOVER_WORKFLOW.mutating is True

    def test_stage_count(self):
        assert len(IFG_PROD_RECOVER_WORKFLOW.stages) == 8

    def test_stage_ids(self):
        ids = [s.id for s in IFG_PROD_RECOVER_WORKFLOW.stages]
        assert "restart_services" in ids
        assert "ksef_verification" in ids

    def test_registered(self, platform_runtime):
        assert platform_runtime.workflows.get("ifg.prod.recover") is not None


class TestRecoverModels:
    def test_defaults(self):
        s = RecoverState()
        assert s.dry_run is True

    def test_exit_code_aborted(self):
        s = RecoverState(aborted=True)
        assert exit_code_for_recover(s) == 1

    def test_exit_code_ok(self):
        s = RecoverState(health_ok=True)
        assert exit_code_for_recover(s) == 0

    def test_report_markdown(self):
        s = RecoverState(remote_host="ds723", git_branch="production")
        tx = WorkflowTransaction("id", "ifg.prod.recover", "ifg", EM.LIVE)
        assert "Prod Recover" in render_markdown(s, transaction=tx)


class TestRecoverRunner:
    def test_live_without_yes(self):
        assert run_prod_recover(dry_run=False, assume_yes=False) == 2

    def test_dry_run_completes(self):
        code = run_prod_recover(dry_run=True)
        assert code == 0

    def test_execute_dry_run_success(self, tmp_path):
        with patch("guardian_platform.profiles.ifg.recover.stages.recover_report_path") as rp:
            rp.return_value = tmp_path / "recover.md"
            ctx = execute_prod_recover(dry_run=True)
        assert ctx.state_machine.state == WorkflowState.SUCCESS
        state = get_recover_state(ctx)
        assert state.dry_run is True


class TestRecoverCLI:
    def test_prod_recover_dry_run(self):
        code, out = run_main(["--dry-run", "ifg", "prod", "recover"])
        assert code == 0
        assert "DRY-RUN" in out

    def test_prod_recover_blocked_without_yes(self):
        code, out = run_main(["ifg", "prod", "recover"])
        assert code == 2
        assert "requires --yes" in out

    def test_prod_recover_command_registered(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["prod", "recover"])
        assert spec is not None
        assert spec.mutating is True

    def test_recover_report_path(self):
        p = recover_report_path()
        assert p.name.startswith("guardian_recover_")


class TestRecoverLiveMocked:
    @patch("guardian_platform.profiles.ifg.recover.stages.run_remote")
    @patch("guardian_platform.profiles.ifg.recover.stages.remote_git")
    @patch("guardian_platform.profiles.ifg.recover.stages.remote_compose_ps")
    @patch("guardian_platform.profiles.ifg.recover.stages.ssh")
    def test_live_recover_mocked(self, mock_ssh, mock_ps, mock_git, mock_remote, tmp_path):
        mock_git.side_effect = ["production", "abc1234"]
        mock_ps.return_value = "api\trunning\nworker\trunning\ndb\trunning"
        mock_remote.return_value = ExecResult(ok=True, simulated=False, output="ok")
        mock_ssh.return_value = '{"status":"ok"}'

        with patch("guardian_platform.profiles.ifg.recover.stages.recover_report_path") as rp:
            rp.return_value = tmp_path / "r.md"
            code = run_prod_recover(dry_run=False, assume_yes=True)
        assert code == 0
