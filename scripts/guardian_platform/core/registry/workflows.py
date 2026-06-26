from __future__ import annotations

from dataclasses import dataclass, field

from guardian_platform.core.workflow.stage import Stage


@dataclass
class WorkflowDefinition:
    id: str
    label: str
    stages: list[Stage] = field(default_factory=list)
    profile: str = "core"
    mutating: bool = False
    requires_yes: bool = False
    depends_on: list[str] = field(default_factory=list)


@dataclass
class WorkflowRegistry:
    _workflows: dict[str, WorkflowDefinition] = field(default_factory=dict)

    def register(self, workflow: WorkflowDefinition) -> None:
        self._workflows[workflow.id] = workflow

    def get(self, workflow_id: str) -> WorkflowDefinition | None:
        return self._workflows.get(workflow_id)

    def list_ids(self) -> list[str]:
        return sorted(self._workflows.keys())
