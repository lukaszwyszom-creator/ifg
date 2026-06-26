from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.deploy_run.stages import (
    BlockerStage,
    BuildPipelineStage,
    DependencyStage,
    InitStage,
    ReleasePlanStage,
    SimulateExecutionStage,
    SummaryStage,
)

IFG_DEPLOY_RUN_WORKFLOW = WorkflowDefinition(
    id="ifg.deploy.run",
    label="IFG deploy run",
    plugin="ifg",
    mutating=True,
    requires_yes=True,
    depends_on=["ifg.release.plan"],
    stages=[
        InitStage(),
        DependencyStage(),
        ReleasePlanStage(),
        BlockerStage(),
        BuildPipelineStage(),
        SimulateExecutionStage(),
        SummaryStage(),
    ],
)
