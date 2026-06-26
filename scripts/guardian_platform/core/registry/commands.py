from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from guardian_platform.core.runtime.context import CommandContext

CommandHandler = Callable[[CommandContext], int]


@dataclass(frozen=True)
class CommandSpec:
    profile: str
    path: tuple[str, ...]
    handler: CommandHandler
    help: str = ""
    mutating: bool = False
    supports_dry_run: bool = False

    @property
    def dotted(self) -> str:
        return f"{self.profile} {' '.join(self.path)}".strip()


@dataclass
class CommandRegistry:
    _commands: list[CommandSpec] = field(default_factory=list)

    def register(self, spec: CommandSpec) -> None:
        self._commands.append(spec)

    def list_commands(self) -> list[CommandSpec]:
        return list(self._commands)

    def resolve(self, tokens: list[str]) -> CommandSpec | None:
        if not tokens:
            return None
        for spec in self._commands:
            if len(tokens) == len(spec.path) and tuple(tokens) == spec.path:
                return spec
        return None

    def resolve_namespaced(self, profile: str, tokens: list[str]) -> CommandSpec | None:
        for spec in self._commands:
            if spec.profile != profile:
                continue
            if tuple(tokens) == spec.path:
                return spec
        return None

    def profiles_with_commands(self) -> dict[str, list[CommandSpec]]:
        grouped: dict[str, list[CommandSpec]] = {}
        for spec in self._commands:
            grouped.setdefault(spec.profile, []).append(spec)
        return grouped
