from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from ifg_guardian.core.workflow.intents import ActionIntent
from ifg_guardian.core.workflow.results import StageExecutionResults

if TYPE_CHECKING:
    from ifg_guardian.core.workflow.context import WorkflowContext


class StageStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class BuildReason:
    decision: str
    because: list[str] = field(default_factory=list)
    confidence: str = "HIGH"
    source_stage: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "because": list(self.because),
            "confidence": self.confidence,
            "source_stage": self.source_stage,
        }


@dataclass
class StagePlan:
    intents: list[ActionIntent] = field(default_factory=list)
    reasons: list[BuildReason] = field(default_factory=list)
    on_fail: Literal["halt", "continue", "verify"] = "halt"


@dataclass
class StageResult:
    status: StageStatus
    message: str = ""
    reasons: list[BuildReason] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status in (StageStatus.PASS, StageStatus.WARN, StageStatus.SKIP)


@dataclass
class SkipReason:
    message: str


class Stage(ABC):
    id: str
    label: str
    mutating: bool = False

    def should_skip(self, ctx: WorkflowContext) -> SkipReason | None:
        return None

    @abstractmethod
    def build_plan(self, ctx: WorkflowContext) -> StagePlan:
        raise NotImplementedError

    @abstractmethod
    def interpret(self, ctx: WorkflowContext, results: StageExecutionResults) -> StageResult:
        raise NotImplementedError