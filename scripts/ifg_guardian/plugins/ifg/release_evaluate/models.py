from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReleaseDecisionStatus(str, Enum):
    READY_FOR_DEPLOY = "READY_FOR_DEPLOY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    READY_WITH_OVERRIDE = "READY_WITH_OVERRIDE"
    STAGING_ONLY = "STAGING_ONLY"
    PRODUCTION_BLOCKED = "PRODUCTION_BLOCKED"


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class FindingCategory(str, Enum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    LOCAL_ENVIRONMENT = "LOCAL_ENVIRONMENT"
    INFORMATION = "INFORMATION"


class FindingScope(str, Enum):
    PROJECT = "PROJECT"
    ENVIRONMENT = "ENVIRONMENT"
    CONFIGURATION = "CONFIGURATION"
    POLICY = "POLICY"


@dataclass
class ClassifiedFinding:
    message: str
    category: FindingCategory
    scope: FindingScope
    source: str = ""
    rule_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "message": self.message,
            "category": self.category.value,
            "scope": self.scope.value,
            "source": self.source,
            "rule_id": self.rule_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ClassifiedFinding:
        return cls(
            message=data.get("message", ""),
            category=FindingCategory(data.get("category", FindingCategory.INFORMATION.value)),
            scope=FindingScope(data.get("scope", FindingScope.PROJECT.value)),
            source=data.get("source", ""),
            rule_id=data.get("rule_id", ""),
        )


@dataclass
class StatusSummary:
    project_status: str = "READY"
    environment_status: str = "READY"
    policy_status: str = "PASS"
    deployment_recommendation: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "project_status": self.project_status,
            "environment_status": self.environment_status,
            "policy_status": self.policy_status,
            "deployment_recommendation": self.deployment_recommendation,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StatusSummary:
        return cls(
            project_status=data.get("project_status", "READY"),
            environment_status=data.get("environment_status", "READY"),
            policy_status=data.get("policy_status", "PASS"),
            deployment_recommendation=data.get("deployment_recommendation", ""),
        )


@dataclass
class ReleaseScorePart:
    name: str
    weight: int
    score: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleaseScorePart:
        return cls(
            name=data.get("name", ""),
            weight=int(data.get("weight", 0)),
            score=int(data.get("score", 0)),
            rationale=data.get("rationale", ""),
        )


@dataclass
class ReleaseEvaluateState:
    status: ReleaseDecisionStatus = ReleaseDecisionStatus.PRODUCTION_BLOCKED
    rationale: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    positives: list[str] = field(default_factory=list)
    next_step: str = ""
    deployment_recommendation: str = ""
    release_score: int = 0
    release_score_parts: list[ReleaseScorePart] = field(default_factory=list)
    impact: dict[str, ImpactLevel] = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)
    doctor_overall_status: str = ""
    deploy_check_exit_code: int | None = None
    test_discovery_ok: bool = False
    policy_rules_triggered: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    backup_required: bool = False
    staging_required: bool = False
    production_blocked: bool = False
    git_status_entries: list[dict[str, str]] = field(default_factory=list)
    deployment_profile: str = "single_production"
    allow_dirty_build: bool = False
    test_discovery_local_env: bool = False
    test_discovery_error: str = ""
    local_environment: list[str] = field(default_factory=list)
    information: list[str] = field(default_factory=list)
    findings: list[ClassifiedFinding] = field(default_factory=list)
    summary: StatusSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "rationale": self.rationale,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "positives": list(self.positives),
            "next_step": self.next_step,
            "deployment_recommendation": self.deployment_recommendation,
            "release_score": self.release_score,
            "release_score_parts": [p.to_dict() for p in self.release_score_parts],
            "impact": {k: v.value for k, v in self.impact.items()},
            "changed_files": list(self.changed_files),
            "doctor_overall_status": self.doctor_overall_status,
            "deploy_check_exit_code": self.deploy_check_exit_code,
            "test_discovery_ok": self.test_discovery_ok,
            "policy_rules_triggered": list(self.policy_rules_triggered),
            "required_actions": list(self.required_actions),
            "backup_required": self.backup_required,
            "staging_required": self.staging_required,
            "production_blocked": self.production_blocked,
            "git_status_entries": list(self.git_status_entries),
            "deployment_profile": self.deployment_profile,
            "allow_dirty_build": self.allow_dirty_build,
            "test_discovery_local_env": self.test_discovery_local_env,
            "test_discovery_error": self.test_discovery_error,
            "local_environment": list(self.local_environment),
            "information": list(self.information),
            "findings": [
                f.to_dict() if hasattr(f, "to_dict") else f for f in self.findings
            ],
            "summary": self.summary.to_dict() if isinstance(self.summary, StatusSummary) else (
                self.summary if isinstance(self.summary, dict) else {}
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleaseEvaluateState:
        impact_raw = data.get("impact", {})
        return cls(
            status=ReleaseDecisionStatus(
                data.get("status", ReleaseDecisionStatus.PRODUCTION_BLOCKED.value)
            ),
            rationale=data.get("rationale", ""),
            blockers=list(data.get("blockers", [])),
            warnings=list(data.get("warnings", [])),
            positives=list(data.get("positives", [])),
            next_step=data.get("next_step", ""),
            deployment_recommendation=data.get("deployment_recommendation", ""),
            release_score=int(data.get("release_score", 0)),
            release_score_parts=[
                ReleaseScorePart.from_dict(p) for p in data.get("release_score_parts", [])
            ],
            impact={k: ImpactLevel(v) for k, v in impact_raw.items()},
            changed_files=list(data.get("changed_files", [])),
            doctor_overall_status=data.get("doctor_overall_status", ""),
            deploy_check_exit_code=data.get("deploy_check_exit_code"),
            test_discovery_ok=bool(data.get("test_discovery_ok", False)),
            policy_rules_triggered=list(data.get("policy_rules_triggered", [])),
            required_actions=list(data.get("required_actions", [])),
            backup_required=bool(data.get("backup_required", False)),
            staging_required=bool(data.get("staging_required", False)),
            production_blocked=bool(data.get("production_blocked", False)),
            git_status_entries=list(data.get("git_status_entries", [])),
            deployment_profile=data.get("deployment_profile", "single_production"),
            allow_dirty_build=bool(data.get("allow_dirty_build", False)),
            test_discovery_local_env=bool(data.get("test_discovery_local_env", False)),
            test_discovery_error=data.get("test_discovery_error", ""),
            local_environment=list(data.get("local_environment", [])),
            information=list(data.get("information", [])),
            findings=[
                ClassifiedFinding.from_dict(f) if isinstance(f, dict) else f
                for f in data.get("findings", [])
            ],
            summary=StatusSummary.from_dict(data["summary"])
            if isinstance(data.get("summary"), dict)
            else data.get("summary"),
        )
