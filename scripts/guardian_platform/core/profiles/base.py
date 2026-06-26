from __future__ import annotations

from abc import ABC, abstractmethod

from guardian_platform.core.registry.profiles import ProfileInfo, ProfileRegistrationContext


class GuardianProfile(ABC):
    @property
    @abstractmethod
    def id(self) -> str:
        raise NotImplementedError

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return ""

    def register(self, ctx: ProfileRegistrationContext) -> None:
        """Register commands and workflows into platform registries."""

    def info(self) -> ProfileInfo:
        return ProfileInfo(
            profile_id=self.id,
            version=self.version,
            description=self.description,
        )
