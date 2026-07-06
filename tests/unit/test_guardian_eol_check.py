"""Unit tests for repo.eol_check — EOL-only vs logical diff classification."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.repo_audit.eol_check import (  # noqa: E402
    EolClassification,
    EolVerdict,
    classify_file_eol,
    classify_from_diff_flags,
    collect_tracked_modified_paths,
    compute_verdict,
    is_tracked_modified_status,
    run_eol_check,
)


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
    _run_git(["config", "core.autocrlf", "false"], cwd=tmp_path)
    (tmp_path / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8")


def _mock_git_diff(normal_dirty: bool, ignore_cr_dirty: bool):
    def side_effect(_root, *args):
        cmd = list(args)
        code = 0
        if "--ignore-cr-at-eol" in cmd:
            code = 1 if ignore_cr_dirty else 0
        elif cmd[:2] == ("diff", "HEAD"):
            code = 1 if normal_dirty else 0
        result = subprocess.CompletedProcess(args=cmd, returncode=code, stdout="", stderr="")
        return result

    return side_effect


class TestIsTrackedModifiedStatus:
    @pytest.mark.parametrize(
        "status,expected",
        [
            (" M", True),
            ("M ", True),
            ("MM", True),
            ("AM", True),
            ("??", False),
            (" D", False),
            ("D ", False),
            ("A ", False),
        ],
    )
    def test_status_codes(self, status: str, expected: bool):
        assert is_tracked_modified_status(status) == expected


class TestClassifyFromDiffFlags:
    def test_eol_only(self):
        cls, note = classify_from_diff_flags(True, False)
        assert cls == EolClassification.EOL_ONLY
        assert "ignore-cr" in note

    def test_logical_change(self):
        cls, _ = classify_from_diff_flags(True, True)
        assert cls == EolClassification.LOGICAL_CHANGE

    def test_unknown_when_no_normal_diff(self):
        cls, _ = classify_from_diff_flags(False, False)
        assert cls == EolClassification.UNKNOWN


class TestClassifyFileEol:
    def test_eol_only_when_normalized_matches_head_despite_git_diff(self):
        with (
            patch(
                "ifg_guardian.core.repo_audit.eol_check._run_git",
                side_effect=_mock_git_diff(normal_dirty=True, ignore_cr_dirty=True),
            ),
            patch(
                "ifg_guardian.core.repo_audit.eol_check._normalized_content_matches_head",
                return_value=True,
            ),
        ):
            result = classify_file_eol("app/persistence/repositories/transmission_repository.py")

        assert result.classification == EolClassification.EOL_ONLY
        assert "false positive" in result.note

    def test_unknown_when_porcelain_m_but_no_normal_diff(self):
        with patch(
            "ifg_guardian.core.repo_audit.eol_check._run_git",
            side_effect=_mock_git_diff(normal_dirty=False, ignore_cr_dirty=False),
        ):
            result = classify_file_eol("app/api/deps.py", root=Path("/tmp/repo"))

        assert result.classification == EolClassification.UNKNOWN
        assert result.normal_diff is False


class TestComputeVerdict:
    def _file(self, path: str, cls: EolClassification):
        from ifg_guardian.core.repo_audit.eol_check import EolFileResult

        return EolFileResult(path=path, status=" M", classification=cls)

    def test_go_when_no_modified_files(self):
        verdict, _ = compute_verdict([])
        assert verdict == EolVerdict.GO

    def test_no_go_when_logical_change(self):
        files = [self._file("a.py", EolClassification.LOGICAL_CHANGE)]
        verdict, msg = compute_verdict(files)
        assert verdict == EolVerdict.NO_GO
        assert "logical" in msg.lower()

    def test_go_with_caution_when_all_eol_only(self):
        files = [
            self._file("a.py", EolClassification.EOL_ONLY),
            self._file("b.py", EolClassification.EOL_ONLY),
        ]
        verdict, msg = compute_verdict(files)
        assert verdict == EolVerdict.GO_WITH_CAUTION
        assert "manual" in msg.lower()

    def test_no_go_when_unknown_present(self):
        files = [
            self._file("a.py", EolClassification.EOL_ONLY),
            self._file("b.py", EolClassification.UNKNOWN),
        ]
        verdict, _ = compute_verdict(files)
        assert verdict == EolVerdict.NO_GO


class TestCollectTrackedModifiedPaths:
    def test_filters_untracked_and_deleted(self):
        porcelain = "\n".join(
            [
                " M app/api/deps.py",
                "?? docs/new.md",
                " D removed.py",
                "M  staged.py",
            ]
        )
        paths = collect_tracked_modified_paths(porcelain)
        path_names = [p[1] for p in paths]
        assert "app/api/deps.py" in path_names
        assert "staged.py" in path_names
        assert "docs/new.md" not in path_names
        assert "removed.py" not in path_names


class TestEolCheckIntegration:
    def test_real_repo_eol_only_file(self, tmp_path: Path):
        _init_repo(tmp_path)
        sample = tmp_path / "sample.py"
        sample.write_text("line\n", encoding="utf-8", newline="\n")
        _run_git(["add", "sample.py"], cwd=tmp_path)
        _run_git(["commit", "-m", "init"], cwd=tmp_path)
        sample.write_text("line\r\n", encoding="utf-8", newline="\r\n")

        with patch("ifg_guardian.core.repo_audit.eol_check.ROOT", tmp_path):
            result = run_eol_check(root=tmp_path)

        assert len(result.files) == 1
        assert result.files[0].classification == EolClassification.EOL_ONLY
        assert result.verdict == EolVerdict.GO_WITH_CAUTION

    def test_real_repo_logical_change(self, tmp_path: Path):
        _init_repo(tmp_path)
        sample = tmp_path / "sample.py"
        sample.write_text("a\n", encoding="utf-8")
        _run_git(["add", "sample.py"], cwd=tmp_path)
        _run_git(["commit", "-m", "init"], cwd=tmp_path)
        sample.write_text("b\n", encoding="utf-8")

        with patch("ifg_guardian.core.repo_audit.eol_check.ROOT", tmp_path):
            result = run_eol_check(root=tmp_path)

        assert result.files[0].classification == EolClassification.LOGICAL_CHANGE
        assert result.verdict == EolVerdict.NO_GO
