from __future__ import annotations

from ifg_guardian.plugins.ifg.doctor.models import DoctorState
from ifg_guardian.plugins.ifg.release_evaluate.classification import get_score_config
from ifg_guardian.plugins.ifg.release_evaluate.models import (
    ImpactLevel,
    ReleaseDecisionStatus,
    ReleaseEvaluateState,
    ReleaseScorePart,
)

DEFAULT_SCORE_WEIGHTS = {
    "repo": 15,
    "tests": 15,
    "build": 15,
    "migrations": 12,
    "docker": 10,
    "configuration": 10,
    "rollback_readiness": 13,
    "documentation": 10,
}

DEFAULT_STATUS_PENALTIES = {
    "WARN": 20,
    "FAIL": 45,
    "CRITICAL": 70,
}

DEFAULT_COMPONENT_SCORES = {
    "tests_failed": 35,
    "rollback_missing": 55,
    "docs_heuristic": 70,
    "empty_group": 50,
}


def get_release_evaluate_state(ctx) -> ReleaseEvaluateState:
    state = ctx.data.get("release_evaluate")
    if not isinstance(state, ReleaseEvaluateState):
        raise RuntimeError("release evaluate state not initialized")
    return state


def score_from_doctor(
    doctor: DoctorState,
    *,
    test_discovery_ok: bool,
    policy: dict | None = None,
) -> list[ReleaseScorePart]:
    cfg = get_score_config(policy or {})
    weights = {**DEFAULT_SCORE_WEIGHTS, **cfg.get("weights", {})}
    status_penalties = {**DEFAULT_STATUS_PENALTIES, **cfg.get("status_penalties", {})}
    component_scores = {**DEFAULT_COMPONENT_SCORES, **cfg.get("component_scores", {})}

    def group_score(prefix: str) -> int:
        checks = [c for c in doctor.checks if c.group == prefix]
        if not checks:
            return int(component_scores.get("empty_group", 50))
        score = 100
        for check in checks:
            penalty = status_penalties.get(check.status.value)
            if penalty is not None:
                score -= int(penalty)
        return max(0, min(100, score))

    parts = [
        ReleaseScorePart("repo", weights["repo"], group_score("repository"), "repo+audit"),
        ReleaseScorePart(
            "tests",
            weights["tests"],
            100 if test_discovery_ok else int(component_scores.get("tests_failed", 35)),
            "pytest collect",
        ),
        ReleaseScorePart("build", weights["build"], group_score("frontend"), "frontend build checks"),
        ReleaseScorePart("migrations", weights["migrations"], group_score("alembic"), "alembic checks"),
        ReleaseScorePart("docker", weights["docker"], group_score("docker"), "docker checks"),
        ReleaseScorePart(
            "configuration",
            weights["configuration"],
            group_score("configuration"),
            "env/config checks",
        ),
        ReleaseScorePart(
            "rollback_readiness",
            weights["rollback_readiness"],
            100
            if any(c.check_id == "database.backup_policy" and c.status.value == "PASS" for c in doctor.checks)
            else int(component_scores.get("rollback_missing", 55)),
            "backup policy + recovery readiness",
        ),
        ReleaseScorePart(
            "documentation",
            weights["documentation"],
            100
            if any(c.group == "configuration" and c.status.value == "PASS" for c in doctor.checks)
            else int(component_scores.get("docs_heuristic", 70)),
            "ops docs and templates",
        ),
    ]
    return parts


def aggregate_release_score(parts: list[ReleaseScorePart]) -> int:
    total = 0
    for part in parts:
        total += int((part.score * part.weight) / 100)
    return max(0, min(100, total))


def detect_impacts(changed_files: list[str]) -> dict[str, ImpactLevel]:
    impact = {
        "Backend": ImpactLevel.LOW,
        "Frontend": ImpactLevel.LOW,
        "Mobile": ImpactLevel.LOW,
        "Docker": ImpactLevel.LOW,
        "DB": ImpactLevel.LOW,
        "Alembic": ImpactLevel.LOW,
        "Worker": ImpactLevel.LOW,
        "KSeF": ImpactLevel.LOW,
        "Warehouse": ImpactLevel.LOW,
        "Payments": ImpactLevel.LOW,
    }
    for path in changed_files:
        p = path.lower()
        if p.startswith("app/"):
            impact["Backend"] = ImpactLevel.MEDIUM
        if p.startswith("frontend-react/"):
            impact["Frontend"] = ImpactLevel.MEDIUM
        if p.startswith("mobile-expo/"):
            impact["Mobile"] = ImpactLevel.MEDIUM
        if p.startswith("docker/"):
            impact["Docker"] = ImpactLevel.HIGH
        if p.startswith("alembic/"):
            impact["Alembic"] = ImpactLevel.HIGH
            impact["DB"] = ImpactLevel.HIGH
        if "worker" in p:
            impact["Worker"] = ImpactLevel.HIGH
        if "ksef" in p:
            impact["KSeF"] = ImpactLevel.HIGH
        if "warehouse" in p:
            impact["Warehouse"] = ImpactLevel.HIGH
        if "payment" in p:
            impact["Payments"] = ImpactLevel.HIGH
    return impact


def make_decision(state: ReleaseEvaluateState) -> None:
    if state.blockers:
        state.status = ReleaseDecisionStatus.PRODUCTION_BLOCKED
        state.deployment_recommendation = "Deploy zablokowany"
        state.next_step = "Usuń blockery i uruchom ponownie guardian release evaluate."
        return

    if state.release_score >= 85 and not state.warnings:
        state.status = ReleaseDecisionStatus.READY_FOR_DEPLOY
        state.deployment_recommendation = "Deploy możliwy"
        state.next_step = "Uruchom kontrolowany deploy według runbooka."
        return

    if state.release_score >= 70:
        state.status = ReleaseDecisionStatus.READY_WITH_WARNINGS
        state.deployment_recommendation = "Deploy możliwy z ostrzeżeniami"
        state.next_step = "Potwierdź ostrzeżenia i zaplanuj deploy z monitoringiem."
        return

    if state.release_score >= 55:
        state.status = ReleaseDecisionStatus.STAGING_ONLY
        state.deployment_recommendation = "Wymagany staging"
        state.next_step = "Najpierw staging + testy regresji, potem ponowna ewaluacja."
        return

    state.status = ReleaseDecisionStatus.PRODUCTION_BLOCKED
    state.deployment_recommendation = "Deploy zablokowany"
    state.next_step = "Najpierw backup i stabilizacja środowiska."
