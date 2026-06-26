from __future__ import annotations

import argparse

from guardian_platform.core.registry.commands import CommandRegistry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardian_platform", add_help=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--format", choices=["terminal", "json", "markdown"], default="terminal")
    parser.add_argument("command", nargs="*", help="Command path")
    return parser


def _split_command_and_flags(tokens: list[str]) -> tuple[list[str], list[str]]:
    command_tokens: list[str] = []
    flag_tokens: list[str] = []
    for token in tokens:
        if token.startswith("-") and command_tokens:
            flag_tokens.append(token)
        elif flag_tokens:
            flag_tokens.append(token)
        else:
            command_tokens.append(token)
    return command_tokens, flag_tokens


def resolve_command(registry: CommandRegistry, tokens: list[str]):
    from guardian_platform.core.registry.commands import CommandSpec

    if not tokens:
        return None, []

    command_tokens, flag_tokens = _split_command_and_flags(tokens)

    if len(command_tokens) >= 2:
        spec = registry.resolve_namespaced(command_tokens[0], command_tokens[1:])
        if spec is not None:
            consumed = 1 + len(spec.path)
            remainder = command_tokens[consumed:] + flag_tokens
            return spec, remainder

    for length in range(len(command_tokens), 0, -1):
        prefix = tuple(command_tokens[:length])
        for spec in registry.list_commands():
            if spec.profile != "core":
                continue
            if prefix == spec.path:
                remainder = command_tokens[length:] + flag_tokens
                return spec, remainder

    return None, tokens
