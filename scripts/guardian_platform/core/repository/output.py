from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from guardian_platform.core.reporting.writers import render_report
from guardian_platform.core.repository.report import ReportExistsError, write_markdown_report
from guardian_platform.core.runtime.context import CommandContext


@dataclass(frozen=True)
class ReportOptions:
    output_path: Path | None = None
    force: bool = False


def parse_report_options(ctx: CommandContext) -> ReportOptions:
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
    return ReportOptions(output_path=output_path, force=force)


def emit_repository_report(
    ctx: CommandContext,
    markdown: str,
    *,
    json_payload: dict,
    report_label: str = "Report",
) -> int:
    options = parse_report_options(ctx)
    written_path: Path | None = None

    if options.output_path is not None:
        try:
            written_path = write_markdown_report(
                ctx.root,
                markdown,
                options.output_path,
                force=options.force,
            )
        except ReportExistsError as exc:
            print(str(exc))
            return 2

    fmt = ctx.output_format
    if fmt == "json":
        print(render_report(json_payload, "json"))
    elif fmt == "markdown" or (written_path is None and fmt == "terminal"):
        print(markdown)
    else:
        print(render_report(json_payload, fmt))

    if written_path is not None:
        try:
            rel = written_path.relative_to(ctx.root)
        except ValueError:
            rel = written_path
        print(f"{report_label}: {rel}")

    return 0
