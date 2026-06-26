from __future__ import annotations

from dataclasses import dataclass, field

from guardian_platform.core.registry.commands import CommandRegistry
from guardian_platform.core.registry.workflows import WorkflowDefinition, WorkflowRegistry


@dataclass
class ProfileRegistrationContext:
    profile_id: str
    commands: CommandRegistry
    workflows: WorkflowRegistry


@dataclass
class ProfileInfo:
    profile_id: str
    version: str
    description: str = ""


@dataclass
class ProfileRegistry:
    _profiles: dict[str, ProfileInfo] = field(default_factory=dict)
    _instances: dict[str, object] = field(default_factory=dict)

    def register_info(self, info: ProfileInfo, instance: object) -> None:
        self._profiles[info.profile_id] = info
        self._instances[info.profile_id] = instance

    def list_profiles(self) -> list[ProfileInfo]:
        return list(self._profiles.values())

    def get(self, profile_id: str) -> object | None:
        return self._instances.get(profile_id)
