"""Output and root isolation tests for `ifg repo audit`."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from guardian_platform.core.config.models import ProjectConfig
from guardian_platform.profiles.ifg.commands.repo_audit import run_repo_audit_cmd
from guardian_platform.profiles.ifg.repo_audit.runner import run_repo_audit
from tests.guardian_platform.conftest import REPO_ROOT, run_main


def _patch_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(
        "guardian_platform.core.cli.app.load_project_config",
        lambda **kwargs: ProjectConfig(root=root),
    )


def _git_init_production(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "gp@test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "GP Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "branch", "-M", "production"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# audit repo\n", encoding="utf-8")
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


def _audit_reports(repo: Path) -> set[Path]:
    audit_dir = repo / "docs" / "guardian"
    if not audit_dir.exists():
        return set()
    return set(audit_dir.glob("REPO_AUDIT_*.md"))


@pytest.fixture
def audit_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "audit_repo"
    repo.mkdir()
    (repo / "docs" / "guardian").mkdir(parents=True)
    _git_init_production(repo)
    return repo


@pytest.fixture
def repo_b(tmp_path: Path) -> Path:
    repo = tmp_path / "repo_b"
    repo.mkdir()
    _git_init_production(repo)
    (repo / "ONLY_IN_B.txt").write_text("B\n", encoding="utf-8")
    subprocess.run(["git", "add", "ONLY_IN_B.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "b marker"], cwd=repo, check=True, capture_output=True)
    return repo


class TestRootPropagation:
    def test_handler_passes_ctx_root_to_runner(self, audit_repo: Path):
        ctx = ProjectConfig.defaults(audit_repo)
        command_ctx = __import__(
            "guardian_platform.core.runtime.context", fromlist=["CommandContext"]
        ).CommandContext(root=audit_repo, config=ctx, argv=["ifg", "repo", "audit"])

        with patch("guardian_platform.profiles.ifg.commands.repo_audit.run_repo_audit") as mock_run:
            mock_run.return_value = 0
            code = run_repo_audit_cmd(command_ctx)
        assert code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["root"] == audit_repo

    def test_runner_rejects_missing_root(self, tmp_path: Path):
        missing = tmp_path / "missing"
        code = run_repo_audit(root=missing)
        assert code == 2

    def test_runner_rejects_non_git_directory(self, tmp_path: Path):
        plain = tmp_path / "plain"
        plain.mkdir()
        code = run_repo_audit(root=plain)
        assert code == 2


class TestRootIsolation:
    def test_repo_a_not_read_from_canonical_repo_root(
        self,
        audit_repo: Path,
        repo_b: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        import io
        from contextlib import redirect_stdout

        monkeypatch.setattr("guardian_platform.profiles.ifg.config.defaults.REPO_ROOT", repo_b)
        (audit_repo / "MARKER_A.txt").write_text("marker-a\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = run_repo_audit(root=audit_repo, output_format="markdown")
        out = buf.getvalue()
        assert code in (0, 1)
        assert "MARKER_A.txt" in out
        assert "ONLY_IN_B.txt" not in out

    def test_canonical_repo_root_constant_does_not_redirect_cli_root(
        self,
        audit_repo: Path,
        repo_b: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr("guardian_platform.profiles.ifg.config.defaults.REPO_ROOT", repo_b)
        _patch_root(monkeypatch, audit_repo)
        marker = audit_repo / "MARKER_A.txt"
        marker.write_text("marker-a\n", encoding="utf-8")
        code, out = run_main(["--format", "markdown", "ifg", "repo", "audit"])
        assert code in (0, 1)
        assert "MARKER_A.txt" in out
        assert "ONLY_IN_B.txt" not in out


class TestOutputContract:
    @pytest.mark.parametrize("fmt,needle", [
        ("terminal", "IFG Guardian — Repo Audit"),
        ("markdown", "# IFG Guardian — Repo Audit"),
        ("json", '"repo_audit_report_v1"'),
    ])
    def test_default_stdout_for_format(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch, fmt: str, needle: str):
        _patch_root(monkeypatch, audit_repo)
        before = _audit_reports(audit_repo)
        code, out = run_main(["--format", fmt, "ifg", "repo", "audit"])
        assert code in (0, 1)
        assert needle in out
        assert _audit_reports(audit_repo) == before

    def test_default_does_not_create_repo_audit_file(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_root(monkeypatch, audit_repo)
        before = _audit_reports(audit_repo)
        code, _ = run_main(["ifg", "repo", "audit"])
        assert code in (0, 1)
        assert _audit_reports(audit_repo) == before

    def test_default_preserves_existing_tracked_audit_report(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        report = audit_repo / "docs" / "guardian" / "REPO_AUDIT_2026_08_22.md"
        sentinel = "# canonical tracked audit\nunchanged\n"
        report.write_text(sentinel, encoding="utf-8")
        _patch_root(monkeypatch, audit_repo)
        code, _ = run_main(["ifg", "repo", "audit"])
        assert code in (0, 1)
        assert report.read_text(encoding="utf-8") == sentinel

    def test_default_git_status_unchanged(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        report = audit_repo / "docs" / "guardian" / "REPO_AUDIT_2026_08_22.md"
        report.write_text("# tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", report.relative_to(audit_repo)], cwd=audit_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "track audit"], cwd=audit_repo, check=True, capture_output=True)
        status_before = _git_status_porcelain(audit_repo)
        _patch_root(monkeypatch, audit_repo)
        code, _ = run_main(["ifg", "repo", "audit"])
        assert code in (0, 1)
        assert _git_status_porcelain(audit_repo) == status_before

    def test_relative_output_writes_under_repo_root(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        out_file = audit_repo / "tmp" / "custom_audit.md"
        _patch_root(monkeypatch, audit_repo)
        code, out = run_main(["ifg", "repo", "audit", "--output", "tmp/custom_audit.md"])
        assert code in (0, 1)
        assert out_file.exists()
        assert "# IFG Guardian — Repo Audit" in out_file.read_text(encoding="utf-8")
        assert "Audit report: tmp/custom_audit.md" in out

    def test_absolute_output_writes_exact_path(self, audit_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        out_file = tmp_path / "absolute_audit.md"
        _patch_root(monkeypatch, audit_repo)
        code, out = run_main(["ifg", "repo", "audit", "--output", str(out_file)])
        assert code in (0, 1)
        assert out_file.exists()
        assert "Audit report:" in out

    def test_json_output_writes_json_file(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        out_file = audit_repo / "audit.json"
        _patch_root(monkeypatch, audit_repo)
        code, out = run_main(["--format", "json", "ifg", "repo", "audit", "--output", str(out_file)])
        assert code in (0, 1)
        assert '"repo_audit_report_v1"' in out_file.read_text(encoding="utf-8")
        assert '"repo_audit_report_v1"' in out

    def test_output_refuses_overwrite(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        out_file = audit_repo / "audit.md"
        out_file.write_text("# existing\n", encoding="utf-8")
        _patch_root(monkeypatch, audit_repo)
        code, out = run_main(["ifg", "repo", "audit", "--output", str(out_file)])
        assert code == 2
        assert "already exists" in out
        assert out_file.read_text(encoding="utf-8") == "# existing\n"

    def test_output_force_overwrites(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        out_file = audit_repo / "audit.md"
        out_file.write_text("# existing\n", encoding="utf-8")
        _patch_root(monkeypatch, audit_repo)
        code, _ = run_main(["ifg", "repo", "audit", "--output", str(out_file), "--force"])
        assert code in (0, 1)
        assert "# IFG Guardian — Repo Audit" in out_file.read_text(encoding="utf-8")


class TestGWO0010Regression:
    def test_no_symlinks_in_pkg02_tests(self):
        import ast

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"symlink", "symlink_to"}:
                    pytest.fail(f"writable symlink API used: {node.func.attr}")

    def test_fixture_scripts_write_only_under_tmp_path(self, tmp_path: Path):
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        target = scripts / "guardian.py"
        target.write_text("print(1)\n", encoding="utf-8")
        assert target.read_text(encoding="utf-8") == "print(1)\n"
        assert not target.is_symlink()

    def test_real_guardian_entrypoint_not_used_as_writable_fixture(self, audit_repo: Path, monkeypatch: pytest.MonkeyPatch):
        before = REPO_ROOT.joinpath("scripts", "guardian.py").read_bytes()
        _patch_root(monkeypatch, audit_repo)
        code, _ = run_main(["ifg", "repo", "audit"])
        assert code in (0, 1)
        after = REPO_ROOT.joinpath("scripts", "guardian.py").read_bytes()
        assert before == after


class TestRepoRootGuard:
    def test_pkg02_commands_do_not_write_under_conftest_repo_root(
        self,
        audit_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        _patch_root(monkeypatch, audit_repo)
        target = REPO_ROOT / "docs" / "guardian"
        before = {p.read_bytes() for p in target.glob("REPO_AUDIT_*.md")} if target.exists() else set()
        code, _ = run_main(["ifg", "repo", "audit"])
        assert code in (0, 1)
        after = {p.read_bytes() for p in target.glob("REPO_AUDIT_*.md")} if target.exists() else set()
        assert before == after
