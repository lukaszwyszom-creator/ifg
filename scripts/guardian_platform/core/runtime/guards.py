from __future__ import annotations

from guardian_platform.core.registry.commands import CommandSpec


class MutatingCommandBlocked(Exception):
    def __init__(self, spec: CommandSpec) -> None:
        path = " ".join(spec.path)
        super().__init__(
            f"Mutating command requires --yes (blocked: {spec.profile} {path})"
        )
        self.spec = spec


def ensure_mutating_allowed(*, spec: CommandSpec, assume_yes: bool, dry_run: bool) -> None:
    if not spec.mutating:
        return
    if dry_run:
        return
    if not assume_yes:
        raise MutatingCommandBlocked(spec)
