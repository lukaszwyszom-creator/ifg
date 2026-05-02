"""git_guard.py - prosty raport bezpieczenstwa dla lokalnych zmian git.

Nie modyfikuje zadnych plikow aplikacji IFG.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


_BLOCKED_PREFIXES: tuple[str, ...] = (
    "app/domain/",
    "alembic/",
    "app/persistence/mappers/",
)
_MAX_FILES = 3
_MAX_LINES = 300
_SUMMARY_RE = re.compile(
    r"(?P<files>\d+) files? changed(?:, (?P<insertions>\d+) insertions?\(\+\))?(?:, (?P<deletions>\d+) deletions?\(-\))?"
)


@dataclass
class DiffReport:
    changed_files: list[str]
    total_files: int
    total_lines: int
    blocked: bool
    reasons: list[str]


def _run_git_command(command: list[str]) -> str:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def _parse_changed_files(name_only_output: str) -> list[str]:
    return [line.strip() for line in name_only_output.splitlines() if line.strip()]


def _parse_untracked_files(status_output: str) -> list[str]:
    untracked_files: list[str] = []
    for line in status_output.splitlines():
        if line.startswith("?? "):
            path = line[3:].strip()
            if path:
                untracked_files.append(path)
    return untracked_files


def _merge_changed_files(diff_files: list[str], untracked_files: list[str]) -> list[str]:
    return sorted(set(diff_files + untracked_files))


def _parse_total_lines(stat_output: str) -> int:
    for line in reversed(stat_output.splitlines()):
        match = _SUMMARY_RE.search(line.strip())
        if not match:
            continue
        insertions = int(match.group("insertions") or 0)
        deletions = int(match.group("deletions") or 0)
        return insertions + deletions
    return 0


def _path_exists_in_head(path: str) -> bool:
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"HEAD:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def _detect_added_files(changed_files: list[str]) -> list[str]:
    added_files: list[str] = []
    for path in changed_files:
        if not _path_exists_in_head(path):
            added_files.append(path)
    return added_files


def build_diff_report(
    changed_files: list[str],
    total_lines: int,
    untracked_files: list[str] | None = None,
) -> DiffReport:
    reasons: list[str] = []
    total_files = len(changed_files)
    untracked_files = untracked_files or []

    for path in changed_files:
        if path.startswith(_BLOCKED_PREFIXES):
            reasons.append(f"blocked path: {path}")

    if total_files > _MAX_FILES:
        reasons.append(f"too many changed files: {total_files} > {_MAX_FILES}")

    if total_lines > _MAX_LINES:
        reasons.append(f"too many changed lines: {total_lines} > {_MAX_LINES}")

    for path in untracked_files:
        if not path.startswith("agent/"):
            reasons.append(f"untracked file outside agent/: {path}")

    return DiffReport(
        changed_files=changed_files,
        total_files=total_files,
        total_lines=total_lines,
        blocked=bool(reasons),
        reasons=reasons,
    )


def check_git_diff() -> DiffReport:
    name_only_output = _run_git_command(["git", "diff", "--name-only"])
    stat_output = _run_git_command(["git", "diff", "--stat"])
    status_output = _run_git_command(["git", "status", "--short"])

    diff_files = _parse_changed_files(name_only_output)
    untracked_files = _parse_untracked_files(status_output)
    changed_files = _merge_changed_files(diff_files, untracked_files)
    total_lines = _parse_total_lines(stat_output)

    return build_diff_report(
        changed_files=changed_files,
        total_lines=total_lines,
        untracked_files=untracked_files,
    )