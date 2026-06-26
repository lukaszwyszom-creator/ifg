from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeploymentRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


RISK_SEVERITY = {
    DeploymentRisk.LOW: 0,
    DeploymentRisk.MEDIUM: 1,
    DeploymentRisk.HIGH: 2,
    DeploymentRisk.CRITICAL: 3,
}


@dataclass
class BuildDecision:
    name: str
    required: bool
    reason: str
    confidence: str = "HIGH"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "reason": self.reason,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BuildDecision:
        return cls(
            name=data["name"],
            required=data.get("required", False),
            reason=data.get("reason", ""),
            confidence=data.get("confidence", "HIGH"),
        )


@dataclass
class PlannedArtifact:
    artifact_type: str
    identifier: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.artifact_type,
            "identifier": self.identifier,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannedArtifact:
        return cls(
            artifact_type=data.get("type", data.get("artifact_type", "")),
            identifier=data.get("identifier", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class ExecutionStep:
    order: int
    action: str
    description: str
    required: bool = True
    simulated: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "description": self.description,
            "required": self.required,
            "simulated": self.simulated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionStep:
        return cls(
            order=data.get("order", 0),
            action=data.get("action", ""),
            description=data.get("description", ""),
            required=data.get("required", True),
            simulated=data.get("simulated", True),
        )


@dataclass
class RepositorySnapshot:
    branch: str = ""
    head_sha: str = ""
    head_short: str = ""
    dirty: bool = False
    ahead: int = 0
    behind: int = 0
    backend_changes: list[str] = field(default_factory=list)
    frontend_changes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "head_sha": self.head_sha,
            "head_short": self.head_short,
            "dirty": self.dirty,
            "ahead": self.ahead,
            "behind": self.behind,
            "backend_changes": list(self.backend_changes),
            "frontend_changes": list(self.frontend_changes),
        }


@dataclass
class ReleasePlanState:
    question: str = "Co dokładnie zostanie wykonane, jeżeli uruchomię deploy?"
    doctor_overall_status: str = ""
    doctor_workflow_id: str = ""
    repository: RepositorySnapshot = field(default_factory=RepositorySnapshot)
    build_decisions: list[BuildDecision] = field(default_factory=list)
    artifacts: list[PlannedArtifact] = field(default_factory=list)
    execution_plan: list[ExecutionStep] = field(default_factory=list)
    deployment_risk: DeploymentRisk = DeploymentRisk.LOW
    risk_rationale: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "doctor_overall_status": self.doctor_overall_status,
            "doctor_workflow_id": self.doctor_workflow_id,
            "repository": self.repository.to_dict(),
            "build_decisions": [d.to_dict() for d in self.build_decisions],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "execution_plan": [s.to_dict() for s in self.execution_plan],
            "deployment_risk": self.deployment_risk.value,
            "risk_rationale": list(self.risk_rationale),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReleasePlanState:
        repo = data.get("repository", {})
        return cls(
            question=data.get("question", ""),
            doctor_overall_status=data.get("doctor_overall_status", ""),
            doctor_workflow_id=data.get("doctor_workflow_id", ""),
            repository=RepositorySnapshot(
                branch=repo.get("branch", ""),
                head_sha=repo.get("head_sha", ""),
                head_short=repo.get("head_short", ""),
                dirty=repo.get("dirty", False),
                ahead=repo.get("ahead", 0),
                behind=repo.get("behind", 0),
                backend_changes=list(repo.get("backend_changes", [])),
                frontend_changes=list(repo.get("frontend_changes", [])),
            ),
            build_decisions=[BuildDecision.from_dict(d) for d in data.get("build_decisions", [])],
            artifacts=[PlannedArtifact.from_dict(a) for a in data.get("artifacts", [])],
            execution_plan=[ExecutionStep.from_dict(s) for s in data.get("execution_plan", [])],
            deployment_risk=DeploymentRisk(data.get("deployment_risk", DeploymentRisk.LOW.value)),
            risk_rationale=list(data.get("risk_rationale", [])),
            summary=dict(data.get("summary", {})),
        )
