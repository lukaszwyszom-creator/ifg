"""Unit tests for IFG release evaluate workflow (Release Engine v1)."""
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
from ifg_guardian.core.workflow.context import WorkflowContext  # noqa: E402
from ifg_guardian.core.workflow.definition import WorkflowDefinition  # noqa: E402
from ifg_guardian.core.workflow.engine import ExecutionEngine  # noqa: E402
from ifg_guardian.core.workflow.mode import ExecutionMode  # noqa: E402
from ifg_guardian.core.workflow.state import WorkflowState, WorkflowStateMachine  # noqa: E402
from ifg_guardian.core.workflow.transaction import WorkflowTransaction  # noqa: E402
from ifg_guardian.modules.ifg_release_evaluate import (  # noqa: E402
    execute_ifg_release_evaluate,
    evaluate_from_context,
    run_ifg_release_explain,
)
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus  # noqa: E402
from ifg_guardian.plugins.ifg.release_evaluate.models import (  # noqa: E402
    ImpactLevel,
    ReleaseDecisionStatus,
    ReleaseEvaluateState,
)
from ifg_guardian.plugins.ifg.release_evaluate.classification import (  # noqa: E402
    classify_doctor_check,
    finalize_classification,
    is_local_environment_error,
)
from ifg_guardian.plugins.ifg.release_evaluate.policy_engine import apply_policy_engine, load_policy_config  # noqa: E402
from ifg_guardian.plugins.ifg.release_evaluate.report import render_json, render_markdown, render_terminal  # noqa: E402


