from __future__ import annotations

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.checks.frontend import (
    check_frontend_dist_freshness,
    check_frontend_worktree_requires_build,
    check_ksef_connect_button_fix,
)


def run_frontend_check(ctx: CommandContext) -> int:
    print("IFG Guardian — frontend check")
    print("=" * 40)
    has_error = False
    notes: list[str] = []

    dist_ok, dist_note = check_frontend_dist_freshness()
    if not dist_ok:
        has_error = True
    notes.append(dist_note)

    worktree_ok, worktree_note = check_frontend_worktree_requires_build()
    if not worktree_ok:
        has_error = True
    notes.append(worktree_note)

    connect_ok, connect_notes = check_ksef_connect_button_fix()
    if not connect_ok:
        has_error = True
    notes.extend(connect_notes)

    for note in notes:
        print(note)

    print("\n" + "=" * 40)
    if has_error:
        print("Status: ERROR")
        return 1
    print("Status: OK")
    return 0
