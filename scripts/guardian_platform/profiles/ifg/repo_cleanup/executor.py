from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from guardian_platform.profiles.ifg.repo_cleanup.git_guard import is_git_tracked_path
from guardian_platform.profiles.ifg.repo_cleanup.models import CleanupAction
from guardian_platform.profiles.ifg.repo_cleanup.policy import CleanupOperation, CleanupPlan


class CleanupExecutionError(RuntimeError):
    pass


def _local_remove(root: Path, rel: str) -> None:
    if is_git_tracked_path(root, rel):
        raise CleanupExecutionError(f"Refusing to remove git-tracked path: {rel}")
    target = root / rel
    if not target.exists():
        return
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def _git_mv(root: Path, source: str, dest: str) -> None:
    dest_path = root / dest
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "mv", source, dest], cwd=root, check=True, capture_output=True, text=True)


def execute_plan(root: Path, plan: CleanupPlan) -> list[str]:
    if plan.dry_run:
        return []

    executed: list[str] = []
    for op in plan.operations:
        if op.action == CleanupAction.LIST_REVIEW:
            continue
        if op.action == CleanupAction.LOCAL_REMOVE:
            _local_remove(root, op.source)
            executed.append(f"removed {op.source}")
        elif op.action == CleanupAction.GIT_MV:
            if not op.target:
                raise CleanupExecutionError(f"git mv missing target for {op.source}")
            _git_mv(root, op.source, op.target)
            executed.append(f"git mv {op.source} -> {op.target}")
    return executed
