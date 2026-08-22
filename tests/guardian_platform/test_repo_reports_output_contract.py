"""Output contract tests for core repo graph / orphan / dead-code commands."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from guardian_platform.core.config.models import ProjectConfig
from guardian_platform.core.repository.analyzer import RepositoryAnalyzer
from guardian_platform.core.repository.report import (
    ReportExistsError,
    write_markdown_report,
    write_repository_graph_report,
)
from tests.guardian_platform.conftest import REPO_ROOT, run_main


def _patch_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(
        "guardian_platform.core.cli.app.load_project_config",
        lambda **kwargs: ProjectConfig(root=root),
    )


def _git_init_commit(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "gp@test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "GP Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)


def _git_status_porcelain(repo: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain=v1", "-uall"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


@pytest.fixture
def report_repo(tmp_path: Path) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "reports").mkdir(parents=True)
    (tmp_path / "app" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app" / "used.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "app" / "orphan.py").write_text("UNUSED = 1\n", encoding="utf-8")
    (tmp_path / "scripts" / "dead.py").write_text("X = 1\n", encoding="utf-8")
    return tmp_path


CANONICAL_REPORTS = {
    "graph": ("repository_graph.md", "# Repository Dependency Graph"),
    "orphan": ("repository_orphans.md", "# Repository Orphans"),
    "dead-code": ("repository_dead_code.md", "# Repository Dead Code Candidates"),
}


class TestGraphOutputContract:
    command = ["repo", "graph"]
    title = "# Repository Dependency Graph"
    canonical_name = "repository_graph.md"
    report_label = "Graph report"

    @pytest.fixture(autouse=True)
    def _setup(self, report_repo: Path, monkeypatch: pytest.MonkeyPatch):
        self.repo = report_repo
        _patch_root(monkeypatch, report_repo)

    def test_default_stdout_markdown(self):
        code, out = run_main(self.command)
        assert code == 0
        assert self.title in out

    def test_default_does_not_create_canonical_report(self):
        canonical = self.repo / "docs" / "reports" / self.canonical_name
        code, _ = run_main(self.command)
        assert code == 0
        assert not canonical.exists()

    def test_default_preserves_existing_tracked_report(self):
        canonical = self.repo / "docs" / "reports" / self.canonical_name
        sentinel = "# canonical tracked report\nunchanged\n"
        canonical.write_text(sentinel, encoding="utf-8")
        code, _ = run_main(self.command)
        assert code == 0
        assert canonical.read_text(encoding="utf-8") == sentinel

    def test_default_git_status_unchanged(self):
        _git_init_commit(self.repo)
        canonical = self.repo / "docs" / "reports" / self.canonical_name
        canonical.write_text("# tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", canonical], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "track report"], cwd=self.repo, check=True, capture_output=True)
        status_before = _git_status_porcelain(self.repo)
        code, _ = run_main(self.command)
        assert code == 0
        assert _git_status_porcelain(self.repo) == status_before

    def test_explicit_output_writes_file(self):
        out_file = self.repo / "tmp" / "custom_report.md"
        code, out = run_main([*self.command, "--output", str(out_file)])
        assert code == 0
        assert out_file.exists()
        assert self.title in out_file.read_text(encoding="utf-8")
        assert f"{self.report_label}: tmp/custom_report.md" in out

    def test_output_refuses_overwrite(self):
        out_file = self.repo / "custom.md"
        out_file.write_text("# existing\n", encoding="utf-8")
        code, out = run_main([*self.command, "--output", str(out_file)])
        assert code == 2
        assert "already exists" in out
        assert out_file.read_text(encoding="utf-8") == "# existing\n"

    def test_output_force_overwrites(self):
        out_file = self.repo / "custom.md"
        out_file.write_text("# existing\n", encoding="utf-8")
        code, _ = run_main([*self.command, "--output", str(out_file), "--force"])
        assert code == 0
        assert self.title in out_file.read_text(encoding="utf-8")

    def test_json_format_no_file_write(self):
        canonical = self.repo / "docs" / "reports" / self.canonical_name
        code, out = run_main(["--format", "json", *self.command])
        assert code == 0
        assert '"title"' in out
        assert not canonical.exists()

    def test_algorithm_metrics_unchanged(self):
        analysis = RepositoryAnalyzer(self.repo).analyze()
        code, out = run_main(self.command)
        assert code == 0
        self._assert_algorithm_output(analysis, out)

    def _assert_algorithm_output(self, analysis, out: str) -> None:
        assert f"**Tracked nodes:** {len(analysis.files)}" in out


class TestOrphanOutputContract(TestGraphOutputContract):
    command = ["repo", "orphan"]
    title = "# Repository Orphans"
    canonical_name = "repository_orphans.md"
    report_label = "Orphans report"

    def _assert_algorithm_output(self, analysis, out: str) -> None:
        orphan_count = sum(1 for item in analysis.files.values() if item.status.value == "ORPHAN")
        assert f"**Count:** {orphan_count}" in out


class TestDeadCodeOutputContract(TestGraphOutputContract):
    command = ["repo", "dead-code"]
    title = "# Repository Dead Code Candidates"
    canonical_name = "repository_dead_code.md"
    report_label = "Dead-code report"

    def _assert_algorithm_output(self, analysis, out: str) -> None:
        dead_count = sum(
            1
            for item in analysis.files.values()
            if item.recommendation.value in {"DELETE", "ARCHIVE"} and item.risk.value == "SAFE"
        )
        assert f"**Count:** {dead_count}" in out


class TestWriteHelpers:
    def test_write_markdown_report_exists_error(self, report_repo: Path):
        out = report_repo / "plan.md"
        out.write_text("# old\n", encoding="utf-8")
        with pytest.raises(ReportExistsError):
            write_markdown_report(report_repo, "# new\n", out)

    def test_programmatic_default_path_write_still_works(self, report_repo: Path):
        analysis = RepositoryAnalyzer(report_repo).analyze()
        path = write_repository_graph_report(report_repo, analysis)
        assert path.exists()
        assert "Repository Dependency Graph" in path.read_text(encoding="utf-8")


class TestRepoRootGuard:
    def test_pkg01_commands_never_touch_conftest_repo_root(
        self,
        report_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _patch_root(monkeypatch, report_repo)
        targets = [
            REPO_ROOT / "docs" / "reports" / name
            for name in ("repository_graph.md", "repository_orphans.md", "repository_dead_code.md")
        ]
        before = {path: (path.read_bytes() if path.exists() else None) for path in targets}
        for command in (["repo", "graph"], ["repo", "orphan"], ["repo", "dead-code"]):
            code, _ = run_main(command)
            assert code == 0
        for path, content in before.items():
            if content is None:
                assert not path.exists()
            else:
                assert path.read_bytes() == content

    def test_conftest_repo_root_is_not_tmp_path(self, tmp_path: Path):
        assert REPO_ROOT.resolve() != tmp_path.resolve()
        assert "ifg_standalone" in str(REPO_ROOT)
