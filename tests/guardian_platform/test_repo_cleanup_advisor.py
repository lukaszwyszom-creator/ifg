"""IFG Repository Cleanup Advisor tests."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from guardian_platform.core.config.models import ProjectConfig
from guardian_platform.core.repository.analyzer import RepositoryAnalyzer
from guardian_platform.profiles.ifg.repo_cleanup.advisor import advise_path
from guardian_platform.profiles.ifg.repo_cleanup.executor import execute_plan
from guardian_platform.profiles.ifg.repo_cleanup.history import classify_history
from guardian_platform.profiles.ifg.repo_cleanup.models import AdvisorDecision, HistoryKind
from guardian_platform.profiles.ifg.repo_cleanup.boundaries import discover_phase0_artifacts, is_within_repo_boundary
from guardian_platform.profiles.ifg.repo_cleanup.git_guard import UNCOMMITTED_CHANGES_MESSAGE
from guardian_platform.profiles.ifg.repo_cleanup.planner import build_cleanup_plan
from guardian_platform.profiles.ifg.repo_cleanup.policy import archive_destination, is_never_delete_path
from guardian_platform.profiles.ifg.repo_cleanup.report import render_plan_markdown, write_plan_report
from guardian_platform.profiles.ifg.repo_cleanup.runner import run_repo_cleanup
from tests.guardian_platform.conftest import REPO_ROOT, run_main


@pytest.fixture
def advisor_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "alembic").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "frontend-react" / "dist").mkdir(parents=True)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / "docs" / "KSEF_SYNC_FIX.md").write_text("# fix\n", encoding="utf-8")
    (tmp_path / "docs" / "GUARDIAN_PLATFORM_ARCHITECTURE.md").write_text("# arch\n", encoding="utf-8")
    (tmp_path / "alembic" / "env.py").write_text("from alembic import op\n", encoding="utf-8")
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "scripts" / "dead.py").write_text("X=1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# readme\n", encoding="utf-8")
    return tmp_path


class TestAdvisorScoring:
    def test_closed_incident_archives(self, advisor_repo: Path):
        analysis = RepositoryAnalyzer(advisor_repo).analyze()
        item = advise_path("docs/KSEF_SYNC_FIX.md", analysis.files["docs/KSEF_SYNC_FIX.md"])
        assert item.decision == AdvisorDecision.ARCHIVE
        assert item.confidence >= 90
        assert item.history == HistoryKind.CLOSED_INCIDENT

    def test_canonical_doc_keep(self, advisor_repo: Path):
        analysis = RepositoryAnalyzer(advisor_repo).analyze()
        item = advise_path(
            "docs/GUARDIAN_PLATFORM_ARCHITECTURE.md",
            analysis.files["docs/GUARDIAN_PLATFORM_ARCHITECTURE.md"],
        )
        assert item.decision == AdvisorDecision.KEEP
        assert item.confidence >= 95

    def test_alembic_never_delete(self, advisor_repo: Path):
        analysis = RepositoryAnalyzer(advisor_repo).analyze()
        item = advise_path("alembic/env.py", analysis.files["alembic/env.py"])
        assert item.decision != AdvisorDecision.DELETE
        assert is_never_delete_path("alembic/env.py")

    def test_init_py_never_delete(self, advisor_repo: Path):
        analysis = RepositoryAnalyzer(advisor_repo).analyze()
        item = advise_path("app/__init__.py", analysis.files["app/__init__.py"])
        assert item.decision != AdvisorDecision.DELETE

    def test_local_artifact_delete(self, advisor_repo: Path):
        item = advise_path("__pycache__", None)
        assert item.decision == AdvisorDecision.DELETE
        assert item.confidence >= 95


class TestArchivePolicy:
    def test_archive_destination_incident(self):
        dest = archive_destination("docs/KSEF_SYNC_FIX.md")
        assert "docs/archive/2026-06/" in dest
        assert dest.endswith("KSEF_SYNC_FIX.md")

    def test_history_closed_incident(self):
        kind, _ = classify_history("docs/KSEF_PURCHASE_SYNC_FIX.md")
        assert kind == HistoryKind.CLOSED_INCIDENT


class TestPhaseSelection:
    def test_phase0_only_local(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=0, dry_run=True)
        assert all(op.phase == 0 for op in plan.operations)
        sources = {op.source for op in plan.operations}
        assert ".pytest_cache" in sources or any("__pycache__" in s for s in sources)
        assert not any("dist" in s for s in sources)
        assert not any("node_modules" in s for s in sources)

    def test_phase1_git_mv_only(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=1, dry_run=True)
        assert all(op.phase == 1 for op in plan.operations)
        assert all(op.action.value == "git_mv" for op in plan.operations)

    def test_phase3_review_only(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=3, dry_run=True)
        assert all(op.action.value == "list_review" for op in plan.operations)

    def test_full_plan_dry_run(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=None, dry_run=True)
        assert plan.operation_count > 0
        assert plan.dry_run is True


class TestDryRunAndRollback:
    def test_dry_run_no_execution(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=0, dry_run=True)
        executed = execute_plan(advisor_repo, plan)
        assert executed == []
        assert (advisor_repo / "__pycache__").exists()

    def test_rollback_plan_present(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=None, dry_run=True)
        assert len(plan.rollback_steps) == plan.operation_count

    def test_report_written(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=None, dry_run=True)
        path = write_plan_report(advisor_repo, plan)
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "IFG Repository Cleanup Plan" in text
        assert "Rollback plan" in text


class TestConfidence:
    def test_high_confidence_archive(self, advisor_repo: Path):
        analysis = RepositoryAnalyzer(advisor_repo).analyze()
        item = advise_path("docs/KSEF_SYNC_FIX.md", analysis.files["docs/KSEF_SYNC_FIX.md"])
        assert item.confidence >= 97

    def test_render_contains_confidence(self, advisor_repo: Path):
        plan = build_cleanup_plan(advisor_repo, phase=1, dry_run=True)
        md = render_plan_markdown(plan, root=advisor_repo)
        assert "Confidence:" in md


class TestCleanupCLI:
    def test_registered_mutating(self, platform_runtime):
        spec = platform_runtime.commands.resolve_namespaced("ifg", ["repo", "cleanup"])
        assert spec is not None
        assert spec.mutating is True
        assert spec.supports_dry_run is True

    def test_dry_run_full_plan(self, advisor_repo: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=advisor_repo),
        )
        code, out = run_main(["--dry-run", "ifg", "repo", "cleanup"])
        assert code == 0
        assert "DRY-RUN" in out
        assert (advisor_repo / "docs" / "reports" / "repository_cleanup_plan.md").exists()

    def test_phase1_dry_run_shows_git_mv(self, advisor_repo: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=advisor_repo),
        )
        code, out = run_main(["--dry-run", "ifg", "repo", "cleanup", "--phase", "1"])
        assert code == 0
        assert "git_mv" in out

    def test_live_blocked_without_yes(self):
        code, out = run_main(["ifg", "repo", "cleanup"])
        assert code == 2
        assert "requires --yes" in out


class TestRegressionIFG:
    def test_alembic_env_not_delete(self, repo_root: Path):
        analysis = RepositoryAnalyzer(repo_root).analyze()
        item = advise_path("alembic/env.py", analysis.files.get("alembic/env.py"))
        assert item.decision != AdvisorDecision.DELETE

    def test_architecture_doc_not_delete(self, repo_root: Path):
        analysis = RepositoryAnalyzer(repo_root).analyze()
        path = "docs/GUARDIAN_PLATFORM_ARCHITECTURE.md"
        item = advise_path(path, analysis.files.get(path))
        assert item.decision != AdvisorDecision.DELETE

    def test_init_not_delete(self, repo_root: Path):
        analysis = RepositoryAnalyzer(repo_root).analyze()
        item = advise_path("app/__init__.py", analysis.files.get("app/__init__.py"))
        assert item.decision != AdvisorDecision.DELETE

    @patch("guardian_platform.profiles.ifg.repo_cleanup.executor._local_remove")
    def test_phase0_yes_local_only(self, mock_remove, advisor_repo: Path):
        code = run_repo_cleanup(root=advisor_repo, dry_run=False, assume_yes=True, phase=0)
        assert code == 0
        assert mock_remove.called
        for call in mock_remove.call_args_list:
            rel = call.args[1]
            assert not rel.startswith(("docs/", "app/", "scripts/", "alembic/"))
            assert is_within_repo_boundary(rel)


class TestRepositoryBoundary:
    @pytest.fixture
    def boundary_repo(self, tmp_path: Path) -> Path:
        (tmp_path / "app" / "__pycache__").mkdir(parents=True)
        (tmp_path / "app" / "__pycache__" / "mod.pyc").write_bytes(b"\x00")
        (tmp_path / ".pytest_cache").mkdir()
        venv_cache = (
            tmp_path
            / ".venv"
            / "lib"
            / "python3.13"
            / "site-packages"
            / "requests"
            / "__pycache__"
        )
        venv_cache.mkdir(parents=True)
        (venv_cache / "models.pyc").write_bytes(b"\x00")
        (tmp_path / ".git" / "objects" / "pack").mkdir(parents=True)
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "NOTE.md").write_text("# x\n", encoding="utf-8")
        return tmp_path

    def test_phase0_excludes_venv_and_git(self, boundary_repo: Path):
        plan = build_cleanup_plan(boundary_repo, phase=0, dry_run=True)
        sources = {op.source for op in plan.operations}
        assert any("app/__pycache__" in s for s in sources)
        assert not any(s.startswith(".venv/") for s in sources)
        assert not any(".venv" in s.split("/") for s in sources)
        assert not any(s.startswith(".git/") for s in sources)
        assert not any("site-packages" in s for s in sources)

    def test_all_phases_respect_boundary(self, boundary_repo: Path):
        plan = build_cleanup_plan(boundary_repo, phase=None, dry_run=True)
        for op in plan.operations:
            assert is_within_repo_boundary(op.source)
            if op.target:
                assert is_within_repo_boundary(op.target)

    def test_real_repo_phase0_not_inflated(self, repo_root: Path):
        plan = build_cleanup_plan(repo_root, phase=0, dry_run=True)
        assert plan.operation_count < 150
        for op in plan.operations:
            assert is_within_repo_boundary(op.source)
            assert ".venv" not in op.source
            assert not op.source.startswith(".git/")

    def test_real_repo_full_plan_boundary(self, repo_root: Path):
        plan = build_cleanup_plan(repo_root, phase=None, dry_run=True)
        for op in plan.operations:
            assert is_within_repo_boundary(op.source)
            if op.target:
                assert is_within_repo_boundary(op.target)
            assert not op.source.startswith((".venv/", ".git/"))
            if op.target:
                assert not op.target.startswith((".venv/", ".git/"))


def _git_init_commit(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)


def _git_status_porcelain(repo: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


class TestPhase0Safety:
    @pytest.fixture
    def phase0_git_repo(self, tmp_path: Path) -> Path:
        (tmp_path / "app").mkdir()
        (tmp_path / "docs").mkdir()
        (tmp_path / "scripts").mkdir()
        (tmp_path / "frontend-react" / "dist").mkdir(parents=True)
        (tmp_path / "frontend-react" / "dist" / "index.html").write_text("built\n", encoding="utf-8")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / ".pytest_cache").mkdir()
        (tmp_path / "app" / "__pycache__").mkdir()
        _git_init_commit(tmp_path)
        subprocess.run(
            ["git", "add", "frontend-react/dist/index.html"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "commit", "-m", "track dist"], cwd=tmp_path, check=True, capture_output=True)
        return tmp_path

    def test_phase0_excludes_git_tracked_dist(self, phase0_git_repo: Path):
        discovered = discover_phase0_artifacts(phase0_git_repo)
        assert not any("dist" in path for path in discovered)

        plan = build_cleanup_plan(phase0_git_repo, phase=0, dry_run=True)
        assert not any("dist" in op.source for op in plan.operations)

    def test_phase0_live_does_not_change_git_status(self, phase0_git_repo: Path):
        status_before = _git_status_porcelain(phase0_git_repo)
        code = run_repo_cleanup(root=phase0_git_repo, dry_run=False, assume_yes=True, phase=0, write_report=False)
        status_after = _git_status_porcelain(phase0_git_repo)

        assert code == 0
        assert status_before == status_after
        assert (phase0_git_repo / "frontend-react" / "dist" / "index.html").exists()
        assert not (phase0_git_repo / ".pytest_cache").exists()


class TestCleanWorktreeGuard:
    @pytest.fixture
    def dirty_git_repo(self, advisor_repo: Path) -> Path:
        _git_init_commit(advisor_repo)
        (advisor_repo / "docs" / "dirty.md").write_text("# dirty\n", encoding="utf-8")
        return advisor_repo

    def test_phase1_refused_when_dirty(self, dirty_git_repo: Path, capsys: pytest.CaptureFixture[str]):
        code = run_repo_cleanup(root=dirty_git_repo, dry_run=True, phase=1, write_report=False)
        out = capsys.readouterr().out

        assert code == 1
        for line in UNCOMMITTED_CHANGES_MESSAGE:
            assert line in out

    def test_phase0_allowed_when_dirty(self, dirty_git_repo: Path):
        code = run_repo_cleanup(root=dirty_git_repo, dry_run=True, phase=0, write_report=False)
        assert code == 0

    def test_all_phases_dirty_runs_phase0_only(self, dirty_git_repo: Path, capsys: pytest.CaptureFixture[str]):
        code = run_repo_cleanup(root=dirty_git_repo, dry_run=True, phase=None, write_report=False)
        out = capsys.readouterr().out
        plan = build_cleanup_plan(dirty_git_repo, phase=0, dry_run=True)

        assert code == 0
        assert "Phases 1-3 skipped" in out
        assert all(op.phase == 0 for op in plan.operations)
