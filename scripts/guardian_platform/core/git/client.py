from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise GitError(detail or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def git_available(root: Path) -> bool:
    try:
        run_git(root, "rev-parse", "--is-inside-work-tree")
        return True
    except (GitError, OSError):
        return False


def current_branch(root: Path) -> str:
    return run_git(root, "rev-parse", "--abbrev-ref", "HEAD")


def short_sha(root: Path, ref: str = "HEAD") -> str:
    return run_git(root, "rev-parse", "--short", ref)


def status_porcelain(root: Path) -> str:
    return run_git(root, "status", "--porcelain")


def is_dirty(root: Path) -> bool:
    return bool(status_porcelain(root).strip())
