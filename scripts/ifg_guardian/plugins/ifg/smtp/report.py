"""Adapter raportu SMTP → standard Guardiana."""
from __future__ import annotations

from datetime import datetime

from ifg_guardian.core.reporting.debt import finish_markdown
from ifg_guardian.core.reporting.renderer import build_standard_build_actions, render_guardian_report
from ifg_guardian.core.reporting.schema import (
    DecisionRow,
    DetailSection,
    ExecutiveSummary,
    GuardianReport,
    ScopeCheckRow,
    TriggerFileGroup,
)
from ifg_guardian.core.reporting.status import ConfidenceLevel
from ifg_guardian.core.time_compat import UTC
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.smtp.models import SmtpEnvironment, SmtpStageStatus, SmtpState


def build_smtp_report(state: SmtpState, transaction: WorkflowTransaction | None = None) -> GuardianReport:
    workflow_id = transaction.workflow_id if transaction else f"ifg.smtp.{state.mode}"
    matrix = []
    if state.environment == SmtpEnvironment.REMOTE:
        matrix.append(
            DecisionRow(
                component="ssh",
                decision="PASS" if state.ssh_ok else "FAIL",
                confidence=ConfidenceLevel.HIGH.value,
                reason=state.remote_host or "DS723+",
                trigger_files=[state.env_file] if state.env_file else [],
                impact="Production env source",
            )
        )
    matrix.extend(
        DecisionRow(
            component=check.key,
            decision=check.status.value,
            confidence=ConfidenceLevel.HIGH.value,
            reason=check.message,
            trigger_files=[state.env_file] if check.key == "env_file" else [],
            impact="SMTP configuration",
        )
        for check in state.config_checks
    )
    matrix.extend(
        DecisionRow(
            component=f"connectivity:{check.stage}",
            decision=check.status.value,
            confidence=ConfidenceLevel.HIGH.value,
            reason=check.message,
            impact="SMTP connectivity",
        )
        for check in state.connectivity_checks
    )
    if state.test_result is not None:
        matrix.append(
            DecisionRow(
                component="test mail",
                decision=state.test_result.status.value,
                confidence=ConfidenceLevel.HIGH.value,
                reason=state.test_result.message,
                impact="diagnostic send",
            )
        )

    local_checks = []
    if state.environment == SmtpEnvironment.LOCAL:
        local_checks = [
            ScopeCheckRow(check.status.value, check.key, check.key, check.message)
            for check in state.config_checks
        ]
    remote_checks = []
    if state.environment == SmtpEnvironment.REMOTE:
        if not state.ssh_ok:
            ssh_msg = next(
                (c.message for c in state.config_checks if c.key == "ssh"),
                "SSH connection failed",
            )
            remote_checks.append(ScopeCheckRow("FAIL", "ssh", "ssh", ssh_msg))
        remote_checks.extend(
            ScopeCheckRow(check.status.value, check.key, check.key, check.message)
            for check in state.config_checks
            if check.key != "ssh"
        )
    remote_checks.extend(
        ScopeCheckRow(check.status.value, check.stage, check.stage, check.message)
        for check in state.connectivity_checks
    )

    masked_lines = [f"- **{key}:** `{value}`" for key, value in state.masked_config.items()]
    recipient_lines = [f"- `{addr}`" for addr in state.recipients] or ["- Brak."]

    detail_sections = [
        DetailSection(
            title="Environment Source",
            lines=[
                f"- **Environment:** {state.environment.value}",
                f"- **Env file:** `{state.env_file or 'n/a'}`",
                f"- **Remote host:** `{state.remote_host or 'n/a'}`" if state.environment == SmtpEnvironment.REMOTE else "- **Remote host:** n/a (local mode)",
            ],
        ),
        DetailSection(title="SMTP Configuration", lines=[c.message for c in state.config_checks] or ["Brak."]),
        DetailSection(
            title="SMTP Connectivity",
            lines=[f"- **{c.stage}:** {c.status.value} — {c.message}" for c in state.connectivity_checks] or ["Brak."],
        ),
        DetailSection(title="Recipients", lines=recipient_lines),
        DetailSection(title="Masked Configuration", lines=masked_lines),
    ]
    if state.test_result is not None:
        detail_sections.append(
            DetailSection(
                title="Test Mail Result",
                lines=[
                    f"- **Status:** {state.test_result.status.value}",
                    f"- **Sent:** {state.test_result.sent}",
                    f"- **Subject:** {state.test_result.subject}",
                    f"- **Message:** {state.test_result.message}",
                ],
            )
        )

    reports: list[str] = []
    if transaction is not None:
        for artifact in transaction.artifacts:
            if artifact.path:
                reports.append(artifact.path)

    return GuardianReport(
        title=f"IFG Guardian — SMTP {'Test' if state.mode == 'test' else 'Check'}",
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        executive_summary=ExecutiveSummary(
            status=state.overall_status.value,
            decision=state.mode,
            risk=ConfidenceLevel.UNKNOWN.value,
            workflow=workflow_id,
            duration_ms=transaction.duration_ms if transaction else 0,
            extras={
                "Environment": state.environment.value,
                "Env file": state.env_file or "n/a",
                "Remote host": state.remote_host or "n/a",
                "Notify enabled": str(state.notify_enabled),
                "Recipients": str(len(state.recipients)),
            },
        ),
        decision_matrix=matrix,
        trigger_files=[
            TriggerFileGroup("Environment", [state.env_file] if state.env_file else []),
            TriggerFileGroup("Recipients", list(state.recipients)) if state.recipients else TriggerFileGroup("Recipients", []),
        ],
        local_checks=local_checks,
        remote_checks=remote_checks,
        build_actions=build_standard_build_actions({}),
        operator_actions=list(state.operator_actions),
        generated_reports=reports,
        detail_sections=detail_sections,
    )


def render_smtp_markdown(state: SmtpState, *, transaction: WorkflowTransaction | None = None) -> str:
    report = build_smtp_report(state, transaction)
    lines = render_guardian_report(report)
    return finish_markdown(lines, state=state, transaction=transaction)
