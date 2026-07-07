from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.release_evaluate.stages import (
    DecisionStage,
    DeployCheckStage,
    DoctorDependencyStage,
    GitChangesStage,
    InitStage,
    SummaryStage,
    TestDiscoveryStage,
)

IFG_RELEASE_EVALUATE_WORKFLOW = WorkflowDefinition(
    id="ifg.release.evaluate",
    label="IFG release evaluate",
    plugin="ifg",
    mutating=False,
    depends_on=["ifg.doctor"],
    stages=[
        InitStage(),
        DoctorDependencyStage(),
        GitChangesStage(),
        DeployCheckStage(),
        TestDiscoveryStage(),
        DecisionStage(),
        SummaryStage(),
    ],
)
