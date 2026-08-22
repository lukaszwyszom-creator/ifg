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
    ReportExistsError,
    render_plan_markdown,
    render_terminal_summary,
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
    output_path: Path | None = None,
    force: bool = False,
    write_report: bool = False,
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

    plan_path: Path | None = None
    if output_path is not None:
        try:
            plan_path = write_plan_report(
                repo,
                plan,
                output_path=output_path,
                force=force,
            )
        except ReportExistsError as exc:
            print(str(exc))
            return 2
    elif write_report:
        # Legacy internal callers must pass an explicit output_path.
        pass

    display_format = output_format
    if output_path is None and display_format == "terminal":
        display_format = "markdown"

    if display_format == "terminal":
        print(render_terminal_summary(plan))
    elif display_format == "markdown":
        print(render_plan_markdown(plan, root=repo))

    if plan_path is not None:
        try:
            rel = plan_path.relative_to(repo)
        except ValueError:
            rel = plan_path
        print(f"Plan report: {rel}")

    if dry_run:
        return 0

    execute_plan(repo, plan)
    return 0
