from __future__ import annotations

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.repo_cleanup.runner import run_repo_cleanup


def _parse_cleanup_options(ctx: CommandContext) -> int | None:
    phase: int | None = None
    tokens = list(ctx.argv) + list(ctx.extra.get("remainder") or [])
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--phase" and idx + 1 < len(tokens):
            phase = int(tokens[idx + 1])
            idx += 2
            continue
        idx += 1
    return phase


def run_repo_cleanup_cmd(ctx: CommandContext) -> int:
    phase = _parse_cleanup_options(ctx)
    dry_run = ctx.dry_run or not ctx.assume_yes
    return run_repo_cleanup(
        root=ctx.root,
        dry_run=dry_run,
        assume_yes=ctx.assume_yes,
        phase=phase,
        write_report=True,
        output_format=ctx.output_format,
    )
