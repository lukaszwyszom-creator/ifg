from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ifg_guardian.core.workflow.definition import WorkflowDefinition

if TYPE_CHECKING:
    from ifg_guardian.core.plugins.context import PluginContext


class GuardianPlugin(ABC):
    """Base contract for Guardian plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def workflows(self) -> list[WorkflowDefinition]:
        raise NotImplementedError

    def initialize(self, ctx: PluginContext) -> None:
        """Called once after registration."""

    def shutdown(self) -> None:
        """Called on unregister or runtime teardown."""

    def repo_audit_extensions(self) -> list:
        """Optional repo audit extensions — IFG plugin may override."""
        return []
