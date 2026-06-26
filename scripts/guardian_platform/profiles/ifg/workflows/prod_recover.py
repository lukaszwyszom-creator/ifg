from __future__ import annotations

from guardian_platform.core.registry.workflows import WorkflowDefinition
from guardian_platform.profiles.ifg.recover.stages import (
    DockerStatusStage,
    HealthStage,
    InitStage,
    KSeFVerificationStage,
    RecoveryReportStage,
    RepositoryValidationStage,
    RestartServicesStage,
    WorkerVerificationStage,
)

IFG_PROD_RECOVER_WORKFLOW = WorkflowDefinition(
    id="ifg.prod.recover",
    label="IFG prod recover",
    profile="ifg",
    mutating=True,
    requires_yes=True,
    stages=[
        InitStage(),
        RepositoryValidationStage(),
        DockerStatusStage(),
        RestartServicesStage(),
        HealthStage(),
        WorkerVerificationStage(),
        KSeFVerificationStage(),
        RecoveryReportStage(),
    ],
)
