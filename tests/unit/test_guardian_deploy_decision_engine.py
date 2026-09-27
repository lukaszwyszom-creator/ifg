"""Unit tests for GWO-GUARDIAN-0076 deploy decision engine."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.plugins.bootstrap import create_runtime  # noqa: E402

_runtime = create_runtime()
_runtime.shutdown()

from ifg_guardian.plugins.ifg.deploy_decision.alembic_scope import AlembicDeploySnapshot  # noqa: E402
from ifg_guardian.plugins.ifg.deploy_decision.paths import is_backend_deploy_path, is_frontend_deploy_path  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.aggregation import aggregate_overall_status  # noqa: E402
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState, OverallStatus  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.build_detector import detect_build_decisions  # noqa: E402
from ifg_guardian.plugins.ifg.release_plan.models import RepositorySnapshot  # noqa: E402


def _doctor_with_checks(checks: list[CheckResult]) -> DoctorState:
    return DoctorState(checks=checks)


def _decision(decisions, name: str):
    return next(d for d in decisions if d.name == name)


def _base_doctor_checks() -> list[CheckResult]:
    return [
        CheckResult("frontend.build_required", "frontend", "build", CheckStatus.PASS, "ok", scope="local"),
        CheckResult("frontend.dist_freshness", "frontend", "dist", CheckStatus.PASS, "ok", scope="local"),
        CheckResult("frontend.src_changed", "frontend", "src", CheckStatus.PASS, "no changes", scope="local"),
        CheckResult("backend.changes", "backend", "changes", CheckStatus.PASS, "none", scope="local"),
        CheckResult("backend.build_required", "backend", "build", CheckStatus.PASS, "none", scope="local"),
        CheckResult("backend.dockerfile", "backend", "Dockerfile", CheckStatus.PASS, "present", scope="local"),
        CheckResult("alembic.pending", "alembic", "pending", CheckStatus.PASS, "schema at head", scope="remote"),
    ]


class TestPathClassification:
    def test_backend_paths(self):
        assert is_backend_deploy_path("app/services/foo.py")
        assert is_backend_deploy_path("alembic/versions/abc.py")
        assert is_backend_deploy_path("worker/__main__.py")
        assert is_backend_deploy_path("requirements.txt")
        assert is_backend_deploy_path("Dockerfile")

    def test_frontend_paths(self):
        assert is_frontend_deploy_path("frontend-react/src/App.jsx")
        assert not is_frontend_deploy_path("app/main.py")


class TestBuildDecisions:
    def test_frontend_only_change(self):
        repo = RepositorySnapshot(
            frontend_changes=["frontend-react/src/App.jsx"],
            backend_changes=[],
        )
        decisions = detect_build_decisions(_doctor_with_checks(_base_doctor_checks()), repo)
        assert _decision(decisions, "Frontend Build").required is True
        assert _decision(decisions, "Backend Build").required is False
        assert "frontend-react/src/App.jsx" in _decision(decisions, "Frontend Build").trigger_files

    def test_backend_only_change(self):
        repo = RepositorySnapshot(
            frontend_changes=[],
            backend_changes=["app/services/purchase_sync_email_notifier.py", "alembic/versions/p6q7r8s9t0u1.py"],
        )
        doctor = _doctor_with_checks(_base_doctor_checks() + [
            CheckResult(
                "backend.changes",
                "backend",
                "changes",
                CheckStatus.WARN,
                "2 backend change(s)",
                details=repo.backend_changes,
                scope="local",
            ),
            CheckResult(
                "backend.build_required",
                "backend",
                "build",
                CheckStatus.FAIL,
                "rebuild required",
                scope="local",
            ),
        ])
        decisions = detect_build_decisions(doctor, repo)
        assert _decision(decisions, "Frontend Build").required is False
        assert _decision(decisions, "Backend Build").required is True
        assert _decision(decisions, "Worker Build").required is True
        reason = _decision(decisions, "Backend Build").reason
        assert "purchase_sync_email_notifier.py" in reason

    def test_new_migration_remote_behind(self):
        repo = RepositorySnapshot()
        alembic = AlembicDeploySnapshot(
            local_head="p6q7r8s9t0u1",
            remote_revision="o5p6q7r8s9t0",
            remote_available=True,
            pending_revisions=["p6q7r8s9t0u1"],
        )
        doctor = _doctor_with_checks(_base_doctor_checks() + [
            CheckResult(
                "alembic.pending",
                "alembic",
                "pending",
                CheckStatus.FAIL,
                "remote behind",
                scope="remote",
            ),
        ])
        decisions = detect_build_decisions(doctor, repo, alembic=alembic)
        mig = _decision(decisions, "Migration Required")
        assert mig.required is True
        assert "p6q7r8s9t0u1" in mig.reason

    def test_migration_not_required_when_heads_match(self):
        alembic = AlembicDeploySnapshot(
            local_head="p6q7r8s9t0u1",
            remote_revision="p6q7r8s9t0u1",
            remote_available=True,
            pending_revisions=[],
        )
        decisions = detect_build_decisions(
            _doctor_with_checks(_base_doctor_checks()),
            RepositorySnapshot(),
            alembic=alembic,
        )
        assert _decision(decisions, "Migration Required").required is False

    def test_migration_required_when_remote_older(self):
        alembic = AlembicDeploySnapshot(
            local_head="headrev2",
            remote_revision="headrev1",
            remote_available=True,
            pending_revisions=["headrev2"],
        )
        decisions = detect_build_decisions(
            _doctor_with_checks(_base_doctor_checks()),
            RepositorySnapshot(),
            alembic=alembic,
        )
        assert _decision(decisions, "Migration Required").required is True

    def test_backend_build_blocked_without_dockerfile(self):
        repo = RepositorySnapshot(backend_changes=["app/main.py"])
        doctor = _doctor_with_checks(_base_doctor_checks() + [
            CheckResult(
                "backend.dockerfile",
                "backend",
                "Dockerfile",
                CheckStatus.FAIL,
                "missing Dockerfile",
                scope="local",
            ),
            CheckResult(
                "backend.build_required",
                "backend",
                "build",
                CheckStatus.FAIL,
                "blocked",
                scope="local",
            ),
        ])
        decisions = detect_build_decisions(doctor, repo)
        backend = _decision(decisions, "Backend Build")
        assert backend.required is False
        assert backend.confidence == "BLOCKED"


class TestDoctorAggregation:
    def test_local_database_url_missing_is_warn_not_blocked(self):
        state = DoctorState(
            checks=[
                CheckResult(
                    "alembic.current",
                    "alembic",
                    "local current",
                    CheckStatus.WARN,
                    "Brak DATABASE_URL — local check unavailable",
                    scope="local",
                ),
                CheckResult(
                    "alembic.head",
                    "alembic",
                    "local head",
                    CheckStatus.PASS,
                    "abc12345",
                    scope="local",
                ),
                CheckResult(
                    "alembic.pending",
                    "alembic",
                    "pending",
                    CheckStatus.PASS,
                    "schema at head",
                    scope="remote",
                ),
            ]
        )
        assert aggregate_overall_status(state) == OverallStatus.READY_WITH_WARNINGS

    def test_ds723_unreachable_is_blocked(self):
        state = DoctorState(
            checks=[
                CheckResult(
                    "docker.remote",
                    "docker",
                    "remote docker",
                    CheckStatus.FAIL,
                    "DS723+ unreachable: connection refused",
                    scope="remote",
                ),
            ]
        )
        assert aggregate_overall_status(state) == OverallStatus.BLOCKED

    def test_local_alembic_fail_downgraded_when_database_url_missing(self):
        state = DoctorState(
            checks=[
                CheckResult(
                    "alembic.current",
                    "alembic",
                    "local current",
                    CheckStatus.FAIL,
                    "DATABASE_URL not set",
                    scope="local",
                ),
            ]
        )
        assert aggregate_overall_status(state) == OverallStatus.READY_WITH_WARNINGS


class TestGitScopeIntegration:
    def test_list_deploy_changed_files_uses_git_diff(self, monkeypatch: pytest.MonkeyPatch):
        from ifg_guardian.plugins.ifg.deploy_decision import git_scope
        from ifg_guardian.plugins.ifg.deploy_decision.git_scope import split_deploy_changes

        def fake_git(*args: str) -> str:
            if args == ("diff", "--name-only", "origin/production...HEAD"):
                return "app/services/foo.py\nfrontend-react/src/App.jsx"
            return ""

        monkeypatch.setattr(git_scope, "git", fake_git)
        files = git_scope.list_deploy_changed_files()
        backend, frontend = split_deploy_changes(files)
        assert "app/services/foo.py" in backend
        assert "frontend-react/src/App.jsx" in frontend
