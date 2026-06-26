from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.release_plan.stages import (
    ArtifactStage,
    BuildDecisionStage,
    DependencyStage,
    DoctorStage,
    ExecutionPlanStage,
    InitStage,
    MigrationStage,
    RepositoryAnalysisStage,
    RiskStage,
    SummaryStage,
)

IFG_RELEASE_PLAN_WORKFLOW = WorkflowDefinition(
    id="ifg.release.plan",
    label="IFG release plan",
    plugin="ifg",
    mutating=False,
    depends_on=["ifg.doctor"],
    stages=[
        InitStage(),
        DependencyStage(),
        DoctorStage(),
        RepositoryAnalysisStage(),
        BuildDecisionStage(),
        MigrationStage(),
        ArtifactStage(),
        ExecutionPlanStage(),
        RiskStage(),
        SummaryStage(),
    ],
)
