from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.core.workflows.repo_audit.stages import (
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

CORE_REPO_AUDIT_WORKFLOW = WorkflowDefinition(
    id="core.repo.audit",
    label="Repository audit",
    plugin="core",
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
