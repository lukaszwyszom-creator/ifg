from __future__ import annotations

from guardian_platform.core.registry.workflows import WorkflowDefinition
from guardian_platform.profiles.ifg.deploy.stages import (
    DeployReportStage,
    ExecutionStage,
    GitValidationStage,
    InitStage,
    RepositoryStage,
)

IFG_DEPLOY_RUN_WORKFLOW = WorkflowDefinition(
    id="ifg.deploy.run",
    label="IFG deploy run",
    profile="ifg",
    mutating=True,
    requires_yes=True,
    stages=[
        InitStage(),
        RepositoryStage(),
        GitValidationStage(),
        ExecutionStage(),
        DeployReportStage(),
    ],
)
