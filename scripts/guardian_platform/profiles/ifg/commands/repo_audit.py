from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.profiles.ifg.repo_audit.runner import run_repo_audit


@dataclass(frozen=True)
class AuditOptions:
    output_path: Path | None = None
    force: bool = False


def _parse_audit_options(ctx: CommandContext) -> AuditOptions:
    output_path: Path | None = None
    force = False
    tokens = list(ctx.argv) + list(ctx.extra.get("remainder") or [])
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "--output" and idx + 1 < len(tokens):
            output_path = Path(tokens[idx + 1])
            idx += 2
            continue
        if tok == "--force":
            force = True
            idx += 1
            continue
        idx += 1
    return AuditOptions(output_path=output_path, force=force)


def run_repo_audit_cmd(ctx: CommandContext) -> int:
    options = _parse_audit_options(ctx)
    return run_repo_audit(
        root=ctx.root,
        do_fetch=bool(ctx.extra.get("do_fetch")),
        dry_run=ctx.dry_run,
        output_format=ctx.output_format,
        output_path=options.output_path,
        force=options.force,
    )
