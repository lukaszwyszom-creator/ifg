from __future__ import annotations

from guardian_platform.core.profiles.base import GuardianProfile
from guardian_platform.core.registry.commands import CommandSpec
from guardian_platform.core.registry.profiles import ProfileRegistrationContext
from guardian_platform.core.runtime.context import CommandContext


def _cmd_psag_ping(ctx: CommandContext) -> int:
    print("psag scaffold active")
    return 0


class PSAGScaffoldProfile(GuardianProfile):
    @property
    def id(self) -> str:
        return "psag"

    @property
    def description(self) -> str:
        return "PSAG scaffold — architecture test profile"

    def register(self, ctx: ProfileRegistrationContext) -> None:
        ctx.commands.register(
            CommandSpec(
                profile="psag",
                path=("ping",),
                handler=_cmd_psag_ping,
                help="PSAG scaffold heartbeat",
            )
        )
