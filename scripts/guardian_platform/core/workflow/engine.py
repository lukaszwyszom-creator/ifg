from __future__ import annotations

import socket
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from guardian_platform.core.registry.workflows import WorkflowDefinition
from guardian_platform.core.runtime.mode import ExecutionMode
from guardian_platform.core.workflow.context import StageRecord, WorkflowContext, WorkflowTransaction
from guardian_platform.core.workflow.executors import IntentExecutor
from guardian_platform.core.workflow.results import StageExecutionResults
from guardian_platform.core.workflow.stage import StageResult, StageStatus
from guardian_platform.core.workflow.state import WorkflowState, WorkflowStateMachine


class ExecutionEngine:
    def __init__(self, *, root: Path) -> None:
        self.root = root

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        mode: ExecutionMode = ExecutionMode.LIVE,
        initial_data: dict | None = None,
    ) -> WorkflowContext:
        workflow_id = _make_workflow_id(workflow.id)
        transaction = WorkflowTransaction(
            workflow_id=workflow_id,
            workflow_type=workflow.id,
            profile=workflow.profile,
            execution_mode=mode,
            host_local=socket.gethostname(),
        )
        state_machine = WorkflowStateMachine(initial=WorkflowState.UNKNOWN)
        ctx = WorkflowContext(
            root=self.root,
            workflow_id=workflow_id,
            workflow_type=workflow.id,
            transaction=transaction,
            mode=mode,
            state_machine=state_machine,
        )
        if initial_data:
            ctx.data.update(initial_data)

        state_machine.transition(WorkflowState.READY)
        transaction.mark_started()
        state_machine.transition(WorkflowState.RUNNING)

        failed = self._run_stages(ctx, workflow, mode=mode)

        state_machine.transition(WorkflowState.VERIFYING)
        final_state = WorkflowState.FAILED if failed else WorkflowState.SUCCESS
        state_machine.transition(final_state)
        transaction.mark_ended(state=final_state)
        return ctx

    def _run_stages(self, ctx: WorkflowContext, workflow: WorkflowDefinition, *, mode: ExecutionMode) -> bool:
        executor = IntentExecutor(root=self.root)
        failed = False

        for stage in workflow.stages:
            started = perf_counter()
            skip = stage.should_skip(ctx)
            if skip is not None:
                result = StageResult(status=StageStatus.SKIP, message=skip.message)
                _record_stage(ctx, stage.id, result, duration_ms=0)
                ctx.stage_results.append(result)
                continue

            plan = stage.build_plan(ctx)
            intent_results = [executor.execute(intent, mode) for intent in plan.intents]
            stage_exec = StageExecutionResults(stage_id=stage.id, intent_results=intent_results)
            result = stage.interpret(ctx, stage_exec)
            duration_ms = int((perf_counter() - started) * 1000)
            _record_stage(ctx, stage.id, result, duration_ms=duration_ms)
            ctx.stage_results.append(result)

            if not result.passed and plan.on_fail == "halt":
                failed = True
                break

        return failed


def _make_workflow_id(workflow_type: str) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    safe_type = workflow_type.replace(".", "_")
    return f"{ts}_{safe_type}"


def _record_stage(ctx: WorkflowContext, stage_id: str, result: StageResult, *, duration_ms: int) -> None:
    ctx.transaction.stages.append(
        StageRecord(
            id=stage_id,
            status=result.status.value,
            duration_ms=duration_ms,
            message=result.message,
        )
    )
