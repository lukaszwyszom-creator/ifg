"""Adaptery workflow IFG → wspólny model raportów Guardiana."""
from __future__ import annotations

from datetime import datetime

from ifg_guardian.core.reporting.renderer import build_standard_build_actions, build_standard_impact_rows
from ifg_guardian.core.reporting.schema import (
    BuildActionRow,
    DecisionRow,
    DetailSection,
    ExecutiveSummary,
    GuardianReport,
    ScopeCheckRow,
    TriggerFileGroup,
)
from ifg_guardian.core.reporting.status import (
    ConfidenceLevel,
    ReportLevel,
    normalize_check_status,
    normalize_confidence,
    normalize_decision_yes_no,
    normalize_overall_status,
    normalize_release_decision,
)
from ifg_guardian.core.time_compat import UTC
from ifg_guardian.core.workflow.transaction import WorkflowTransaction
from ifg_guardian.plugins.ifg.deploy_run.models import DeployRunState, DeployStepStatus
from ifg_guardian.plugins.ifg.doctor.models import CheckResult, DoctorState
from ifg_guardian.plugins.ifg.release_evaluate.models import ReleaseEvaluateState
from ifg_guardian.plugins.ifg.release_plan.models import BuildDecision, ReleasePlanState


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _artifacts_from_transaction(transaction: WorkflowTransaction | None) -> tuple[list[str], list[str]]:
    if transaction is None:
        return [], []
    reports: list[str] = []
    handoffs: list[str] = []
    for artifact in transaction.artifacts:
        path = artifact.path
        if not path:
            continue
        lowered = artifact.type.lower()
        if "handoff" in lowered:
            handoffs.append(path)
        else:
            reports.append(path)
    return reports, handoffs


def _trigger_groups_from_paths(
    *,
    backend: list[str] | None = None,
    frontend: list[str] | None = None,
    docker: list[str] | None = None,
    compose: list[str] | None = None,
) -> list[TriggerFileGroup]:
    groups: list[TriggerFileGroup] = []
    mapping = {
        "Backend": backend or [],
        "Frontend": frontend or [],
        "Docker": docker or [],
        "Compose": compose or [],
    }
    for category, files in mapping.items():
        if files:
            groups.append(TriggerFileGroup(category=category, files=list(files)))
    return groups


def _checks_by_scope(checks: list[CheckResult]) -> tuple[list[ScopeCheckRow], list[ScopeCheckRow]]:
    local: list[ScopeCheckRow] = []
    remote: list[ScopeCheckRow] = []
    for check in checks:
        row = ScopeCheckRow(
            status=normalize_check_status(check.status).value,
            check_id=check.check_id,
            name=check.name,
            message=check.message,
        )
        if check.scope == "remote":
            remote.append(row)
        else:
            local.append(row)
    return local, remote


def _impact_from_build_decisions(decisions: list[BuildDecision]) -> dict[str, tuple[str, str]]:
    by_name = {d.name: d for d in decisions}

    def _row(name: str, component: str) -> tuple[str, str]:
        decision = by_name.get(name)
        if decision is None:
            return "NO", "no change detected"
        if decision.confidence == "BLOCKED":
            return ReportLevel.BLOCKED.value, decision.reason
        required = "YES" if decision.required else "NO"
        return required, decision.reason

    backend, backend_reason = _row("Backend Build", "API Image")
    worker, worker_reason = _row("Worker Build", "Worker Image")
    frontend, frontend_reason = _row("Frontend Build", "Frontend")
    compose, compose_reason = _row("Compose Restart", "Compose")
    migration, migration_reason = _row("Migration Required", "Alembic")
    static, static_reason = _row("Static Files", "Static Assets")
    restart, restart_reason = _row("Compose Restart", "Restart Required")
    return {
        "API Image": (backend, backend_reason),
        "Worker Image": (worker, worker_reason),
        "Frontend": (frontend, frontend_reason),
        "Compose": (compose, compose_reason),
        "Alembic": (migration, migration_reason),
        "Database": (migration, migration_reason if migration == "YES" else "no schema migration"),
        "Scheduler": ("NO", "no scheduler changes detected"),
        "Static Assets": (static, static_reason),
        "Reverse Proxy": ("NO", "no reverse proxy changes detected"),
        "Restart Required": (restart, restart_reason),
    }


