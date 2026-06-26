"""Guardian Platform IFG profile tests."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from guardian_platform.core.profiles.loader import load_platform
from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.core.config.models import ProjectConfig
from guardian_platform.profiles.ifg.doctor.aggregation import (
    aggregate_overall_status,
    exit_code_for_status,
    stage_status_from_checks,
)
from guardian_platform.profiles.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus
from guardian_platform.profiles.ifg.lib.risk import FileCategory, RiskLevel, max_risk
from guardian_platform.profiles.ifg.repo_audit.classifier import classify_modified_path, classify_untracked
from guardian_platform.profiles.ifg.repo_audit.models import ClassifiedFile, RepoAuditState
from guardian_platform.profiles.ifg.repo_audit.service import aggregate_risk, parse_changed_paths
from guardian_platform.profiles.ifg.workflows.doctor import IFG_DOCTOR_WORKFLOW
from guardian_platform.profiles.ifg.workflows.repo_audit import IFG_REPO_AUDIT_WORKFLOW
from tests.guardian_platform.conftest import REPO_ROOT, run_main


def _ctx(**extra):
    return CommandContext(
        root=REPO_ROOT,
        config=ProjectConfig.defaults(REPO_ROOT),
        argv=[],
        extra=extra,
    )


class TestIFGProfileLoading:
    def test_profile_in_runtime(self):
        rt = load_platform(["ifg"])
        assert "ifg" in {p.profile_id for p in rt.profiles.list_profiles()}

    def test_all_read_only_commands_registered(self):
        rt = load_platform(["ifg"])
        paths = {c.path for c in rt.commands.list_commands() if c.profile == "ifg"}
        expected = {
            ("ping",),
            ("doctor",),
            ("deploy", "check"),
            ("deploy", "run"),
            ("frontend", "check"),
            ("ksef", "check"),
            ("prod", "health"),
            ("prod", "recover"),
            ("repo", "audit"),
            ("repo", "cleanup"),
        }
        assert expected <= paths

    def test_doctor_workflow_defined(self):
        assert IFG_DOCTOR_WORKFLOW.id == "ifg.doctor"
        assert len(IFG_DOCTOR_WORKFLOW.stages) == 12

    def test_repo_audit_workflow_defined(self):
        assert IFG_REPO_AUDIT_WORKFLOW.id == "ifg.repo.audit"
        assert len(IFG_REPO_AUDIT_WORKFLOW.stages) == 9

    def test_no_ifg_guardian_imports(self):
        result = subprocess.run(
            ["grep", "-R", "--exclude=__pycache__", "ifg_guardian", str(REPO_ROOT / "scripts/guardian_platform/profiles/ifg")],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0 or not result.stdout.strip()


class TestIFGDoctorModels:
    def test_check_result_roundtrip(self):
        cr = CheckResult("id", "grp", "name", CheckStatus.PASS, "ok")
        assert CheckResult.from_dict(cr.to_dict()).status == CheckStatus.PASS

    def test_aggregate_blocked_on_critical(self):
        state = DoctorState(
            checks=[
                CheckResult("a", "g", "n", CheckStatus.CRITICAL, "x"),
            ]
        )
        assert aggregate_overall_status(state) == OverallStatus.BLOCKED

    def test_aggregate_ready_with_warnings(self):
        state = DoctorState(
            checks=[CheckResult("a", "g", "n", CheckStatus.WARN, "x")]
        )
        assert aggregate_overall_status(state) == OverallStatus.READY_WITH_WARNINGS

    def test_exit_code_ready(self):
        assert exit_code_for_status(OverallStatus.READY) == 0

    def test_exit_code_blocked(self):
        assert exit_code_for_status(OverallStatus.BLOCKED) == 1

    def test_stage_status_from_checks_fail(self):
        checks = [CheckResult("a", "g", "n", CheckStatus.FAIL, "x")]
        from guardian_platform.core.workflow.stage import StageStatus

        assert stage_status_from_checks(checks) == StageStatus.FAIL


class TestIFGRepoAudit:
    def test_classify_untracked_docs(self):
        f = classify_untracked("docs/REPORT.md")
        assert f.category == FileCategory.COMMIT

    def test_classify_modified_app(self):
        f = classify_modified_path("app/main.py")
        assert f.risk == RiskLevel.HIGH

    def test_classify_env_as_ignore(self):
        f = classify_modified_path(".env.production")
        assert f.category == FileCategory.IGNORE

    def test_parse_changed_paths(self):
        paths = parse_changed_paths(" M app/main.py\n?? docs/x.md")
        assert ("M", "app/main.py") in paths

    def test_aggregate_risk_high_on_wrong_branch(self):
        audit = RepoAuditState(branch="main", files=[])
        aggregate_risk(audit)
        assert audit.overall_risk == RiskLevel.HIGH

    def test_max_risk_order(self):
        assert max_risk(RiskLevel.LOW, RiskLevel.HIGH) == RiskLevel.HIGH


class TestIFGCLICommands:
    @patch("guardian_platform.profiles.ifg.commands.doctor.run_ifg_doctor", return_value=0)
    def test_ifg_doctor(self, mock_run):
        code, _ = run_main(["ifg", "doctor"])
        assert code == 0
        mock_run.assert_called_once()

    @patch("guardian_platform.profiles.ifg.commands.repo_audit.run_repo_audit", return_value=0)
    def test_ifg_repo_audit(self, mock_run):
        code, _ = run_main(["ifg", "repo", "audit"])
        assert code == 0
        mock_run.assert_called_once()

    def test_ifg_deploy_check_runs(self):
        code, out = run_main(["ifg", "deploy", "check"])
        assert "IFG Guardian Deploy Check" in out
        assert code in (0, 1)

    def test_ifg_frontend_check_runs(self):
        code, out = run_main(["ifg", "frontend", "check"])
        assert "frontend check" in out
        assert code in (0, 1)

    def test_ifg_ksef_check_runs(self):
        code, out = run_main(["ifg", "ksef", "check"])
        assert "KSeF" in out
        assert code in (0, 1)

    def test_ifg_prod_health_runs(self):
        code, out = run_main(["ifg", "prod", "health"])
        assert "prod health" in out
        assert code in (0, 1)


class TestIFGRepoAuditWorkflow:
    def test_repo_audit_in_git_repo(self, git_repo, monkeypatch):
        monkeypatch.chdir(git_repo)
        from guardian_platform.profiles.ifg.repo_audit.runner import execute_repo_audit
        from guardian_platform.core.workflow.state import WorkflowState

        ctx = execute_repo_audit(output_format="none")
        assert ctx.state_machine.state == WorkflowState.SUCCESS

    def test_collect_audit_returns_state(self, git_repo, monkeypatch):
        monkeypatch.chdir(git_repo)
        from guardian_platform.profiles.ifg.repo_audit.runner import collect_audit

        audit = collect_audit()
        assert audit.branch
        assert audit.head


class TestIFGDoctorRunner:
    @patch("guardian_platform.profiles.ifg.doctor.stages.collect_audit")
    @patch("guardian_platform.profiles.ifg.doctor.checks.run_health_checks")
    @patch("guardian_platform.profiles.ifg.doctor.checks.run_docker_checks")
    @patch("guardian_platform.profiles.ifg.doctor.checks.run_alembic_checks")
    def test_run_ifg_doctor_minimal(self, mock_alembic, mock_docker, mock_health, mock_audit, git_repo, monkeypatch):
        monkeypatch.chdir(git_repo)
        mock_audit.return_value = RepoAuditState()
        mock_docker.return_value = []
        mock_health.return_value = []
        mock_alembic.return_value = []

        from guardian_platform.profiles.ifg.doctor.runner import run_ifg_doctor

        code = run_ifg_doctor(remote_host="localhost", remote_path="/tmp")
        assert code in (0, 1)

    def test_doctor_state_in_service(self):
        from guardian_platform.profiles.ifg.doctor.models import DoctorState
        from guardian_platform.profiles.ifg.doctor.service import get_doctor_state

        class FakeCtx:
            data = {"doctor": DoctorState()}

        assert get_doctor_state(FakeCtx()) is not None
