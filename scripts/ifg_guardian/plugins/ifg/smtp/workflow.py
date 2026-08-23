from __future__ import annotations

from ifg_guardian.core.workflow.definition import WorkflowDefinition
from ifg_guardian.plugins.ifg.smtp.stages import (
    ConfigStage,
    ConnectivityStage,
    InitStage,
    PreflightStage,
    SummaryStage,
    TestSendStage,
)

_COMMON_STAGES = [
    InitStage(),
    PreflightStage(),
    ConfigStage(),
    ConnectivityStage(),
]

IFG_SMTP_CHECK_WORKFLOW = WorkflowDefinition(
    id="ifg.smtp.check",
    label="IFG SMTP configuration check",
    plugin="ifg",
    mutating=False,
    stages=[*_COMMON_STAGES, SummaryStage()],
)

IFG_SMTP_TEST_WORKFLOW = WorkflowDefinition(
    id="ifg.smtp.test",
    label="IFG SMTP diagnostic test mail",
    plugin="ifg",
    mutating=True,
    requires_yes=True,
    stages=[*_COMMON_STAGES, TestSendStage(), SummaryStage()],
)