def _build_actions_from_execution_plan(state: ReleasePlanState) -> list[BuildActionRow]:
    by_action: dict[str, tuple[str, str, str]] = {}
    for step in state.execution_plan:
        action = step.action
        decision = "YES" if step.required else "NO"
        command = step.description
        if action == "frontend build":
            by_action["npm build"] = (decision, step.description, "cd frontend-react && npm run build")
        elif action == "docker build api":
            by_action["docker build api"] = (decision, step.description, "docker compose build api")
        elif action == "docker build worker":
            by_action["docker build worker"] = (decision, step.description, "docker compose build worker")
        elif action == "migration":
            by_action["alembic"] = (decision, step.description, "alembic upgrade head")
        elif action == "restart":
            by_action["compose up"] = (decision, step.description, "docker compose up -d")
        elif action == "health":
            by_action["health"] = (decision, step.description, "curl /health")
        elif action == "log verification":
            by_action["logs"] = (decision, step.description, "docker compose logs api worker")
    return build_standard_build_actions(by_action)


def build_doctor_report(
    state: DoctorState,
    transaction: WorkflowTransaction | None = None,
) -> GuardianReport:
    status = normalize_overall_status(state.overall_status)
    local, remote = _checks_by_scope(state.checks)
    fail_checks = [c for c in state.checks if c.status.value in ("FAIL", "CRITICAL")]
    operator_actions = [
        f"Resolve `{check.check_id}`: {check.message}"
        for check in fail_checks
    ] or ["No operator action required — environment ready."]

    reports, handoffs = _artifacts_from_transaction(transaction)
    return GuardianReport(
        title="IFG Guardian — IFG Doctor",
        generated_at=_timestamp(),
        executive_summary=ExecutiveSummary(
            status=status.value,
            decision=status.value,
            risk=ConfidenceLevel.UNKNOWN.value,
            workflow=transaction.workflow_id if transaction else "ifg.doctor",
            duration_ms=transaction.duration_ms if transaction else 0,
            extras={"Question": "Czy środowisko IFG jest gotowe do bezpiecznej pracy i deployu?"},
        ),
        decision_matrix=[
            DecisionRow(
                component="Environment readiness",
                decision=status.value,
                confidence=ConfidenceLevel.HIGH.value,
                reason=f"{len(state.checks)} checks evaluated",
                impact="Deploy gate",
            )
        ],
        local_checks=local,
        remote_checks=remote,
        operator_actions=operator_actions,
        generated_reports=reports,
        generated_handoffs=handoffs,
        detail_sections=[
            DetailSection(
                title="Checks Summary",
                lines=[f"- **{key}:** {value}" for key, value in state.summary.items()] or ["Brak."],
            )
        ],
    )


def build_release_plan_report(
    state: ReleasePlanState,
    transaction: WorkflowTransaction | None = None,
) -> GuardianReport:
    status_level = state.deployment_risk.value
    decision = "DEPLOY_PLAN_READY" if state.deployment_risk.value in ("LOW", "MEDIUM") else "REVIEW_REQUIRED"
    matrix = [
        DecisionRow(
            component=d.name,
            decision=normalize_decision_yes_no(
                required=d.required,
                blocked=d.confidence == "BLOCKED",
            ),
            confidence=normalize_confidence(d.confidence),
            reason=d.reason,
            trigger_files=list(d.trigger_files),
            impact=d.name,
        )
        for d in state.build_decisions
    ]
    docker_files = [p for p in state.repository.backend_changes if "dockerfile" in p.lower() or p == "Dockerfile"]
    reports, handoffs = _artifacts_from_transaction(transaction)
    operator_actions = [item for item in state.risk_rationale] or ["Review build decisions before deploy."]
    extras = {
        "Question": state.question,
        "Doctor status": state.doctor_overall_status or "n/a",
    }
    if transaction and transaction.dependencies:
        extras["Dependencies"] = ", ".join(transaction.dependencies.keys())

    alb = state.repository.alembic
    local_checks = [
        ScopeCheckRow("INFO", "alembic.local_head", "Local HEAD", alb.local_head or "n/a"),
        ScopeCheckRow("INFO", "alembic.local_current", "Local current", alb.local_current or "n/a"),
    ]
    remote_checks = [
        ScopeCheckRow(
            "INFO" if alb.remote_available else "WARN",
            "alembic.remote_revision",
            "Remote revision",
            alb.remote_revision or "unavailable",
        ),
    ]
    if alb.pending_revisions:
        remote_checks.append(
            ScopeCheckRow(
                "WARN",
                "alembic.pending",
                "Pending revisions",
                ", ".join(alb.pending_revisions),
            )
        )

    return GuardianReport(
        title="IFG Guardian — Release Plan",
        generated_at=_timestamp(),
        executive_summary=ExecutiveSummary(
            status=status_level,
            decision=decision,
            risk=state.deployment_risk.value,
            workflow=transaction.workflow_id if transaction else "ifg.release.plan",
            duration_ms=transaction.duration_ms if transaction else 0,
            extras=extras,
        ),
        decision_matrix=matrix,
        trigger_files=_trigger_groups_from_paths(
            backend=state.repository.backend_changes,
            frontend=state.repository.frontend_changes,
            docker=docker_files,
            compose=["docker/docker-compose.prod.yml"] if state.repository.backend_changes else [],
        ),
        local_checks=local_checks,
        remote_checks=remote_checks,
        impact=build_standard_impact_rows(_impact_from_build_decisions(state.build_decisions)),
        build_actions=_build_actions_from_execution_plan(state),
        operator_actions=operator_actions,
        generated_reports=reports,
        generated_handoffs=handoffs,
        detail_sections=[
            DetailSection(
                title="Repository",
                lines=[
                    f"- Branch: `{state.repository.branch}`",
                    f"- HEAD: `{state.repository.head_short}` (`{state.repository.head_sha}`)",
                    f"- Dirty: {state.repository.dirty}",
                    f"- Ahead/behind: {state.repository.ahead}/{state.repository.behind}",
                ],
            ),
            DetailSection(
                title="Artifacts",
                lines=[
                    f"- **{artifact.artifact_type}:** `{artifact.identifier}` — {artifact.notes}"
                    for artifact in state.artifacts
                ] or ["Brak."],
            ),
        ],
    )


