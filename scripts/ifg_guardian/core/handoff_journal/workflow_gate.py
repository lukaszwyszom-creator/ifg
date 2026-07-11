from __future__ import annotations

from ifg_guardian.core.handoff_journal.service import PublishResult, PublishStep
from ifg_guardian.core.workflow.context import WorkflowContext
from ifg_guardian.core.workflow.state import WorkflowState


class HandoffArtifactGateError(RuntimeError):
    pass


REQUIRED_STEPS = (
    PublishStep.REPORT_SAVED,
    PublishStep.HANDOFF_GENERATED,
    PublishStep.HANDOFF_SAVED,
    PublishStep.LATEST_UPDATED,
    PublishStep.INDEX_UPDATED,
)


def apply_handoff_publish_result(ctx: WorkflowContext, result: PublishResult) -> None:
    """Record handoff artifact outcome; mark workflow FAILED when publish is incomplete."""
    ctx.data["handoff_publish_result"] = {
        "ok": result.ok,
        "handoff_id": result.handoff_id,
        "failed_step": result.failed_step.value if result.failed_step else None,
        "message": result.message,
        "completed_steps": [step.value for step in result.completed_steps],
    }
    if not result.ok:
        ctx.state_machine.transition(WorkflowState.FAILED)
        ctx.transaction.mark_ended(state=WorkflowState.FAILED)
        raise HandoffArtifactGateError(
            f"Handoff artifact gate failed at {result.failed_step}: {result.message}"
        )


def require_handoff_steps(result: PublishResult, *, require_clipboard: bool = True) -> bool:
    steps = set(result.completed_steps)
    needed = set(REQUIRED_STEPS)
    if require_clipboard:
        needed.add(PublishStep.CLIPBOARD_UPDATED)
    return result.ok and needed.issubset(steps)
