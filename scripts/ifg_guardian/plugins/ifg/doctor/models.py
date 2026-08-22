from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    CRITICAL = "CRITICAL"


class OverallStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


CHECK_SEVERITY = {
    CheckStatus.PASS: 0,
    CheckStatus.WARN: 1,
    CheckStatus.FAIL: 2,
    CheckStatus.CRITICAL: 3,
}


@dataclass
class CheckResult:
    check_id: str
    group: str
    name: str
    status: CheckStatus
    message: str
    details: list[str] = field(default_factory=list)
    scope: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "group": self.group,
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": list(self.details),
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckResult:
        return cls(
            check_id=data["check_id"],
            group=data.get("group", ""),
            name=data.get("name", ""),
            status=CheckStatus(data["status"]),
            message=data.get("message", ""),
            details=list(data.get("details", [])),
            scope=data.get("scope", "local"),
        )


@dataclass
class DoctorState:
    remote_host: str = ""
    remote_path: str = ""
    dry_run: bool = False
    do_fetch: bool = False
    checks: list[CheckResult] = field(default_factory=list)
    overall_status: OverallStatus = OverallStatus.READY
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "remote_host": self.remote_host,
            "remote_path": self.remote_path,
            "dry_run": self.dry_run,
            "do_fetch": self.do_fetch,
            "checks": [c.to_dict() for c in self.checks],
            "overall_status": self.overall_status.value,
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DoctorState:
        return cls(
            remote_host=data.get("remote_host", ""),
            remote_path=data.get("remote_path", ""),
            dry_run=data.get("dry_run", False),
            do_fetch=data.get("do_fetch", False),
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            overall_status=OverallStatus(data.get("overall_status", OverallStatus.READY.value)),
            summary=dict(data.get("summary", {})),
        )
