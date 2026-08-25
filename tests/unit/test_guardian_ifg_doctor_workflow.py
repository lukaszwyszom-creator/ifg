"""Unit tests for IFG doctor workflow (Sprint 4)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.state import WorkflowState  # noqa: E402
from ifg_guardian.core.workflow.transaction import WorkflowTransaction  # noqa: E402
from ifg_guardian.modules.ifg_doctor import doctor_from_context, execute_ifg_doctor  # noqa: E402
from ifg_guardian.plugins.core.plugin import CorePlugin  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.aggregation import (  # noqa: E402
    aggregate_overall_status,
    exit_code_for_status,
    stage_status_from_checks,
)
from ifg_guardian.plugins.ifg.doctor.models import (  # noqa: E402
    CheckResult,
    CheckStatus,
    DoctorState,
    OverallStatus,
)
from ifg_guardian.plugins.ifg.doctor.report import (  # noqa: E402
    doctor_from_transaction,
    render_json,
    render_markdown,
    render_terminal,
)
from ifg_guardian.core.workflow.stage import StageStatus  # noqa: E402


def _run_git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _run_git(["init"], cwd=tmp_path)
    _run_git(["config", "user.email", "doctor@test"], cwd=tmp_path)
    _run_git(["config", "user.name", "Doctor Test"], cwd=tmp_path)
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=x\nJWT_SECRET_KEY=y\n", encoding="utf-8")
    (tmp_path / ".env.production.template").write_text("APP_ENV=production\n", encoding="utf-8")
    _run_git(["add", "."], cwd=tmp_path)
    _run_git(["commit", "-m", "init"], cwd=tmp_path)
    return tmp_path


def _patch_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    import ifg_guardian.config as config_mod
    import ifg_guardian.core.git as git_mod
    import ifg_guardian.core.line_endings as le_mod
    import ifg_guardian.modules.frontend as frontend_mod

    monkeypatch.setattr(config_mod, "ROOT", root)
    monkeypatch.setattr(git_mod, "ROOT", root)
    monkeypatch.setattr(le_mod, "ROOT", root)
    monkeypatch.setattr(frontend_mod, "ROOT", root)


class TestWorkflowRegistry:
    def test_ifg_doctor_only_in_ifg_plugin(self):
        core_ids = [wf.id for wf in CorePlugin().workflows()]
        assert "ifg.doctor" not in core_ids

        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.doctor")
            assert wf is not None
            assert wf.plugin == "ifg"
            assert len(wf.stages) == 12
        finally:
            runtime.shutdown()


class TestCheckStatuses:
    def test_pass_check(self):
        check = CheckResult("t.pass", "test", "pass", CheckStatus.PASS, "ok")
        assert stage_status_from_checks([check]) == StageStatus.PASS

    def test_warn_check(self):
        check = CheckResult("t.warn", "test", "warn", CheckStatus.WARN, "warning")
        assert stage_status_from_checks([check]) == StageStatus.WARN

    def test_fail_check(self):
        check = CheckResult("t.fail", "test", "fail", CheckStatus.FAIL, "failed")
        assert stage_status_from_checks([check]) == StageStatus.FAIL

    def test_critical_check(self):
        check = CheckResult("t.crit", "test", "critical", CheckStatus.CRITICAL, "blocked")
        assert stage_status_from_checks([check]) == StageStatus.FAIL


class TestRiskAggregation:
    def test_all_pass_ready(self):
        state = DoctorState(
            checks=[CheckResult("a", "g", "a", CheckStatus.PASS, "ok")]
        )
        assert aggregate_overall_status(state) == OverallStatus.READY
        assert exit_code_for_status(OverallStatus.READY) == 0

    def test_warn_ready_with_warnings(self):
        state = DoctorState(
            checks=[CheckResult("a", "g", "a", CheckStatus.WARN, "warn")]
        )
        assert aggregate_overall_status(state) == OverallStatus.READY_WITH_WARNINGS
        assert exit_code_for_status(OverallStatus.READY_WITH_WARNINGS) == 1

    def test_fail_blocked(self):
        state = DoctorState(
            checks=[CheckResult("a", "g", "a", CheckStatus.FAIL, "fail")]
        )
        assert aggregate_overall_status(state) == OverallStatus.BLOCKED

    def test_critical_blocked(self):
        state = DoctorState(
            checks=[CheckResult("a", "g", "a", CheckStatus.CRITICAL, "crit")]
        )
        assert aggregate_overall_status(state) == OverallStatus.BLOCKED


class TestWorkflowTransaction:
    def test_doctor_persisted(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)

        with (
            patch("ifg_guardian.modules.repo_audit.collect_audit") as mock_collect,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_docker_checks") as mock_docker,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_health_checks") as mock_health,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_alembic_checks") as mock_alembic,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_frontend_checks") as mock_frontend,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_backend_checks") as mock_backend,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_environment_checks") as mock_env,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_database_checks") as mock_db,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_configuration_checks") as mock_cfg,
        ):
            from ifg_guardian.core.repo_audit.models import RepoAuditState
            from ifg_guardian.core.risk import RiskLevel

            mock_collect.return_value = RepoAuditState(branch="production", overall_risk=RiskLevel.LOW)
            mock_docker.return_value = [
                CheckResult("docker", "docker", "compose", CheckStatus.PASS, "ok")
            ]
            mock_health.return_value = [
                CheckResult("health", "health", "/health", CheckStatus.PASS, "ok")
            ]
            mock_alembic.return_value = [
                CheckResult("alembic", "alembic", "head", CheckStatus.PASS, "ok")
            ]
            mock_frontend.return_value = [
                CheckResult("frontend.dist", "frontend", "dist", CheckStatus.PASS, "ok")
            ]
            mock_backend.return_value = [
                CheckResult("backend.changes", "backend", "changes", CheckStatus.PASS, "ok")
            ]
            mock_env.return_value = [
                CheckResult("env.branch", "environment", "branch", CheckStatus.PASS, "ok")
            ]
            mock_db.return_value = [
                CheckResult("database.postgres", "database", "postgres", CheckStatus.PASS, "ok")
            ]
            mock_cfg.return_value = [
                CheckResult("config.template", "configuration", "template", CheckStatus.PASS, "ok")
            ]

            ctx_result = execute_ifg_doctor(output_format="none", dry_run=True, root=git_repo)

        payload = ctx_result.transaction.to_dict()
        assert payload["doctor"]
        assert payload["doctor"]["overall_status"]
        assert payload["lifecycle"]["duration_ms"] >= 0
        restored = doctor_from_transaction(ctx_result.transaction)
        assert restored.overall_status == doctor_from_context(ctx_result).overall_status


class TestReportRendering:
    def _sample_state(self) -> tuple[DoctorState, WorkflowTransaction]:
        state = DoctorState(
            overall_status=OverallStatus.READY_WITH_WARNINGS,
            checks=[
                CheckResult("c1", "environment", "branch", CheckStatus.PASS, "ok"),
                CheckResult("c2", "frontend", "dist", CheckStatus.WARN, "stale"),
            ],
            summary={"checks_total": 2, "warn": 1},
        )
        tx = WorkflowTransaction(
            workflow_id="2026-05-22T120000Z_ifg_doctor",
            workflow_type="ifg.doctor",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        tx.mark_started()
        tx.mark_ended(state=WorkflowState.SUCCESS)
        tx.doctor = state.to_dict()
        return state, tx

    def test_markdown_report(self):
        state, tx = self._sample_state()
        md = render_markdown(state, transaction=tx)
        assert "# IFG Guardian — IFG Doctor" in md
        assert "READY_WITH_WARNINGS" in md
        assert "| **Workflow** |" in md

    def test_json_report(self):
        state, tx = self._sample_state()
        data = json.loads(render_json(state, transaction=tx))
        assert data["schema"] == "ifg_doctor_report_v1"
        assert data["doctor"]["overall_status"] == "READY_WITH_WARNINGS"

    def test_terminal_report(self):
        state, tx = self._sample_state()
        text = render_terminal(state, transaction=tx)
        assert "IFG Doctor" in text
        assert "READY WITH WARNINGS" in text


class TestDoctorWorkflowDryRun:
    def test_workflow_completes_dry_run(self, git_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, git_repo)

        with (
            patch("ifg_guardian.modules.repo_audit.collect_audit") as mock_collect,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_docker_checks") as mock_docker,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_health_checks") as mock_health,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_alembic_checks") as mock_alembic,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_frontend_checks") as mock_frontend,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_backend_checks") as mock_backend,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_environment_checks") as mock_env,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_database_checks") as mock_db,
            patch("ifg_guardian.plugins.ifg.doctor.stages.run_configuration_checks") as mock_cfg,
        ):
            from ifg_guardian.core.repo_audit.models import RepoAuditState
            from ifg_guardian.core.risk import RiskLevel

            mock_collect.return_value = RepoAuditState(branch="production", overall_risk=RiskLevel.LOW)
            mock_docker.return_value = [
                CheckResult("docker.remote", "docker", "remote", CheckStatus.WARN, "dry-run skip")
            ]
            mock_health.return_value = [
                CheckResult("health.endpoint", "health", "/health", CheckStatus.WARN, "dry-run skip")
            ]
            mock_alembic.return_value = [
                CheckResult("alembic.pending", "alembic", "pending", CheckStatus.PASS, "ok")
            ]
            mock_frontend.return_value = [
                CheckResult("frontend.dist", "frontend", "dist", CheckStatus.PASS, "ok")
            ]
            mock_backend.return_value = [
                CheckResult("backend.changes", "backend", "changes", CheckStatus.PASS, "ok")
            ]
            mock_env.return_value = [
                CheckResult("env.branch", "environment", "branch", CheckStatus.PASS, "ok")
            ]
            mock_db.return_value = [
                CheckResult("database.postgres", "database", "postgres", CheckStatus.PASS, "ok")
            ]
            mock_cfg.return_value = [
                CheckResult("config.template", "configuration", "template", CheckStatus.PASS, "ok")
            ]

            ctx = execute_ifg_doctor(output_format="none", dry_run=True, root=git_repo)

        assert ctx.state_machine.state == WorkflowState.SUCCESS
        state = doctor_from_context(ctx)
        assert state.overall_status in (
            OverallStatus.READY,
            OverallStatus.READY_WITH_WARNINGS,
            OverallStatus.BLOCKED,
        )
        assert len(state.checks) > 0
