"""Adapter raportu env reload → standard Guardiana."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ifg_guardian.config import ROOT
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
from ifg_guardian.plugins.ifg.env_reload.models import EnvReloadState


def default_env_reload_report_path() -> Path:
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    return ROOT / "docs" / "reports" / f"{date}_GWO-GUARDIAN-0079_ENV_RELOAD.md"


def build_env_reload_report(
    state: EnvReloadState,
    transaction: WorkflowTransaction | None = None,
) -> GuardianReport:
    workflow_id = transaction.workflow_id if transaction else "ifg.env.reload"
    matrix = [
        DecisionRow(
            component=check.key,
            decision=check.status.value,
            confidence=ConfidenceLevel.HIGH.value,
            reason=check.message,
            trigger_files=[state.env_file] if check.key == "env_file" else [state.compose_file],
            impact="Environment reload preflight",
        )
        for check in state.preflight_checks
    ]
    if not state.dry_run:
        matrix.extend(
            [
                DecisionRow(
                    component="compose up",
                    decision="PASS" if state.compose_up_executed else "FAIL",
                    confidence=ConfidenceLevel.HIGH.value,
                    reason=state.compose_up_output[:160] or "docker compose up -d api worker",
                    impact="Container recreation",
                ),
                DecisionRow(
                    component="health.endpoint",
                    decision="PASS" if state.health_ok else "FAIL",
                    confidence=ConfidenceLevel.HIGH.value,
                    reason=state.health_detail or "n/a",
                    impact="API availability",
                ),
            ]
        )
        for svc in state.service_statuses:
            matrix.append(
                DecisionRow(
                    component=f"service:{svc.service}",
                    decision="PASS" if svc.running else "FAIL",
                    confidence=ConfidenceLevel.HIGH.value,
                    reason=svc.state_line or "unknown",
                    impact="Container runtime",
                )
            )

    remote_checks = [
        ScopeCheckRow(check.status.value, check.key, check.key, check.message)
        for check in state.preflight_checks
    ]
    if not state.dry_run:
        remote_checks.extend(
            [
                ScopeCheckRow(
                    "PASS" if state.health_ok else "FAIL",
                    "health.endpoint",
                    "/health",
                    state.health_detail or "n/a",
                )
            ]
        )
        for svc in state.service_statuses:
            remote_checks.append(
                ScopeCheckRow(
                    "PASS" if svc.running else "FAIL",
                    f"service.{svc.service}",
                    svc.service,
                    svc.state_line or "unknown",
                )
            )

    container_lines = (
        [f"- `{name}`" for name in state.containers_restarted]
        if state.containers_restarted
        else ["- Brak (dry-run lub preflight FAIL)."]
    )
    env_lines = [
        f"- **Env file:** `{state.env_file}`",
        f"- **Exists:** {state.env_file_exists}",
        f"- **Compose file:** `{state.compose_file}`",
        f"- **Compose up executed:** {state.compose_up_executed}",
    ]
    health_lines = [
        f"- **Status:** {'PASS' if state.health_ok else 'FAIL'}",
        f"- **Detail:** {state.health_detail or 'n/a'}",
    ]

    detail_sections = [
        DetailSection(title="Containers restarted", lines=container_lines),
        DetailSection(title="Environment reloaded", lines=env_lines),
        DetailSection(title="Health", lines=health_lines),
        DetailSection(title="Startup logs summary", lines=state.startup_logs_summary or ["Brak."]),
    ]

    reports: list[str] = []
    if transaction is not None:
        for artifact in transaction.artifacts:
            if artifact.path:
                reports.append(artifact.path)

    build_actions = build_standard_build_actions(
        {
            "compose up": (
                "YES" if state.compose_up_executed else ("DRY-RUN" if state.dry_run else "NO"),
                "docker compose up -d api worker — env reload only",
                "docker compose up -d api worker",
            ),
            "health": (
                "YES" if state.health_ok else ("SKIP" if state.dry_run else "FAIL"),
                state.health_detail or "health probe",
                "curl http://127.0.0.1:8000/health",
            ),
            "logs": (
                "YES" if state.startup_logs else "SKIP",
                "last 30 lines api/worker",
                "docker compose logs --tail=30 api worker",
            ),
        }
    )

    return GuardianReport(
        title="IFG Guardian — Environment Reload",
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        executive_summary=ExecutiveSummary(
            status=state.overall_status.value,
            decision="env_reload",
            risk=ConfidenceLevel.LOW.value if state.overall_status.value == "READY" else ConfidenceLevel.HIGH.value,
            workflow=workflow_id,
            duration_ms=transaction.duration_ms if transaction else 0,
            extras={
                "Remote host": state.remote_host or "n/a",
                "Remote path": state.remote_path or "n/a",
                "Dry run": str(state.dry_run),
            },
        ),
        decision_matrix=matrix,
        trigger_files=[
            TriggerFileGroup("Environment", [state.env_file] if state.env_file else []),
            TriggerFileGroup("Compose", [state.compose_file] if state.compose_file else []),
        ],
        local_checks=[],
        remote_checks=remote_checks,
        build_actions=build_actions,
        operator_actions=list(state.operator_actions),
        generated_reports=reports,
        detail_sections=detail_sections,
    )


def render_env_reload_markdown(
    state: EnvReloadState,
    *,
    transaction: WorkflowTransaction | None = None,
) -> str:
    report = build_env_reload_report(state, transaction)
    lines = render_guardian_report(report)
    return finish_markdown(lines, state=state, transaction=transaction)
