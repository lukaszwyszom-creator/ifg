from __future__ import annotations

from enum import Enum


class WorkflowState(str, Enum):
    UNKNOWN = "UNKNOWN"
    READY = "READY"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    ROLLED_BACK = "ROLLED_BACK"

    @property
    def is_terminal(self) -> bool:
        return self in (
            WorkflowState.SUCCESS,
            WorkflowState.FAILED,
            WorkflowState.ABORTED,
            WorkflowState.ROLLED_BACK,
        )


class InvalidStateTransition(Exception):
    pass


class WorkflowStateMachine:
    """Minimal lifecycle state machine for workflow runs."""

    _TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
        WorkflowState.UNKNOWN: frozenset({WorkflowState.READY, WorkflowState.ABORTED}),
        WorkflowState.READY: frozenset({WorkflowState.RUNNING, WorkflowState.ABORTED}),
        WorkflowState.RUNNING: frozenset(
            {WorkflowState.VERIFYING, WorkflowState.FAILED, WorkflowState.ABORTED}
        ),
        WorkflowState.VERIFYING: frozenset(
            {WorkflowState.SUCCESS, WorkflowState.FAILED, WorkflowState.ROLLED_BACK}
        ),
        WorkflowState.SUCCESS: frozenset(),
        WorkflowState.FAILED: frozenset(),
        WorkflowState.ABORTED: frozenset(),
        WorkflowState.ROLLED_BACK: frozenset(),
    }

    def __init__(self, *, initial: WorkflowState = WorkflowState.UNKNOWN) -> None:
        self.state = initial

    def transition(self, target: WorkflowState) -> WorkflowState:
        allowed = self._TRANSITIONS.get(self.state, frozenset())
        if target not in allowed:
            raise InvalidStateTransition(f"{self.state.value} -> {target.value}")
        self.state = target
        return self.state

    def can_transition(self, target: WorkflowState) -> bool:
        return target in self._TRANSITIONS.get(self.state, frozenset())
