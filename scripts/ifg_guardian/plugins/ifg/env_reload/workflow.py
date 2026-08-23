from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.env_reload.stages import (
    HealthStage,
    InitStage,
    LogsStage,
    PreflightStage,
    ReloadStage,
    SummaryStage,
    VerifyStage,
)

IFG_ENV_RELOAD_WORKFLOW = WorkflowDefinition(
    id="ifg.env.reload",
    label="IFG environment reload (.env.production)",
    plugin="ifg",
    mutating=True,
    requires_yes=True,
    stages=[
        InitStage(),
        PreflightStage(),
        ReloadStage(),
        VerifyStage(),
        HealthStage(),
        LogsStage(),
        SummaryStage(),
    ],
)
