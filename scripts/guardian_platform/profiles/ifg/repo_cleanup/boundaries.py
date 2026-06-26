from __future__ import annotations

from pathlib import Path

from guardian_platform.profiles.ifg.repo_cleanup.git_guard import is_git_tracked_path

# Logical IFG repo roots — scan and cleanup only within these trees.
REPO_SCAN_ROOTS: tuple[str, ...] = (
    "app",
    "scripts",
    "docs",
    "tests",
    "frontend-react",
    "alembic",
    "mobile-expo",
    "docker",
    "agent",
)

# Root-level local artifacts (phase 0) — not descended from scan roots.
ROOT_ARTIFACT_PATHS: tuple[str, ...] = (
    ".pytest_cache",
    ".logs",
    "tmp",
)

# Never enter or emit paths containing these path segments.
FORBIDDEN_PATH_PARTS: frozenset[str] = frozenset(
    {
        ".venv",
        ".venv313",
        ".git",
        "node_modules",
        "site-packages",
        ".idea",
        ".vscode",
        ".cursor",
        ".guardian",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "dist-info",
        ".eggs",
    }
)

# Patterns searched only inside REPO_SCAN_ROOTS (not repo-wide glob).
SCAN_ROOT_ARTIFACT_GLOBS: tuple[str, ...] = (
    "**/__pycache__",
    "**/.DS_Store",
    "**/*.pyc",
)


def normalize_rel_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/").lstrip("/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def path_has_forbidden_segment(rel: str) -> bool:
    parts = normalize_rel_path(rel).split("/")
    return any(part in FORBIDDEN_PATH_PARTS for part in parts)


def is_within_repo_boundary(rel: str) -> bool:
    normalized = normalize_rel_path(rel)
    if not normalized or path_has_forbidden_segment(normalized):
        return False

    if normalized in ROOT_ARTIFACT_PATHS:
        return True

    first = normalized.split("/", 1)[0]
    if first in REPO_SCAN_ROOTS:
        return True

    # Allow only root-level __pycache__ if ever present (rare).
    if normalized == "__pycache__" or normalized.startswith("__pycache__/"):
        return True

    return False


def _iter_scan_root(base: Path, glob_pattern: str) -> list[Path]:
    if glob_pattern.startswith("**/"):
        return sorted(base.glob(glob_pattern))
    return sorted(base.glob(glob_pattern)) if (base / glob_pattern).exists() else []


def _is_phase0_safe_untracked(root: Path, rel: str) -> bool:
    if not is_within_repo_boundary(rel):
        return False
    return not is_git_tracked_path(root, rel)


def discover_phase0_artifacts(root: Path) -> list[str]:
    """Discover local, untracked artifacts strictly inside repo boundaries."""
    found: set[str] = set()

    for name in ROOT_ARTIFACT_PATHS:
        target = root / name
        if target.exists() and _is_phase0_safe_untracked(root, name):
            found.add(name)

    for scan_root in REPO_SCAN_ROOTS:
        base = root / scan_root
        if not base.is_dir():
            continue
        for pattern in SCAN_ROOT_ARTIFACT_GLOBS:
            for match in _iter_scan_root(base, pattern):
                if pattern == "**/__pycache__" and not match.is_dir():
                    continue
                if pattern == "**/*.pyc":
                    if "__pycache__" in match.parts:
                        continue
                    if not match.is_file():
                        continue
                rel = normalize_rel_path(match.relative_to(root))
                if _is_phase0_safe_untracked(root, rel):
                    found.add(rel)

    return sorted(found)