def build_release_evaluate_report(
    state: ReleaseEvaluateState,
    transaction: WorkflowTransaction | None = None,
) -> GuardianReport:
    status = normalize_release_decision(state.status)
    reports, handoffs = _artifacts_from_transaction(transaction)
    matrix = [
        DecisionRow(
            component="Release decision",
            decision=status.value,
            confidence=ConfidenceLevel.HIGH.value,
            reason=state.rationale or state.deployment_recommendation,
            impact=state.deployment_recommendation,
        )
    ]
    for area, level in state.impact.items():
        matrix.append(
            DecisionRow(
                component=area,
                decision=level.value,
                confidence=ConfidenceLevel.MEDIUM.value,
                reason=f"Change impact level: {level.value}",
                impact=level.value,
            )
        )

    impact_map = {name: ("YES" if level.value == "HIGH" else "NO", f"impact={level.value}") for name, level in state.impact.items()}
    for component in ("API Image", "Worker Image", "Frontend", "Compose", "Alembic", "Database", "Scheduler", "Static Assets", "Reverse Proxy", "Restart Required"):
        impact_map.setdefault(component, ("NO", "no direct impact flagged"))

    operator_actions = list(state.required_actions)
    if state.next_step:
        operator_actions.append(state.next_step)
    if not operator_actions:
        operator_actions = ["No additional operator actions."]

    extras = {
        "Release score": f"{state.release_score}/100",
        "Deployment profile": state.deployment_profile,
        "Backup required": str(state.backup_required),
        "Staging required": str(state.staging_required),
        "Production blocked": str(state.production_blocked),
    }
    if state.summary is not None:
        extras["Project status"] = state.summary.project_status
        extras["Environment status"] = state.summary.environment_status
        extras["Policy status"] = state.summary.policy_status

    detail_lines: list[str] = []
    for title, items in (
        ("BLOCKERS", state.blockers),
        ("WARNINGS", state.warnings),
        ("LOCAL ENVIRONMENT", state.local_environment),
        ("INFORMATION", state.information),
    ):
        detail_lines.append(f"### {title}")
        detail_lines.append("")
        detail_lines.extend(f"- {item}" for item in items) if items else detail_lines.append("- None")
        detail_lines.append("")

    return GuardianReport(
        title="IFG Guardian — Release Engine Evaluation",
        generated_at=_timestamp(),
        executive_summary=ExecutiveSummary(
            status=status.value,
            decision=state.status.value,
            risk=state.deployment_recommendation or ConfidenceLevel.UNKNOWN.value,
            workflow=transaction.workflow_id if transaction else "ifg.release.evaluate",
            duration_ms=transaction.elapsed_ms() if transaction else 0,
            extras=extras,
        ),
        decision_matrix=matrix,
        trigger_files=_trigger_groups_from_paths(
            backend=[p for p in state.changed_files if p.startswith(("app/", "alembic/", "worker/"))],
            frontend=[p for p in state.changed_files if p.startswith("frontend-react/")],
        ),
        local_checks=[
            ScopeCheckRow("INFO", "local_environment", "Local environment", item)
            for item in state.local_environment[:10]
        ],
        remote_checks=[],
        impact=build_standard_impact_rows(impact_map),
        build_actions=build_standard_build_actions({}),
        operator_actions=operator_actions,
        generated_reports=reports,
        generated_handoffs=handoffs,
        detail_sections=[
            DetailSection(title="Decision Rationale", lines=[state.rationale or "No rationale provided."]),
            DetailSection(title="Findings", lines=detail_lines),
            DetailSection(
                title="Release Score Breakdown",
                lines=[
                    f"| {part.name} | {part.weight} | {part.score} | {part.rationale} |"
                    for part in state.release_score_parts
                ] or ["Brak."],
            ),
        ],
    )


