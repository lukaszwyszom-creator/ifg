from __future__ import annotations

from ifg_guardian.core.plugins.base import GuardianPlugin
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.workflow_registry import WorkflowRegistry


class PluginRegistry:
    """In-memory registry of Guardian plugins — not a global singleton."""

    def __init__(self) -> None:
        self._plugins: dict[str, GuardianPlugin] = {}
        self._workflows = WorkflowRegistry()

    @property
    def workflow_registry(self) -> WorkflowRegistry:
        return self._workflows

    def register(self, plugin: GuardianPlugin) -> None:
        if plugin.name in self._plugins:
            raise ValueError(f"plugin already registered: {plugin.name}")
        self._plugins[plugin.name] = plugin
        self._workflows.index_plugin(plugin)

    def unregister(self, name: str) -> None:
        plugin = self._plugins.pop(name)
        plugin.shutdown()
        self._workflows.unindex_plugin(name)

    def get(self, name: str) -> GuardianPlugin:
        return self._plugins[name]

    def list(self) -> list[GuardianPlugin]:
        return list(self._plugins.values())

    def resolve_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._workflows.get(workflow_id)