def _run_git(args: list[str], *, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _run_git(["init"], cwd=tmp_path)
    _run_git(["config", "user.email", "release@test"], cwd=tmp_path)
    _run_git(["config", "user.name", "Release Eval Test"], cwd=tmp_path)
    (tmp_path / "README.md").write_text("# test\n", encoding="utf-8")
    _run_git(["add", "."], cwd=tmp_path)
    _run_git(["commit", "-m", "init"], cwd=tmp_path)
    return tmp_path


def _sample_doctor_state() -> DoctorState:
    return DoctorState(
        overall_status=OverallStatus.READY_WITH_WARNINGS,
        checks=[
            CheckResult("env.branch", "environment", "branch", CheckStatus.PASS, "on production"),
            CheckResult("repo.audit", "repository", "repo audit", CheckStatus.PASS, "risk LOW"),
            CheckResult("frontend.build_required", "frontend", "npm run build", CheckStatus.WARN, "dirty src"),
            CheckResult("alembic.pending", "alembic", "pending", CheckStatus.PASS, "schema at head"),
            CheckResult("docker.remote", "docker", "remote", CheckStatus.WARN, "dry-run skipped"),
            CheckResult("config.template", "configuration", "template", CheckStatus.PASS, "ok"),
            CheckResult("database.backup_policy", "database", "backup policy", CheckStatus.PASS, "documented"),
        ],
    )


class TestWorkflowRegistry:
    def test_release_evaluate_registered(self):
        runtime = create_runtime()
        try:
            wf = runtime.resolve_workflow("ifg.release.evaluate")
            assert wf is not None
            assert wf.plugin == "ifg"
            assert wf.depends_on == ["ifg.doctor"]
            assert len(wf.stages) == 7
        finally:
            runtime.shutdown()


class TestReleaseEvaluateWorkflow:
    def test_workflow_uses_doctor_dependency_and_computes_decision(self, git_repo: Path):
        doctor_state = _sample_doctor_state()
        fake_doctor_tx = WorkflowTransaction(
            workflow_id="dep-doctor",
            workflow_type="ifg.doctor",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        fake_doctor_tx.doctor = doctor_state.to_dict()
        fake_doctor_tx.mark_started()
        fake_doctor_tx.mark_ended(state=WorkflowState.SUCCESS)

        fake_doctor_ctx = WorkflowContext(
            root=git_repo,
            workflow=WorkflowDefinition(id="ifg.doctor", label="doctor"),
            transaction=fake_doctor_tx,
            mode=ExecutionMode.LIVE,
            state_machine=WorkflowStateMachine(initial=WorkflowState.SUCCESS),
        )

        original_deps = ExecutionEngine._run_dependencies

        def fake_deps(self, ctx, workflow, *, mode, initial_data, _stack=None):
            if workflow.id != "ifg.release.evaluate":
                return original_deps(self, ctx, workflow, mode=mode, initial_data=initial_data, _stack=_stack)
            ctx.data["dependency_contexts"] = {"ifg.doctor": fake_doctor_ctx}
            ctx.transaction.dependencies["ifg.doctor"] = {
                "workflow_id": fake_doctor_tx.workflow_id,
                "workflow_type": "ifg.doctor",
                "outcome": "SUCCESS",
                "state": "SUCCESS",
            }

        with (
            patch.object(ExecutionEngine, "_run_dependencies", fake_deps),
            patch("ifg_guardian.plugins.ifg.release_evaluate.stages.ROOT", git_repo),
            patch("ifg_guardian.plugins.ifg.release_evaluate.stages.run_deploy_check", return_value=0),
            patch("ifg_guardian.plugins.ifg.release_evaluate.stages.subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                subprocess.CompletedProcess(["git"], 0, " M app/services/ksef.py\n", ""),
                subprocess.CompletedProcess(["pytest"], 0, "collected 10 items\n", ""),
            ]
            ctx = execute_ifg_release_evaluate(output_format="none", root=git_repo)

        assert ctx.state_machine.state == WorkflowState.SUCCESS
        state = evaluate_from_context(ctx)
        assert state.status in (
            ReleaseDecisionStatus.READY_WITH_WARNINGS,
            ReleaseDecisionStatus.STAGING_ONLY,
            ReleaseDecisionStatus.PRODUCTION_BLOCKED,
            ReleaseDecisionStatus.READY_FOR_DEPLOY,
        )
        assert state.release_score > 0
        assert state.impact["KSeF"] == ImpactLevel.HIGH
        assert isinstance(state.policy_rules_triggered, list)


class TestReleaseEvaluateReport:
    def test_report_rendering(self):
        tx = WorkflowTransaction(
            workflow_id="test-release",
            workflow_type="ifg.release.evaluate",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        tx.mark_started()
        tx.mark_ended(state=WorkflowState.SUCCESS)
        state = evaluate_from_context(
            type("Ctx", (), {"transaction": type("Tx", (), {"release_evaluate": {
                "status": "STAGING_ONLY",
                "rationale": "score below production threshold",
                "blockers": [],
                "warnings": ["docker warning"],
                "positives": ["repo clean"],
                "next_step": "run staging",
                "deployment_recommendation": "Wymagany staging",
                "release_score": 68,
                "release_score_parts": [],
                "impact": {"Backend": "MEDIUM"},
                "changed_files": ["app/services/a.py"],
                "doctor_overall_status": "READY_WITH_WARNINGS",
                "deploy_check_exit_code": 1,
                "test_discovery_ok": True,
                "policy_rules_triggered": ["alembic_changes_require_staging"],
                "required_actions": ["Run staging"],
                "backup_required": False,
                "staging_required": True,
                "production_blocked": False,
                "git_status_entries": [],
                "local_environment": [],
                "information": ["repo clean"],
                "summary": {
                    "project_status": "WARNING",
                    "environment_status": "READY",
                    "policy_status": "WARN",
                    "deployment_recommendation": "Wymagany staging",
                },
            }})()})
        )
        md = render_markdown(state, transaction=tx)
        js = json.loads(render_json(state, transaction=tx))
        term = render_terminal(state, transaction=tx)
        assert "Release Engine Evaluation" in md
        assert js["schema"] == "ifg_release_evaluate_report_v1"
        assert "Decision" in term
        assert "## BLOCKERS" in md
        assert "## LOCAL ENVIRONMENT" in md
        assert "## Executive Summary" in md


class TestClassificationEngine:
    def test_is_local_environment_error_detects_pytest_psycopg_alembic(self):
        assert is_local_environment_error("No module named 'pytest'")
        assert is_local_environment_error("No module named 'psycopg'")
        assert is_local_environment_error("[Errno 2] No such file or directory: 'alembic'")

    def test_classify_doctor_alembic_missing_as_local_environment(self):
        check = CheckResult(
            "alembic.current",
            "alembic",
            "current",
            CheckStatus.WARN,
            "[Errno 2] No such file or directory: 'alembic'",
        )
        finding = classify_doctor_check(check)
        assert finding.category.value == "LOCAL_ENVIRONMENT"
        assert finding.scope.value == "ENVIRONMENT"

    def test_local_env_pytest_missing_does_not_block_release(self):
        doctor = _sample_doctor_state()
        state = ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_FOR_DEPLOY,
            test_discovery_ok=False,
            test_discovery_local_env=True,
            test_discovery_error="No module named 'pytest'",
            release_score=80,
        )
        policy = load_policy_config()
        apply_policy_engine(state, doctor=doctor, policy=policy)
        finalize_classification(state, doctor=doctor, policy=policy)
        assert state.status != ReleaseDecisionStatus.PRODUCTION_BLOCKED
        assert "tests_must_pass" not in state.policy_rules_triggered
        assert any("pytest" in item for item in state.local_environment)

    def test_failed_project_tests_still_block(self):
        doctor = _sample_doctor_state()
        state = ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_FOR_DEPLOY,
            test_discovery_ok=False,
            test_discovery_local_env=False,
            test_discovery_error="collected 0 items / 3 errors",
            release_score=80,
        )
        policy = load_policy_config()
        apply_policy_engine(state, doctor=doctor, policy=policy)
        assert state.status == ReleaseDecisionStatus.PRODUCTION_BLOCKED
        assert state.release_score == 40


class TestWorkflowDuration:
    def test_elapsed_ms_before_mark_ended(self):
        import time

        tx = WorkflowTransaction(
            workflow_id="dur-test",
            workflow_type="ifg.release.evaluate",
            plugin="ifg",
            execution_mode=ExecutionMode.LIVE,
        )
        tx.mark_started()
        time.sleep(0.01)
        assert tx.elapsed_ms() >= 10
        tx.mark_ended(state=WorkflowState.SUCCESS)
        assert tx.duration_ms >= 10


class TestPolicyEngine:
    def test_critical_migration_requires_backup_single_production(self):
        doctor = _sample_doctor_state()
        state = ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_FOR_DEPLOY,
            changed_files=["alembic/versions/x.py", "app/persistence/models/transmissions.py"],
            test_discovery_ok=True,
        )
        apply_policy_engine(
            state,
            doctor=doctor,
            policy={
                "default_deployment_profile": "single_production",
                "profiles": {
                    "single_production": {"staging_available": False},
                    "enterprise": {"staging_available": True},
                },
                "critical_migration_tables": ["transmissions"],
                "non_report_untracked_block_patterns": [".env"],
                "report_paths": ["docs/reports/"],
            },
        )
        assert state.status == ReleaseDecisionStatus.READY_WITH_WARNINGS
        assert state.backup_required is True
        assert state.staging_required is False
        assert "critical_db_change_requires_verified_backup" in state.policy_rules_triggered

    def test_failed_tests_block_production(self):
        doctor = _sample_doctor_state()
        state = ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_FOR_DEPLOY,
            changed_files=[],
            test_discovery_ok=False,
        )
        apply_policy_engine(
            state,
            doctor=doctor,
            policy=load_policy_config(),
        )
        assert state.status == ReleaseDecisionStatus.PRODUCTION_BLOCKED
        assert state.production_blocked is True
        assert "tests_must_pass" in state.policy_rules_triggered

    def test_dirty_working_tree_blocks_production(self):
        doctor = _sample_doctor_state()
        state = ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_FOR_DEPLOY,
            changed_files=["app/services/a.py"],
            git_status_entries=[{"code": " M", "path": "app/services/a.py"}],
            test_discovery_ok=True,
            release_score=80,
        )
        apply_policy_engine(
            state,
            doctor=doctor,
            policy=load_policy_config(),
        )
        assert state.status == ReleaseDecisionStatus.PRODUCTION_BLOCKED
        assert "dirty_working_tree_blocks_production" in state.policy_rules_triggered

    def test_dirty_working_tree_allows_override(self):
        doctor = _sample_doctor_state()
        state = ReleaseEvaluateState(
            status=ReleaseDecisionStatus.READY_FOR_DEPLOY,
            changed_files=["frontend-react/src/App.jsx"],
            git_status_entries=[{"code": " M", "path": "frontend-react/src/App.jsx"}],
            test_discovery_ok=True,
            release_score=80,
            allow_dirty_build=True,
        )
        apply_policy_engine(
            state,
            doctor=doctor,
            policy=load_policy_config(),
        )
        assert state.status == ReleaseDecisionStatus.READY_WITH_OVERRIDE
        assert "dirty_tree_build_with_override" in state.policy_rules_triggered
        assert state.release_score == 55


class TestReleaseExplain:
    def test_release_explain_json(self, capsys):
        code = run_ifg_release_explain(output_format="json")
        captured = capsys.readouterr().out
        assert code == 0
        payload = json.loads(captured)
        assert "critical_migration_tables" in payload
