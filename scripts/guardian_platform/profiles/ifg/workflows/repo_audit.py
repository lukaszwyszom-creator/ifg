from __future__ import annotations

from guardian_platform.core.registry.workflows import WorkflowDefinition
from guardian_platform.profiles.ifg.repo_audit.stages import (
    ClassifyFilesStage,
    CollectGitStatusStage,
    CollectRepositoryMetadataStage,
    InitStage,
    LineEndingAnalysisStage,
    RecommendedActionsStage,
    ReportStage,
    RiskAnalysisStage,
    SummaryStage,
)

IFG_REPO_AUDIT_WORKFLOW = WorkflowDefinition(
    id="ifg.repo.audit",
    label="IFG repository audit",
    profile="ifg",
    mutating=False,
    stages=[
        InitStage(),
        CollectGitStatusStage(),
        CollectRepositoryMetadataStage(),
        ClassifyFilesStage(),
        LineEndingAnalysisStage(),
        RiskAnalysisStage(),
        RecommendedActionsStage(),
        ReportStage(),
        SummaryStage(),
    ],
)
