"""Tests for immutable git-archive build snapshots."""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.build_snapshot import (  # noqa: E402
    SnapshotError,
    cleanup_snapshot,
    create_immutable_commit_snapshot,
    reverify_snapshot,
    resolve_commit_sha,
)


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "git failed")
    return (result.stdout or "").strip()


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    # Historical CRLF content + eol=lf attributes (the production failure mode).
    (repo / ".gitattributes").write_text("* text=auto eol=lf\n*.py text eol=lf\n", encoding="utf-8")
    (repo / "app").mkdir()
    # Write CRLF via binary to simulate legacy blob.
    (repo / "app" / "main.py").write_bytes(b"print('hello')\r\nprint('world')\r\n")
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    script = repo / "bin" / "tool.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    link = repo / "link-to-readme"
    link.symlink_to("README.md")
    _git(repo, "add", "-A")
    # Force add without letting clean filter rewrite if possible — still OK if LF.
    _git(repo, "commit", "-m", "initial")
    return repo


class TestImmutableCommitSnapshot:
    def test_crlf_checkout_noise_does_not_block_snapshot(self, tmp_path: Path):
        repo = _init_repo(tmp_path)
        sha = _git(repo, "rev-parse", "HEAD")
        # Simulate checkout noise: touch status by rewriting file with different EOL in WT.
        main = repo / "app" / "main.py"
        main.write_bytes(b"print('hello')\nprint('world')\n")
        porcelain = _git(repo, "status", "--porcelain")
        # May or may not be dirty depending on filters; force an untracked WIP too.
        (repo / "wip_untracked.txt").write_text("wip\n", encoding="utf-8")
        snap = create_immutable_commit_snapshot(repo_root=repo, commit=sha, base_temp_dir=tmp_path / "snaps")
        try:
            assert snap.commit_sha == sha
            assert (snap.tree_dir / "app" / "main.py").is_file()
            assert not (snap.tree_dir / "wip_untracked.txt").exists()
            assert snap.source_wip_detected is True
            assert snap.source_wip_excluded is True
            # Snapshot matches blob bytes (archive), not necessarily working tree.
            blob = subprocess.run(
                ["git", "-C", str(repo), "show", f"{sha}:app/main.py"],
                capture_output=True,
                check=True,
            ).stdout
            assert (snap.tree_dir / "app" / "main.py").read_bytes() == blob
        finally:
            cleanup_snapshot(snap)

    def test_snapshot_matches_commit_and_excludes_untracked(self, tmp_path: Path):
        repo = _init_repo(tmp_path)
        sha = _git(repo, "rev-parse", "HEAD")
        (repo / "secret_untracked.py").write_text("SECRET=1\n", encoding="utf-8")
        snap = create_immutable_commit_snapshot(repo_root=repo, commit="HEAD", base_temp_dir=tmp_path / "snaps")
        try:
            assert snap.commit_sha == sha
            assert not (snap.tree_dir / "secret_untracked.py").exists()
            assert (snap.tree_dir / "README.md").read_text(encoding="utf-8") == "readme\n"
        finally:
            cleanup_snapshot(snap)

    def test_excludes_unstaged_and_staged_changes(self, tmp_path: Path):
        repo = _init_repo(tmp_path)
        sha = _git(repo, "rev-parse", "HEAD")
        readme = repo / "README.md"
        original = readme.read_text(encoding="utf-8")
        # Unstaged change
        readme.write_text("unstaged change\n", encoding="utf-8")
        # Staged but uncommitted change to another file
        (repo / "app" / "main.py").write_bytes(b"print('staged')\n")
        _git(repo, "add", "app/main.py")
        snap = create_immutable_commit_snapshot(repo_root=repo, commit=sha, base_temp_dir=tmp_path / "snaps")
        try:
            assert (snap.tree_dir / "README.md").read_text(encoding="utf-8") == original
            blob = subprocess.run(
                ["git", "-C", str(repo), "show", f"{sha}:app/main.py"],
                capture_output=True,
                check=True,
            ).stdout
            assert (snap.tree_dir / "app" / "main.py").read_bytes() == blob
            assert snap.source_wip_detected is True
        finally:
            cleanup_snapshot(snap)

    def test_tamper_after_verify_blocks(self, tmp_path: Path):
        repo = _init_repo(tmp_path)
        snap = create_immutable_commit_snapshot(repo_root=repo, commit="HEAD", base_temp_dir=tmp_path / "snaps")
        try:
            reverify_snapshot(snap, repo_root=repo)
            target = snap.tree_dir / "README.md"
            target.write_text("tampered\n", encoding="utf-8")
            with pytest.raises(SnapshotError, match="manifest hash mismatch|content hash"):
                reverify_snapshot(snap, repo_root=repo)
        finally:
            cleanup_snapshot(snap)

    def test_invalid_sha_blocks(self, tmp_path: Path):
        repo = _init_repo(tmp_path)
        with pytest.raises(SnapshotError, match="invalid or unknown commit"):
            create_immutable_commit_snapshot(
                repo_root=repo,
                commit="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                base_temp_dir=tmp_path / "snaps",
            )

    def test_symlink_and_executable_preserved(self, tmp_path: Path):
        repo = _init_repo(tmp_path)
        snap = create_immutable_commit_snapshot(repo_root=repo, commit="HEAD", base_temp_dir=tmp_path / "snaps")
        try:
            link = snap.tree_dir / "link-to-readme"
            assert link.is_symlink()
            assert os.readlink(link) == "README.md"
            tool = snap.tree_dir / "bin" / "tool.sh"
            assert tool.is_file()
            assert tool.stat().st_mode & stat.S_IXUSR
            reverify_snapshot(snap, repo_root=repo)
        finally:
            cleanup_snapshot(snap)

    def test_eol_noise_vs_real_content_change(self, tmp_path: Path):
        """Regression: EOL-only WT rewrite must not equal a real content change in snapshot."""
        repo = _init_repo(tmp_path)
        sha = resolve_commit_sha(repo, "HEAD")
        blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"{sha}:app/main.py"],
            capture_output=True,
            check=True,
        ).stdout
        # Working tree: EOL flip only (may look dirty under eol=lf).
        eol_flipped = blob.replace(b"\r\n", b"\n") if b"\r\n" in blob else blob.replace(b"\n", b"\r\n")
        (repo / "app" / "main.py").write_bytes(eol_flipped)
        # Real content change staged separately would differ — snapshot must keep blob.
        snap = create_immutable_commit_snapshot(repo_root=repo, commit=sha, base_temp_dir=tmp_path / "snaps")
        try:
            snap_bytes = (snap.tree_dir / "app" / "main.py").read_bytes()
            assert snap_bytes == blob
            assert snap_bytes != eol_flipped or eol_flipped == blob
            # Real content change is also excluded until committed.
            (repo / "app" / "main.py").write_bytes(b"print('REAL_CHANGE')\n")
            snap2 = create_immutable_commit_snapshot(repo_root=repo, commit=sha, base_temp_dir=tmp_path / "snaps")
            try:
                assert (snap2.tree_dir / "app" / "main.py").read_bytes() == blob
                assert (snap2.tree_dir / "app" / "main.py").read_bytes() != b"print('REAL_CHANGE')\n"
            finally:
                cleanup_snapshot(snap2)
        finally:
            cleanup_snapshot(snap)
