from __future__ import annotations

from dataclasses import dataclass, field

from ifg_guardian.core.workflow.stage import Stage


@dataclass
class WorkflowDefinition:
    id: str
    label: str
    stages: list[Stage] = field(default_factory=list)
    plugin: str | None = None
    mutating: bool = False
    requires_yes: bool = False
    depends_on: list[str] = field(default_factory=list)
