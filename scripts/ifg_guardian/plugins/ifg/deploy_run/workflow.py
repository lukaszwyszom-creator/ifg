from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.deploy_run.preflight_stage import PreflightStage
from ifg_guardian.plugins.ifg.deploy_run.stages import (
    BlockerStage,
    BuildPipelineStage,
    DependencyStage,
    InitStage,
    ReleaseEvaluateStage,
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
    depends_on=["ifg.release.plan", "ifg.release.evaluate"],
    stages=[
        InitStage(),
        DependencyStage(),
        ReleasePlanStage(),
        ReleaseEvaluateStage(),
        BlockerStage(),
        PreflightStage(),
        BuildPipelineStage(),
        SimulateExecutionStage(),
        SummaryStage(),
    ],
)
