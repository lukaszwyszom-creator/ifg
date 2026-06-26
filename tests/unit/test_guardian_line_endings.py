"""Unit tests for Guardian CRLF / line-ending classification."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.line_endings import (  # noqa: E402
    Confidence,
    LineEndingCategory,
    analyze_line_endings,
)


def _mock_git_diff_clean(*args, **kwargs):
    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    return Result()


def _mock_git_diff_dirty(*args, **kwargs):
    class Result:
        returncode = 1
        stdout = "diff"
        stderr = ""

    return Result()


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> None:
    _run_git(["init"], cwd=tmp_path)
    _run_git(["config", "user.email", "guardian@test"], cwd=tmp_path)
    _run_git(["config", "user.name", "Guardian Test"], cwd=tmp_path)


class TestAnalyzeLineEndingsMocked:
    """Pure logic tests with mocked blob reads and git diff."""

    def test_crlf_only_high_confidence_when_only_eol_differs(self):
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=b"line\n"),
            patch("ifg_guardian.core.line_endings._read_index", return_value=b"line\n"),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=b"line\r\n"),
            patch("ifg_guardian.core.line_endings._run_git", side_effect=_mock_git_diff_clean),
        ):
            result = analyze_line_endings("example.py")

        assert result.category == LineEndingCategory.CRLF_ONLY
        assert result.confidence == Confidence.HIGH
        assert result.restore_would_help is True
        assert any("restore simulation" in v for v in result.verification)

    def test_unknown_when_head_index_worktree_raw_identical(self):
        """False positive case: deps.py — CRLF everywhere, restore useless."""
        crlf = b"import os\r\n\r\n"
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=crlf),
            patch("ifg_guardian.core.line_endings._read_index", return_value=crlf),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=crlf),
            patch("ifg_guardian.core.line_endings._run_git", side_effect=_mock_git_diff_clean),
        ):
            result = analyze_line_endings("app/api/deps.py")

        assert result.category == LineEndingCategory.UNKNOWN_LINE_ENDINGS
        assert result.confidence == Confidence.LOW
        assert result.restore_would_help is False
        assert "restore nic nie zmieni" in result.note

    def test_not_line_ending_when_content_differs(self):
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=b"a\n"),
            patch("ifg_guardian.core.line_endings._read_index", return_value=b"a\n"),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=b"b\n"),
            patch("ifg_guardian.core.line_endings._run_git", side_effect=_mock_git_diff_clean),
        ):
            result = analyze_line_endings("changed.py")

        assert result.category == LineEndingCategory.NOT_LINE_ENDING
        assert result.confidence == Confidence.HIGH

    def test_unknown_when_git_diff_inconsistent(self):
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=b"x\n"),
            patch("ifg_guardian.core.line_endings._read_index", return_value=b"x\n"),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=b"x\r\n"),
            patch(
                "ifg_guardian.core.line_endings._run_git",
                side_effect=lambda args: (
                    _mock_git_diff_dirty()
                    if args[:2] == ["diff", "--ignore-cr-at-eol"]
                    else _mock_git_diff_clean()
                ),
            ),
        ):
            result = analyze_line_endings("inconsistent.py")

        assert result.category == LineEndingCategory.UNKNOWN_LINE_ENDINGS
        assert result.confidence == Confidence.LOW
        assert result.restore_would_help is False

    def test_unknown_medium_when_index_equals_worktree_but_head_differs(self):
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=b"line\n"),
            patch("ifg_guardian.core.line_endings._read_index", return_value=b"line\r\n"),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=b"line\r\n"),
            patch("ifg_guardian.core.line_endings._run_git", side_effect=_mock_git_diff_clean),
        ):
            result = analyze_line_endings("staged_crlf.py")

        assert result.category == LineEndingCategory.UNKNOWN_LINE_ENDINGS
        assert result.confidence == Confidence.MEDIUM
        assert result.restore_would_help is False
        assert "restore nie zmieni" in result.note

    def test_verification_includes_required_checks(self):
        with (
            patch("ifg_guardian.core.line_endings._read_head", return_value=b"a\n"),
            patch("ifg_guardian.core.line_endings._read_index", return_value=b"a\n"),
            patch("ifg_guardian.core.line_endings._read_worktree", return_value=b"a\r\n"),
            patch("ifg_guardian.core.line_endings._run_git", side_effect=_mock_git_diff_clean),
        ):
            result = analyze_line_endings("checks.py")

        joined = "\n".join(result.verification)
        assert "git diff --ignore-cr-at-eol" in joined
        assert "HEAD vs working tree (raw bytes)" in joined
        assert "git ls-files --eol" in joined
        assert "file" in joined
        assert "restore simulation" in joined


class TestAnalyzeLineEndingsGitRepo:
    """Integration tests against a real temporary git repository."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path):
        _init_repo(tmp_path)
        return tmp_path

    def test_real_crlf_only_restore_would_help(self, git_repo: Path):
        file_path = git_repo / "sample.py"
        file_path.write_text("hello\n", encoding="utf-8", newline="\n")
        _run_git(["add", "sample.py"], cwd=git_repo)
        _run_git(["commit", "-m", "lf"], cwd=git_repo)

        file_path.write_bytes(b"hello\r\n")

        with patch("ifg_guardian.core.line_endings.ROOT", git_repo):
            result = analyze_line_endings("sample.py")

        assert result.category == LineEndingCategory.CRLF_ONLY
        assert result.restore_would_help is True
        assert result.confidence == Confidence.HIGH

    def test_real_identical_crlf_unknown_not_crlf_only(self, git_repo: Path):
        file_path = git_repo / "deps.py"
        file_path.write_bytes(b"import x\r\n")
        _run_git(["add", "deps.py"], cwd=git_repo)
        _run_git(["commit", "-m", "crlf"], cwd=git_repo)

        with patch("ifg_guardian.core.line_endings.ROOT", git_repo):
            result = analyze_line_endings("deps.py")

        assert result.category == LineEndingCategory.UNKNOWN_LINE_ENDINGS
        assert result.restore_would_help is False
