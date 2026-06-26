from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from guardian_platform.core.workflow.intents import ActionIntent


@dataclass
class IntentResult:
    intent: ActionIntent
    ok: bool
    simulated: bool = False
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class StageExecutionResults:
    stage_id: str
    intent_results: list[IntentResult] = field(default_factory=list)

    def first_data(self, intent_type: str) -> dict[str, Any] | None:
        for result in self.intent_results:
            if result.intent.intent_type == intent_type and result.ok:
                return result.data
        return None

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.intent_results)
