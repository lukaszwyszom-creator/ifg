from __future__ import annotations

import sys

from guardian_platform import __version__
from guardian_platform.core.cli.builder import build_parser, resolve_command
from guardian_platform.core.config.loader import load_project_config
from guardian_platform.core.profiles.loader import load_platform
from guardian_platform.core.runtime.context import CommandContext
from guardian_platform.core.runtime.guards import MutatingCommandBlocked, ensure_mutating_allowed


def _print_help(runtime) -> None:
    print(f"Guardian Platform {__version__}")
    print("=" * 40)
    print("\nCore commands:")
    for spec in runtime.commands.list_commands():
        if spec.profile == "core":
            print(f"  {' '.join(spec.path):30} {spec.help}")
    print("\nProfile commands:")
    for spec in runtime.commands.list_commands():
        if spec.profile != "core":
            print(f"  {spec.profile} {' '.join(spec.path):26} {spec.help}")
    print("\nGlobal flags: --dry-run, --yes, --format terminal|json|markdown")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        config = load_project_config()
        runtime = load_platform(config.active_profiles)
        _print_help(runtime)
        return 0

    if argv[0] == "--version":
        print(f"Guardian Platform {__version__}")
        return 0

    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)
    tokens = list(args.command) + list(unknown)

    config = load_project_config()
    runtime = load_platform(config.active_profiles)

    spec, remainder = resolve_command(runtime.commands, tokens)
    if spec is None:
        print(f"Unknown command: {' '.join(tokens)}")
        _print_help(runtime)
        return 2

    try:
        ensure_mutating_allowed(spec=spec, assume_yes=args.yes, dry_run=args.dry_run)
    except MutatingCommandBlocked as exc:
        print(str(exc))
        return 2

    ctx = CommandContext(
        root=config.root,
        config=config,
        argv=argv,
        dry_run=args.dry_run,
        assume_yes=args.yes,
        output_format=args.format,
        extra={
            "profile_list": runtime.profiles.list_profiles(),
            "workflow_ids": runtime.workflows.list_ids(),
            "workflow_registry": runtime.workflows,
        },
    )

    if spec.path == ("workflow", "run"):
        if not remainder:
            print("Usage: workflow run <workflow_id>")
            return 2
        ctx.extra["workflow_id"] = remainder[0]

    if remainder:
        ctx.extra["remainder"] = remainder

    return spec.handler(ctx)
