from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.repo_cleanup.runner import run_repo_cleanup


@dataclass(frozen=True)
class CleanupOptions:
    phase: int | None = None
    output_path: Path | None = None
    force: bool = False


def _parse_cleanup_options(ctx: CommandContext) -> CleanupOptions:
    phase: int | None = None
    output_path: Path | None = None
    force = False
    tokens = list(ctx.argv) + list(ctx.extra.get("remainder") or [])
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--phase" and idx + 1 < len(tokens):
            phase = int(tokens[idx + 1])
            idx += 2
            continue
        if tok == "--output" and idx + 1 < len(tokens):
            output_path = Path(tokens[idx + 1])
            idx += 2
            continue
        if tok == "--force":
            force = True
            idx += 1
            continue
        idx += 1
    return CleanupOptions(phase=phase, output_path=output_path, force=force)


def run_repo_cleanup_cmd(ctx: CommandContext) -> int:
    options = _parse_cleanup_options(ctx)
    dry_run = ctx.dry_run or not ctx.assume_yes
    return run_repo_cleanup(
        root=ctx.root,
        dry_run=dry_run,
        assume_yes=ctx.assume_yes,
        phase=options.phase,
        output_path=options.output_path,
        force=options.force,
        output_format=ctx.output_format,
    )
