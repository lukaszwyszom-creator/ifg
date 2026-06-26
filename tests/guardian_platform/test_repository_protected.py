"""Tests for protected artefact classification (Repo Graph v1.1)."""
from __future__ import annotations

from pathlib import Path

import pytest

from guardian_platform.core.repository.analyzer import RepositoryAnalyzer
from guardian_platform.core.repository.models import FileStatus, Recommendation
from guardian_platform.core.repository.protected import (
    ProtectedCategory,
    classify_protected_artifact,
    detect_framework_signals,
    is_non_deletable,
)
from guardian_platform.core.repository.scoring import count_would_be_false_positives
from tests.guardian_platform.conftest import REPO_ROOT, run_main


@pytest.fixture
def protected_repo(tmp_path: Path) -> Path:
    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    (tmp_path / "app" / "api").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "tests" / "unit").mkdir(parents=True)
    (tmp_path / "docker").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)

    (tmp_path / "alembic" / "env.py").write_text("from alembic import op\n", encoding="utf-8")
    (tmp_path / "alembic" / "script.py.mako").write_text("# mako\n", encoding="utf-8")
    (tmp_path / "alembic" / "versions" / "001_init.py").write_text("revision = '001'\n", encoding="utf-8")
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "main.py").write_text("app = 1\n", encoding="utf-8")
    (tmp_path / "app" / "api" / "routes.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "entry.py").write_text(
        "if __name__ == '__main__':\n    print('run')\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "dead_helper.py").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "tests" / "unit" / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "tests" / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (tmp_path / "docs" / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# README\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    (tmp_path / ".guardian.yml").write_text("schema: guardian_project_v1\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
    return tmp_path


class TestProtectedRules:
    def test_package_init(self):
        status, cat, _ = classify_protected_artifact("app/__init__.py")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.PACKAGE_INIT

    def test_alembic_env(self):
        status, cat, _ = classify_protected_artifact("alembic/env.py")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.ALEMBIC

    def test_alembic_migration(self):
        status, cat, _ = classify_protected_artifact("alembic/versions/001_init.py")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.ALEMBIC

    def test_documentation(self):
        status, cat, _ = classify_protected_artifact("docs/GUIDE.md")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.DOCUMENTATION

    def test_readme(self):
        status, cat, _ = classify_protected_artifact("README.md")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.DOCUMENTATION

    def test_pyproject(self):
        status, cat, _ = classify_protected_artifact("pyproject.toml")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.CONFIGURATION

    def test_dockerfile(self):
        status, cat, _ = classify_protected_artifact("Dockerfile")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.CONFIGURATION

    def test_guardian_yml(self):
        status, cat, _ = classify_protected_artifact(".guardian.yml")
        assert status == FileStatus.PROTECTED
        assert cat == ProtectedCategory.CONFIGURATION

    def test_entrypoint_main(self):
        status, cat, _ = classify_protected_artifact("app/main.py")
        assert status == FileStatus.ENTRYPOINT
        assert cat == ProtectedCategory.ENTRYPOINT

    def test_entrypoint_dunder_main(self):
        status, cat, _ = classify_protected_artifact(
            "scripts/run.py",
            is_entry_point=True,
        )
        assert status == FileStatus.ENTRYPOINT

    def test_fastapi_router(self):
        source = "from fastapi import APIRouter\nrouter = APIRouter()\n"
        status, cat, _ = classify_protected_artifact("app/api/routes.py", source=source)
        assert status == FileStatus.FRAMEWORK
        assert cat == ProtectedCategory.FRAMEWORK

    def test_pytest_discovery(self):
        signals = detect_framework_signals("def test_x(): pass", "tests/unit/test_x.py")
        assert "pytest_discovery" in signals

    def test_non_deletable_never_delete(self):
        assert is_non_deletable(FileStatus.PROTECTED, ProtectedCategory.ALEMBIC)
        assert is_non_deletable(FileStatus.ENTRYPOINT, ProtectedCategory.ENTRYPOINT)
        assert is_non_deletable(FileStatus.FRAMEWORK, ProtectedCategory.FRAMEWORK)


class TestProtectedRepoAnalysis:
    def test_protected_files_not_delete(self, protected_repo: Path):
        analysis = RepositoryAnalyzer(protected_repo).analyze()
        protected_paths = [
            "alembic/env.py",
            "alembic/versions/001_init.py",
            "app/__init__.py",
            "docs/GUIDE.md",
            "README.md",
            "pyproject.toml",
            "Dockerfile",
            ".guardian.yml",
            "scripts/entry.py",
            "app/api/routes.py",
            "tests/unit/test_sample.py",
        ]
        for path in protected_paths:
            item = analysis.files[path]
            assert item.recommendation != Recommendation.DELETE, path

    def test_dead_helper_still_delete(self, protected_repo: Path):
        analysis = RepositoryAnalyzer(protected_repo).analyze()
        item = analysis.files["scripts/dead_helper.py"]
        assert item.status == FileStatus.ORPHAN
        assert item.recommendation == Recommendation.DELETE

    def test_false_positives_prevented_summary(self, protected_repo: Path):
        analysis = RepositoryAnalyzer(protected_repo).analyze()
        fp = analysis.false_positives_prevented
        assert fp.total > 0
        assert fp.alembic >= 2
        assert fp.docs >= 2
        assert fp.config >= 3


class TestRegressionIFGRepo:
    def test_alembic_env_not_delete(self, repo_root: Path):
        item = RepositoryAnalyzer(repo_root).get_file("alembic/env.py")
        assert item is not None
        assert item.recommendation != Recommendation.DELETE

    def test_architecture_doc_not_delete(self, repo_root: Path):
        item = RepositoryAnalyzer(repo_root).get_file("docs/GUARDIAN_PLATFORM_ARCHITECTURE.md")
        assert item is not None
        assert item.recommendation != Recommendation.DELETE

    def test_init_py_not_delete(self, repo_root: Path):
        item = RepositoryAnalyzer(repo_root).get_file("app/__init__.py")
        assert item is not None
        assert item.recommendation != Recommendation.DELETE

    def test_orphan_report_excludes_protected(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
        from guardian_platform.core.config.models import ProjectConfig

        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=repo_root),
        )
        analysis = RepositoryAnalyzer(repo_root).analyze()
        orphan_paths = {p for p, f in analysis.files.items() if f.status == FileStatus.ORPHAN}
        assert not any(p.startswith("alembic/") for p in orphan_paths)
        assert not any(p.endswith("/__init__.py") for p in orphan_paths)
        assert not any(p.startswith("docs/") for p in orphan_paths)

    def test_false_positive_count_on_real_repo(self, repo_root: Path):
        analysis = RepositoryAnalyzer(repo_root).analyze()
        prevented = count_would_be_false_positives(analysis.files)
        assert prevented > 0
        delete_on_protected = [
            p
            for p, f in analysis.files.items()
            if f.recommendation == Recommendation.DELETE
            and (
                p.startswith("alembic/")
                or p.endswith("/__init__.py")
                or p.startswith("docs/")
                or p == "README.md"
            )
        ]
        assert delete_on_protected == []

    def test_repo_graph_shows_false_positives(self, repo_root: Path, monkeypatch: pytest.MonkeyPatch):
        from guardian_platform.core.config.models import ProjectConfig

        monkeypatch.setattr(
            "guardian_platform.core.cli.app.load_project_config",
            lambda **kwargs: ProjectConfig(root=repo_root),
        )
        code, out = run_main(["repo", "graph"])
        assert code == 0
        assert "false_positives_prevented" in out or "tracked_nodes" in out
