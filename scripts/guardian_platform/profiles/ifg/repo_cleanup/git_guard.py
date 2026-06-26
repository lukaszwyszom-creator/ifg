from __future__ import annotations

import subprocess
from pathlib import Path

from guardian_platform.core.git.client import git_available, status_porcelain
from guardian_platform.profiles.ifg.infra.git import porcelain_is_dirty

UNCOMMITTED_CHANGES_MESSAGE: tuple[str, ...] = (
    "Repository contains uncommitted changes.",
    "Commit or stash changes before repository cleanup.",
)


def _normalize_rel_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def has_uncommitted_changes(root: Path) -> bool:
    if not git_available(root):
        return False
    return porcelain_is_dirty(status_porcelain(root))


def is_git_tracked_path(root: Path, rel: str) -> bool:
    normalized = _normalize_rel_path(rel)
    if not normalized or not git_available(root):
        return False

    exact = subprocess.run(
        ["git", "ls-files", "--error-unmatch", normalized],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if exact.returncode == 0:
        return True

    under = subprocess.run(
        ["git", "ls-files", f"{normalized}/"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(under.stdout.strip())


def phase_requires_clean_worktree(phase: int | None) -> bool:
    return phase is not None and phase >= 1
