from __future__ import annotations

import re
from dataclasses import dataclass

from ifg_guardian.plugins.ifg.doctor.models import CheckResult, CheckStatus, DoctorState
from ifg_guardian.plugins.ifg.release_evaluate.models import (
    ClassifiedFinding,
    FindingCategory,
    FindingScope,
    ReleaseEvaluateState,
    StatusSummary,
)

LOCAL_ENV_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"No module named ['\"]pytest", re.I),
    re.compile(r"No module named ['\"]psycopg", re.I),
    re.compile(r"No such file or directory: ['\"]alembic['\"]", re.I),
    re.compile(r"\balembic\b.*(not found|No such file)", re.I),
    re.compile(r"command not found.*\balembic\b", re.I),
    re.compile(r"\[Errno 2\].*alembic", re.I),
    re.compile(r"skipped in dry-run", re.I),
)


@dataclass
class PolicyRuleMeta:
    rule_id: str
    scope: FindingScope
    category: FindingCategory
    penalty: int = 0

    @classmethod
    def from_policy(cls, rule_id: str, meta: dict) -> PolicyRuleMeta:
        return cls(
            rule_id=rule_id,
            scope=FindingScope(meta.get("scope", FindingScope.POLICY.value)),
            category=FindingCategory(meta.get("category", FindingCategory.WARNING.value)),
            penalty=int(meta.get("penalty", 0)),
        )


def is_local_environment_error(text: str) -> bool:
    if not text:
        return False
    return any(pattern.search(text) for pattern in LOCAL_ENV_PATTERNS)


def load_policy_rules_meta(policy: dict) -> dict[str, PolicyRuleMeta]:
    raw = policy.get("policy_rules", {})
    return {
        rule_id: PolicyRuleMeta.from_policy(rule_id, meta if isinstance(meta, dict) else {})
        for rule_id, meta in raw.items()
    }


def get_score_config(policy: dict) -> dict:
    return policy.get("score_config", {})


def get_rule_penalty(policy: dict, rule_id: str) -> int:
    rules = load_policy_rules_meta(policy)
    if rule_id in rules and rules[rule_id].penalty:
        return rules[rule_id].penalty
    penalties = get_score_config(policy).get("rule_penalties", {})
    if rule_id in penalties:
        return int(penalties[rule_id])
    if rule_id == "dirty_tree_build_with_override":
        return int(policy.get("dirty_tree_policy", {}).get("score_penalty", 0))
    return 0


def _doctor_check_scope(check: CheckResult) -> FindingScope:
    if check.group in {"alembic", "database"}:
        return FindingScope.ENVIRONMENT
    if check.group in {"configuration", "docker", "health"}:
        return FindingScope.CONFIGURATION
    if check.group in {"environment", "repository", "frontend", "backend"}:
        return FindingScope.PROJECT
    return FindingScope.PROJECT


def classify_doctor_check(check: CheckResult) -> ClassifiedFinding:
    scope = _doctor_check_scope(check)
    message = f"[{check.group}] {check.name}: {check.message}"
    source = f"doctor:{check.check_id}"

    if is_local_environment_error(check.message):
        return ClassifiedFinding(
            message=message,
            category=FindingCategory.LOCAL_ENVIRONMENT,
            scope=FindingScope.ENVIRONMENT,
            source=source,
        )

    if check.status == CheckStatus.PASS:
        return ClassifiedFinding(
            message=message,
            category=FindingCategory.INFORMATION,
            scope=scope,
            source=source,
        )

    if check.status == CheckStatus.WARN:
        return ClassifiedFinding(
            message=message,
            category=FindingCategory.WARNING,
            scope=scope,
            source=source,
        )

    return ClassifiedFinding(
        message=message,
        category=FindingCategory.BLOCKER,
        scope=scope,
        source=source,
    )


