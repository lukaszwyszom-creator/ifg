from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ifg_guardian.core.plugins.registry import PluginRegistry

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.stage import StageResult
from ifg_guardian.core.workflow.state import WorkflowStateMachine
from ifg_guardian.core.workflow.transaction import WorkflowTransaction


@dataclass
class WorkflowContext:
    root: Path
    workflow: WorkflowDefinition
    transaction: WorkflowTransaction
    mode: ExecutionMode
    state_machine: WorkflowStateMachine
    plugin_registry: PluginRegistry | None = None
    stage_results: list[StageResult] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def workflow_id(self) -> str:
        return self.transaction.workflow_id

    @property
    def workflow_type(self) -> str:
        return self.workflow.id
