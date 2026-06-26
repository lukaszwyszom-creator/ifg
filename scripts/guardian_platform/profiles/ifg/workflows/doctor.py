from __future__ import annotations

from guardian_platform.core.registry.workflows import WorkflowDefinition
from guardian_platform.profiles.ifg.doctor.stages import (
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
    profile="ifg",
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
