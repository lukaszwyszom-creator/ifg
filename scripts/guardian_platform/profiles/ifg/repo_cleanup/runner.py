from __future__ import annotations

from pathlib import Path

from guardian_platform.profiles.ifg.config.defaults import REPO_ROOT
from guardian_platform.profiles.ifg.repo_cleanup.executor import execute_plan
from guardian_platform.profiles.ifg.repo_cleanup.git_guard import (
    UNCOMMITTED_CHANGES_MESSAGE,
    has_uncommitted_changes,
    phase_requires_clean_worktree,
)
from guardian_platform.profiles.ifg.repo_cleanup.planner import build_cleanup_plan
from guardian_platform.profiles.ifg.repo_cleanup.report import (
    render_terminal_summary,
    write_execution_report,
    write_plan_report,
)

LIVE_REQUIRES_YES = "LIVE cleanup requires --yes (or use --dry-run)."
PHASES_SKIPPED_DIRTY = (
    "Phases 1-3 skipped: repository contains uncommitted changes.",
    "Commit or stash changes before running archive or review phases.",
)


def run_repo_cleanup(
    *,
    root: Path | None = None,
    dry_run: bool = True,
    assume_yes: bool = False,
    phase: int | None = None,
    write_report: bool = True,
    output_format: str = "terminal",
) -> int:
    repo = (root or REPO_ROOT).resolve()

    if not dry_run and not assume_yes:
        print(LIVE_REQUIRES_YES)
        return 2

    dirty = has_uncommitted_changes(repo)
    effective_phase = phase

    if dirty and phase_requires_clean_worktree(phase):
        for line in UNCOMMITTED_CHANGES_MESSAGE:
            print(line)
        return 1

    if dirty and phase is None:
        effective_phase = 0
        for line in PHASES_SKIPPED_DIRTY:
            print(line)

    plan = build_cleanup_plan(repo, phase=effective_phase, dry_run=dry_run)
    plan_path = write_plan_report(repo, plan) if write_report else None

    if output_format == "terminal":
        print(render_terminal_summary(plan))
        if plan_path:
            print(f"Plan report: {plan_path.relative_to(repo)}")
    elif output_format == "markdown":
        from guardian_platform.profiles.ifg.repo_cleanup.report import render_plan_markdown

        print(render_plan_markdown(plan, root=repo))

    if dry_run:
        return 0

    executed = execute_plan(repo, plan)
    if write_report:
        exec_path = write_execution_report(repo, plan, executed)
        print(f"Execution report: {exec_path.relative_to(repo)}")
    return 0
