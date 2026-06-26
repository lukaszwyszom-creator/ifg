from __future__ import annotations

from dataclasses import dataclass

from ifg_guardian.config import ROOT
from ifg_guardian.core.plugins.context import GuardianConfig
from ifg_guardian.core.plugins.loader import PluginLoader
from ifg_guardian.core.plugins.registry import PluginRegistry
from ifg_guardian.core.workflow.definition import WorkflowDefinition


@dataclass
class GuardianRuntime:
    """Bootstrapped Guardian instance — created per CLI invocation or test."""

    plugin_registry: PluginRegistry
    config: GuardianConfig

    def resolve_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self.plugin_registry.resolve_workflow(workflow_id)

    def shutdown(self) -> None:
        for name in [plugin.name for plugin in self.plugin_registry.list()]:
            self.plugin_registry.unregister(name)


def create_runtime(*, root=None) -> GuardianRuntime:
    from pathlib import Path

    project_root = Path(root) if root is not None else ROOT
    config = GuardianConfig(root=project_root)
    registry = PluginRegistry()
    loader = PluginLoader(registry, config)
    loader.load_static_plugins()
    return GuardianRuntime(plugin_registry=registry, config=config)
