from __future__ import annotations

from pathlib import Path

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.config.defaults import DEFAULT_REMOTE_PATH, resolve_remote_host
from guardian_platform.profiles.ifg.deploy.runner import run_deploy_run


def run_deploy_run_cmd(ctx: CommandContext) -> int:
    report_path = Path(ctx.extra["report_path"]) if ctx.extra.get("report_path") else None
    return run_deploy_run(
        dry_run=ctx.dry_run,
        assume_yes=ctx.assume_yes,
        output_format=ctx.output_format,
        report_path=report_path,
        remote_host=resolve_remote_host(ctx.extra.get("remote_host")),
        remote_path=ctx.extra.get("remote_path") or DEFAULT_REMOTE_PATH,
    )
