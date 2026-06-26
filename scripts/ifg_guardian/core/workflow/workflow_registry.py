from __future__ import annotations

from ifg_guardian.core.plugins.base import GuardianPlugin
from ifg_guardian.core.workflow.definition import WorkflowDefinition


class WorkflowRegistry:
    """Indexes workflows contributed by registered plugins."""

    def __init__(self) -> None:
        self._by_id: dict[str, WorkflowDefinition] = {}
        self._by_plugin: dict[str, list[str]] = {}

    def index_plugin(self, plugin: GuardianPlugin) -> None:
        workflow_ids: list[str] = []
        for workflow in plugin.workflows():
            if workflow.id in self._by_id:
                raise ValueError(f"duplicate workflow id: {workflow.id}")
            if workflow.plugin is None:
                workflow.plugin = plugin.name
            self._by_id[workflow.id] = workflow
            workflow_ids.append(workflow.id)
        self._by_plugin[plugin.name] = workflow_ids

    def unindex_plugin(self, plugin_name: str) -> None:
        for workflow_id in self._by_plugin.pop(plugin_name, []):
            self._by_id.pop(workflow_id, None)

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._by_id.get(workflow_id)

    def list_ids(self) -> list[str]:
        return list(self._by_id.keys())

    def count_for_plugin(self, plugin_name: str) -> int:
        return len(self._by_plugin.get(plugin_name, []))