def _status_from_findings(findings: list[ClassifiedFinding], *, scopes: set[FindingScope]) -> str:
    scoped = [f for f in findings if f.scope in scopes]
    if any(f.category == FindingCategory.BLOCKER for f in scoped):
        return "BLOCKED"
    if any(
        f.category in {FindingCategory.WARNING, FindingCategory.LOCAL_ENVIRONMENT}
        for f in scoped
    ):
        return "WARNING"
    return "READY"


def _policy_status(state: ReleaseEvaluateState) -> str:
    if state.production_blocked:
        return "BLOCK"
    if state.policy_rules_triggered:
        return "WARN"
    return "PASS"


def finalize_classification(
    state: ReleaseEvaluateState,
    *,
    doctor: DoctorState,
    policy: dict,
) -> None:
    """Classify all findings into exclusive report sections and compute summary."""
    rules_meta = load_policy_rules_meta(policy)
    findings: list[ClassifiedFinding] = []

    for check in doctor.checks:
        findings.append(classify_doctor_check(check))

    for rule_id in state.policy_rules_triggered:
        meta = rules_meta.get(rule_id)
        if meta is None:
            continue
        findings.append(
            ClassifiedFinding(
                message=f"Policy rule triggered: {rule_id}",
                category=meta.category,
                scope=meta.scope,
                source="policy_engine",
                rule_id=rule_id,
            )
        )

    for blocker in list(state.blockers):
        if any(f.message == blocker for f in findings):
            continue
        findings.append(
            ClassifiedFinding(
                message=blocker,
                category=FindingCategory.BLOCKER,
                scope=FindingScope.POLICY,
                source="policy_engine",
            )
        )

    if state.test_discovery_local_env:
        findings.append(
            ClassifiedFinding(
                message=state.test_discovery_error or "pytest not available in local interpreter",
                category=FindingCategory.LOCAL_ENVIRONMENT,
                scope=FindingScope.ENVIRONMENT,
                source="test_discovery",
            )
        )
    elif not state.test_discovery_ok and state.test_discovery_error:
        findings.append(
            ClassifiedFinding(
                message=f"Test discovery: {state.test_discovery_error}",
                category=FindingCategory.BLOCKER,
                scope=FindingScope.PROJECT,
                source="test_discovery",
                rule_id="tests_must_pass",
            )
        )

    if state.deploy_check_exit_code not in (None, 0):
        findings.append(
            ClassifiedFinding(
                message=f"Deploy check returned exit code {state.deploy_check_exit_code}",
                category=FindingCategory.WARNING,
                scope=FindingScope.CONFIGURATION,
                source="deploy_check",
            )
        )

    for positive in state.positives[:12]:
        findings.append(
            ClassifiedFinding(
                message=positive,
                category=FindingCategory.INFORMATION,
                scope=FindingScope.PROJECT,
                source="positive_signal",
            )
        )

    for action in state.required_actions:
        findings.append(
            ClassifiedFinding(
                message=action,
                category=FindingCategory.INFORMATION,
                scope=FindingScope.POLICY,
                source="required_action",
            )
        )

    blockers = _unique_messages(f for f in findings if f.category == FindingCategory.BLOCKER)
    warnings = _unique_messages(f for f in findings if f.category == FindingCategory.WARNING)
    local_environment = _unique_messages(
        f for f in findings if f.category == FindingCategory.LOCAL_ENVIRONMENT
    )
    information = _unique_messages(f for f in findings if f.category == FindingCategory.INFORMATION)

    state.findings = findings
    state.blockers = blockers
    state.warnings = warnings
    state.local_environment = local_environment
    state.information = information

    project_scopes = {FindingScope.PROJECT, FindingScope.CONFIGURATION}
    state.summary = StatusSummary(
        project_status=_status_from_findings(findings, scopes=project_scopes),
        environment_status=_status_from_findings(
            findings, scopes={FindingScope.ENVIRONMENT}
        ),
        policy_status=_policy_status(state),
        deployment_recommendation=state.deployment_recommendation,
    )


def _unique_messages(findings) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for finding in findings:
        if finding.message in seen:
            continue
        seen.add(finding.message)
        out.append(finding.message)
    return out
