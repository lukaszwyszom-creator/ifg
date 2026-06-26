from __future__ import annotations

from pathlib import Path

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.repo_audit.runner import run_repo_audit


def run_repo_audit_cmd(ctx: CommandContext) -> int:
    report_path = Path(ctx.extra["report_path"]) if ctx.extra.get("report_path") else None
    return run_repo_audit(
        do_fetch=bool(ctx.extra.get("do_fetch")),
        dry_run=ctx.dry_run,
        output_format=ctx.output_format,
        report_path=report_path,
    )
