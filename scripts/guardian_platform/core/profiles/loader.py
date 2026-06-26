from __future__ import annotations

from guardian_platform.core.profiles.base import GuardianProfile
from guardian_platform.core.profiles.builtin import CoreProfile
from guardian_platform.core.registry.commands import CommandRegistry
from guardian_platform.core.registry.profiles import ProfileInfo, ProfileRegistry, ProfileRegistrationContext
from guardian_platform.core.registry.workflows import WorkflowRegistry
from guardian_platform.profiles.ifg.profile import IFGProfile
from guardian_platform.profiles.ifg_scaffold.profile import IFGScaffoldProfile
from guardian_platform.profiles.psag_scaffold.profile import PSAGScaffoldProfile

_BUILTIN: dict[str, type[GuardianProfile]] = {
    "core": CoreProfile,
    "ifg": IFGProfile,
    "ifg_scaffold": IFGScaffoldProfile,
    "psag_scaffold": PSAGScaffoldProfile,
}

_PROFILE_ALIASES: dict[str, str] = {
    "ifg_scaffold": "ifg",
}


class PlatformRuntime:
    def __init__(self) -> None:
        self.commands = CommandRegistry()
        self.workflows = WorkflowRegistry()
        self.profiles = ProfileRegistry()

    def load_profiles(self, active: list[str]) -> None:
        always = ["core"]
        seen_ids: set[str] = set()
        for profile_id in always + [p for p in active if p != "core"]:
            canonical = _PROFILE_ALIASES.get(profile_id, profile_id)
            cls = _BUILTIN.get(profile_id) or _BUILTIN.get(canonical)
            if cls is None:
                continue
            profile = cls()
            if profile.id in seen_ids:
                continue
            seen_ids.add(profile.id)
            ctx = ProfileRegistrationContext(
                profile_id=profile.id,
                commands=self.commands,
                workflows=self.workflows,
            )
            profile.register(ctx)
            self.profiles.register_info(profile.info(), profile)


def load_platform(active_profiles: list[str]) -> PlatformRuntime:
    runtime = PlatformRuntime()
    runtime.load_profiles(active_profiles)
    return runtime