def build_deploy_run_report(
    state: DeployRunState,
    transaction: WorkflowTransaction | None = None,
) -> GuardianReport:
    mode = "DRY-RUN" if state.dry_run else "LIVE"
    if state.blockers:
        status = ReportLevel.BLOCKED.value
    elif any(step.status == DeployStepStatus.FAILED for step in state.steps):
        status = ReportLevel.FAIL.value
    elif state.dry_run:
        status = ReportLevel.INFO.value
    else:
        status = ReportLevel.READY.value

    reports, handoffs = _artifacts_from_transaction(transaction)
    matrix = [
        DecisionRow(
            component=step.action,
            decision=step.status.value if not step.skipped else "SKIPPED",
            confidence=ConfidenceLevel.HIGH.value,
            reason=step.reason,
            impact="required" if step.required else "optional",
        )
        for step in state.steps
    ]

    action_map: dict[str, tuple[str, str, str]] = {}
    for step in state.steps:
        decision = "YES" if step.required and not step.skipped else "NO"
        if step.status == DeployStepStatus.FAILED:
            decision = ReportLevel.FAIL.value
        elif step.skipped:
            decision = "SKIPPED"
        entry = (decision, step.reason, step.command)
        if step.action == "frontend build":
            action_map["npm build"] = entry
        elif step.action == "docker build api":
            action_map["docker build api"] = entry
        elif step.action == "docker build worker":
            action_map["docker build worker"] = entry
        elif step.action == "migration":
            action_map["alembic"] = entry
        elif step.action == "restart":
            action_map["compose up"] = entry
        elif step.action == "health":
            action_map["health"] = entry
        elif step.action == "log verification":
            action_map["logs"] = entry

    operator_actions = list(state.blockers) + list(state.warnings)
    if state.failed_step:
        operator_actions.append(
            f"Investigate failed step `{state.failed_step.get('step', '')}`: "
            f"{state.failed_step.get('root_cause', '')}"
        )
    if not operator_actions:
        operator_actions = ["Deploy pipeline complete — verify health and logs."]

    extras = {
        "Mode": mode,
        "Doctor status": state.doctor_status,
        "Release decision": state.release_decision,
        "Release plan": state.release_plan_workflow_id,
        "Release evaluate": state.release_evaluate_workflow_id,
    }
    if state.allow_dirty_build_override:
        extras["Dirty override"] = "YES"
    if state.build_source:
        extras["Build source"] = state.build_source
    if state.build_commit:
        extras["Build commit"] = state.build_commit
    if state.build_snapshot_path:
        extras["Build snapshot"] = state.build_snapshot_path
    if state.build_manifest_sha256:
        extras["Snapshot manifest"] = state.build_manifest_sha256[:16]
    if state.source_wip_detected:
        extras["Source WIP"] = "detected (excluded from snapshot)"
    elif state.build_source:
        extras["Source WIP"] = "none"

    pipeline_lines = [
        "| # | Action | Required | Status | Duration | Exit | Reason | Command |",
        "|---|--------|----------|--------|----------|------|--------|---------|",
    ]
    for step in state.steps:
        req = "yes" if step.required else "no"
        status_value = "SKIPPED" if step.skipped else step.status.value
        exit_code = "" if step.exit_code is None else str(step.exit_code)
        pipeline_lines.append(
            f"| {step.order} | {step.action} | {req} | {status_value} | {step.duration_ms}ms | {exit_code} "
            f"| {step.reason} | `{step.command}` |"
        )

    detail_sections = [DetailSection(title="Execution Pipeline", lines=pipeline_lines)]
    if state.failed_step:
        detail_sections.append(
            DetailSection(
                title="FAILED STEP",
                lines=[
                    f"- **Step:** `{state.failed_step.get('step', '')}`",
                    f"- **Command:** `{state.failed_step.get('command', '')}`",
                    f"- **Exit code:** `{state.failed_step.get('exit_code')}`",
                    f"- **Root cause:** {state.failed_step.get('root_cause', '')}",
                ],
            )
        )

    return GuardianReport(
        title="IFG Guardian — Deploy Run",
        generated_at=_timestamp(),
        executive_summary=ExecutiveSummary(
            status=status,
            decision=state.release_decision or status,
            risk=state.deployment_risk or ConfidenceLevel.UNKNOWN.value,
            workflow=transaction.workflow_id if transaction else "ifg.deploy.run",
            duration_ms=transaction.duration_ms if transaction else 0,
            extras=extras,
        ),
        decision_matrix=matrix,
        build_actions=build_standard_build_actions(action_map),
        operator_actions=operator_actions,
        generated_reports=reports,
        generated_handoffs=handoffs,
        detail_sections=detail_sections,
    )
