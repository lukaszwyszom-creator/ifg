"""Zmiany w repozytorium istotne dla decyzji deploy (commit + dirty + untracked)."""
from __future__ import annotations

from ifg_guardian.config import TARGET_BRANCH
from ifg_guardian.core.git import git
from ifg_guardian.plugins.ifg.deploy_decision.paths import (
    is_backend_deploy_path,
    is_frontend_deploy_path,
    is_image_context_path,
)


def _unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in paths:
        path = raw.strip().replace("\\", "/").lstrip("./")
        if not path or path in seen:
            continue
        seen.add(path)
        ordered.append(path)
    return ordered


def list_deploy_changed_files(*, base_ref: str | None = None) -> list[str]:
    """Pliki zmienione względem origin/production oraz lokalnie (dirty tracked)."""
    ref = base_ref or f"origin/{TARGET_BRANCH}"
    collected: list[str] = []
    for command in (
        ["diff", "--name-only", f"{ref}...HEAD"],
        ["diff", "--name-only", "HEAD"],
        ["diff", "--name-only", "--cached", "HEAD"],
    ):
        try:
            output = git(*command)
        except RuntimeError:
            continue
        if output:
            collected.extend(line.strip() for line in output.splitlines() if line.strip())
    return _unique_paths(collected)


def list_untracked_files() -> list[str]:
    """Nieśledzone pliki (z uwzględnieniem .gitignore)."""
    try:
        output = git("ls-files", "--others", "--exclude-standard")
    except RuntimeError:
        return []
    if not output:
        return []
    return _unique_paths([line.strip() for line in output.splitlines() if line.strip()])


def list_dirty_tracked_files() -> list[str]:
    """Zmienione lub staged pliki względem HEAD (bez untracked)."""
    collected: list[str] = []
    for command in (
        ["diff", "--name-only", "HEAD"],
        ["diff", "--name-only", "--cached", "HEAD"],
    ):
        try:
            output = git(*command)
        except RuntimeError:
            continue
        if output:
            collected.extend(line.strip() for line in output.splitlines() if line.strip())
    return _unique_paths(collected)


def list_committed_changes_vs_origin(*, base_ref: str | None = None) -> list[str]:
    ref = base_ref or f"origin/{TARGET_BRANCH}"
    try:
        output = git("diff", "--name-only", f"{ref}...HEAD")
    except RuntimeError:
        return []
    if not output:
        return []
    return _unique_paths([line.strip() for line in output.splitlines() if line.strip()])


def list_image_context_changed_files(*, base_ref: str | None = None) -> list[str]:
    """Wszystkie zmiany image-context: commit vs origin + dirty tracked + untracked."""
    combined = (
        list_deploy_changed_files(base_ref=base_ref)
        + list_untracked_files()
    )
    return _unique_paths([p for p in combined if is_image_context_path(p)])


def list_dirty_image_context_files() -> list[str]:
    """Niezacommitowane zmiany w kontekście obrazu (tracked dirty + untracked)."""
    combined = list_dirty_tracked_files() + list_untracked_files()
    return _unique_paths([p for p in combined if is_image_context_path(p)])


def list_committed_image_context_changes(*, base_ref: str | None = None) -> list[str]:
    return _unique_paths(
        [p for p in list_committed_changes_vs_origin(base_ref=base_ref) if is_image_context_path(p)]
    )


def split_deploy_changes(paths: list[str]) -> tuple[list[str], list[str]]:
    backend = [p for p in paths if is_backend_deploy_path(p)]
    frontend = [p for p in paths if is_frontend_deploy_path(p)]
    return backend, frontend


def current_git_head() -> str:
    try:
        return (git("rev-parse", "HEAD") or "").strip()
    except RuntimeError:
        return ""
