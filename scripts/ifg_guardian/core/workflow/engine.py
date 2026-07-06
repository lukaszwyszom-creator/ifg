from __future__ import annotations

import json
import socket
from datetime import datetime

from ifg_guardian.core.time_compat import UTC
from pathlib import Path
from time import perf_counter

from ifg_guardian.config import ROOT
from ifg_guardian.core.execution_guard import enforce_execution_guard
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.core.workflow.executors import DeployExecutorContext, IntentExecutor
from ifg_guardian.core.workflow.mode import ExecutionMode
from ifg_guardian.core.workflow.results import StageExecutionResults
from ifg_guardian.core.workflow.stage import StageResult, StageStatus
from ifg_guardian.core.workflow.state import WorkflowState, WorkflowStateMachine
from ifg_guardian.core.workflow.transaction import ArtifactRecord, StageRecord, WorkflowTransaction

GUARDIAN_DIR = ROOT / ".guardian"
WORKFLOWS_DIR = GUARDIAN_DIR / "workflows"


class ExecutionEngine:
    """Minimal workflow runner: stage loop with build_plan → execute → interpret."""

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or ROOT

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        mode: ExecutionMode = ExecutionMode.LIVE,
        initial_data: dict | None = None,
        plugin_registry=None,
    ) -> WorkflowContext:
        workflow_id = _make_workflow_id(workflow.id)
        transaction = WorkflowTransaction(
            workflow_id=workflow_id,
            workflow_type=workflow.id,
            plugin=workflow.plugin,
            execution_mode=mode,
            host_local=socket.gethostname(),
        )
        state_machine = WorkflowStateMachine(initial=WorkflowState.UNKNOWN)
        ctx = WorkflowContext(
            root=self.root,
            workflow=workflow,
            transaction=transaction,
            mode=mode,
            state_machine=state_machine,
            plugin_registry=plugin_registry,
        )
        if initial_data:
            ctx.data.update(initial_data)

        enforce_execution_guard(
            workflow=workflow,
            mode=mode,
            root=self.root,
            remote_path=ctx.data.get("remote_path"),
        )

        state_machine.transition(WorkflowState.READY)
        transaction.mark_started()
        state_machine.transition(WorkflowState.RUNNING)

        if workflow.depends_on:
            self._run_dependencies(ctx, workflow, mode=mode, initial_data=initial_data or {})

        failed = self._run_stages(ctx, workflow, mode=mode)

        state_machine.transition(WorkflowState.VERIFYING)
        final_state = WorkflowState.FAILED if failed else WorkflowState.SUCCESS
        state_machine.transition(final_state)
        transaction.mark_ended(state=final_state)
        _persist_transaction(ctx)
        return ctx

    def _run_dependencies(
        self,
        ctx: WorkflowContext,
        workflow: WorkflowDefinition,
        *,
        mode: ExecutionMode,
        initial_data: dict,
        _stack: frozenset[str] | None = None,
    ) -> None:
        if ctx.plugin_registry is None:
            raise RuntimeError(f"plugin_registry required for dependencies of {workflow.id}")

        stack = _stack or frozenset()
        if workflow.id in stack:
            raise RuntimeError(f"circular workflow dependency: {workflow.id}")

        dependency_contexts: dict[str, WorkflowContext] = dict(ctx.data.get("dependency_contexts", {}))
        next_stack = stack | {workflow.id}

        for dep_id in workflow.depends_on:
            if dep_id in dependency_contexts:
                continue
            dep_workflow = ctx.plugin_registry.resolve_workflow(dep_id)
            if dep_workflow is None:
                raise RuntimeError(f"unknown workflow dependency: {dep_id}")

            dep_initial = dict(initial_data)
            dep_initial.setdefault("output_format", "none")
            dep_initial["_dependency_for"] = workflow.id

            dep_engine = ExecutionEngine(root=self.root)
            if dep_workflow.depends_on:
                dep_ctx = dep_engine.run(
                    dep_workflow,
                    mode=mode,
                    initial_data=dep_initial,
                    plugin_registry=ctx.plugin_registry,
                )
            else:
                dep_ctx = dep_engine._run_single(
                    dep_workflow,
                    mode=mode,
                    initial_data=dep_initial,
                    plugin_registry=ctx.plugin_registry,
                )

            dependency_contexts[dep_id] = dep_ctx
            ctx.transaction.dependencies[dep_id] = {
                "workflow_id": dep_ctx.transaction.workflow_id,
                "workflow_type": dep_id,
                "outcome": dep_ctx.transaction.outcome,
                "state": dep_ctx.state_machine.state.value,
            }

        ctx.data["dependency_contexts"] = dependency_contexts

    def _run_single(
        self,
        workflow: WorkflowDefinition,
        *,
        mode: ExecutionMode,
        initial_data: dict,
        plugin_registry,
    ) -> WorkflowContext:
        """Run a workflow without resolving its depends_on (used for leaf dependencies)."""
        workflow_id = _make_workflow_id(workflow.id)
        transaction = WorkflowTransaction(
            workflow_id=workflow_id,
            workflow_type=workflow.id,
            plugin=workflow.plugin,
            execution_mode=mode,
            host_local=socket.gethostname(),
        )
        state_machine = WorkflowStateMachine(initial=WorkflowState.UNKNOWN)
        ctx = WorkflowContext(
            root=self.root,
            workflow=workflow,
            transaction=transaction,
            mode=mode,
            state_machine=state_machine,
            plugin_registry=plugin_registry,
        )
        ctx.data.update(initial_data)

        enforce_execution_guard(
            workflow=workflow,
            mode=mode,
            root=self.root,
            remote_path=ctx.data.get("remote_path"),
        )

        state_machine.transition(WorkflowState.READY)
        transaction.mark_started()
        state_machine.transition(WorkflowState.RUNNING)
        failed = self._run_stages(ctx, workflow, mode=mode)
        state_machine.transition(WorkflowState.VERIFYING)
        final_state = WorkflowState.FAILED if failed else WorkflowState.SUCCESS
        state_machine.transition(final_state)
        transaction.mark_ended(state=final_state)
        _persist_transaction(ctx)
        return ctx

    def _run_stages(self, ctx: WorkflowContext, workflow: WorkflowDefinition, *, mode: ExecutionMode) -> bool:
        deploy_context = DeployExecutorContext(
            remote_host=ctx.data.get("remote_host"),
            remote_path=ctx.data.get("remote_path"),
        )
        executor = IntentExecutor(root=self.root, deploy_context=deploy_context)
        ctx.data["deploy_executor_context"] = deploy_context
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
            intent_results = [
                executor.execute(intent, mode) for intent in plan.intents
            ]
            stage_exec = StageExecutionResults(stage_id=stage.id, intent_results=intent_results)
            result = stage.interpret(ctx, stage_exec)
            duration_ms = int((perf_counter() - started) * 1000)
            _record_stage(ctx, stage.id, result, duration_ms=duration_ms, plan_reasons=plan.reasons)
            ctx.stage_results.append(result)

            if not result.passed and plan.on_fail == "halt":
                failed = True
                break

        return failed


def _make_workflow_id(workflow_type: str) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    safe_type = workflow_type.replace(".", "_")
    return f"{ts}_{safe_type}"


def _record_stage(
    ctx: WorkflowContext,
    stage_id: str,
    result: StageResult,
    *,
    duration_ms: int,
    plan_reasons: list | None = None,
) -> None:
    reasons = list(result.reasons)
    if plan_reasons:
        reasons = list(plan_reasons) + reasons
    ctx.transaction.stages.append(
        StageRecord(
            id=stage_id,
            status=result.status.value,
            duration_ms=duration_ms,
            reasons=reasons,
            message=result.message,
        )
    )


def _persist_transaction(ctx: WorkflowContext) -> None:
    run_dir = WORKFLOWS_DIR / ctx.transaction.workflow_id
    run_dir.mkdir(parents=True, exist_ok=True)
    tx_path = run_dir / "transaction.json"
    ctx.transaction.artifacts.append(
        ArtifactRecord(type="workflow_report", path=str(tx_path.relative_to(ROOT)))
    )
    payload = ctx.transaction.to_dict()
    tx_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    latest_dir = GUARDIAN_DIR / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    latest_name = ctx.workflow.id.replace(".", "_") + ".json"
    latest_path = latest_dir / latest_name
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
