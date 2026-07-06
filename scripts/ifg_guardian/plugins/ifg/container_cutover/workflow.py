from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.container_cutover.stages import (
    BackupStage,
    CleanupStage,
    ComposeConfigGateStage,
    CutoverUpStage,
    FunctionalGateStage,
    GitPullStage,
    GuardianVerifyStage,
    InitStage,
    LegacyContainersStage,
    PostHealthStage,
    PreflightStage,
    SummaryStage,
)

IFG_CONTAINER_CUTOVER_WORKFLOW = WorkflowDefinition(
    id="ifg.container.cutover",
    label="IFG Container Manager cutover (project ifg)",
    plugin="ifg",
    mutating=True,
    requires_yes=True,
    stages=[
        InitStage(),
        BackupStage(),
        GitPullStage(),
        ComposeConfigGateStage(),
        PreflightStage(),
        LegacyContainersStage(),
        CutoverUpStage(),
        PostHealthStage(),
        GuardianVerifyStage(),
        FunctionalGateStage(),
        CleanupStage(),
        SummaryStage(),
    ],
)
