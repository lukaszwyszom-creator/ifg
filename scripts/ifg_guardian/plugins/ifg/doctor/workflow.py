from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.doctor.stages import (
    AlembicStage,
    BackendStage,
    ConfigurationStage,
    DatabaseStage,
    DockerStage,
    EnvironmentStage,
    FrontendStage,
    HealthStage,
    InitStage,
    RepositoryStage,
    RiskAggregationStage,
    SummaryStage,
)

IFG_DOCTOR_WORKFLOW = WorkflowDefinition(
    id="ifg.doctor",
    label="IFG environment doctor",
    plugin="ifg",
    mutating=False,
    stages=[
        InitStage(),
        EnvironmentStage(),
        RepositoryStage(),
        FrontendStage(),
        BackendStage(),
        DockerStage(),
        DatabaseStage(),
        AlembicStage(),
        ConfigurationStage(),
        HealthStage(),
        RiskAggregationStage(),
        SummaryStage(),
    ],
)
