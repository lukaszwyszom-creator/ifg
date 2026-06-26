from __future__ import annotations

from enum import Enum


class WorkflowState(str, Enum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class InvalidStateTransition(Exception):
    pass


class WorkflowStateMachine:
    _ALLOWED = {
        WorkflowState.UNKNOWN: {WorkflowState.READY},
        WorkflowState.READY: {WorkflowState.RUNNING},
        WorkflowState.RUNNING: {WorkflowState.VERIFYING},
        WorkflowState.VERIFYING: {WorkflowState.SUCCESS, WorkflowState.FAILED},
    }

    def __init__(self, initial: WorkflowState = WorkflowState.UNKNOWN) -> None:
        self.state = initial

    def transition(self, target: WorkflowState) -> None:
        allowed = self._ALLOWED.get(self.state, set())
        if target not in allowed:
            raise InvalidStateTransition(f"{self.state.value} -> {target.value}")
        self.state = target
