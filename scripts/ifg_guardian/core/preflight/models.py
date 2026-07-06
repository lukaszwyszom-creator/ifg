from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ifg_guardian.core.time_compat import UTC
from enum import Enum
from typing import Any

from ifg_guardian.core.workflow.mode import ExecutionMode


class PreflightStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class DeploymentDecisionStatus(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"


@dataclass
class PreflightCheckResult:
    check_id: str
    label: str
    status: PreflightStatus
    description: str
    duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreflightReport:
    checks: list[PreflightCheckResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    duration_ms: int = 0
    workflow_id: str = ""
    mode: str = ""

    def add(self, result: PreflightCheckResult) -> None:
        self.checks.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.status == PreflightStatus.PASS)

    @property
    def warnings(self) -> int:
        return sum(1 for c in self.checks if c.status == PreflightStatus.WARNING)

    @property
    def failures(self) -> int:
        return sum(1 for c in self.checks if c.status == PreflightStatus.FAIL)


@dataclass
class DeploymentDecision:
    status: DeploymentDecisionStatus
    blocking_items: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def is_go(self) -> bool:
        return self.status == DeploymentDecisionStatus.GO


@dataclass
class PreflightContext:
    root: Any
    mode: ExecutionMode
    remote_host: str | None = None
    remote_path: str | None = None
    compose_file: str = "docker/docker-compose.prod.yml"
    env_file: str = ".env.production"
    target_branch: str = "production"
    skip_remote: bool = False
