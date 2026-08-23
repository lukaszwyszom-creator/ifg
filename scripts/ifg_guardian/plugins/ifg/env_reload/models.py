"""Modele workflow przeładowania środowiska IFG (GWO-GUARDIAN-0079)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EnvReloadStageStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class EnvReloadOverallStatus(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"


@dataclass
class PreflightCheck:
    key: str
    status: EnvReloadStageStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "status": self.status.value, "message": self.message}


@dataclass
class ServiceStatus:
    service: str
    running: bool
    state_line: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "running": self.running,
            "state_line": self.state_line,
        }


@dataclass
class EnvReloadState:
    dry_run: bool = False
    remote_host: str = ""
    remote_path: str = ""
    env_file: str = ""
    env_file_exists: bool = False
    compose_file: str = ""
    compose_up_executed: bool = False
    compose_up_output: str = ""
    containers_restarted: list[str] = field(default_factory=list)
    service_statuses: list[ServiceStatus] = field(default_factory=list)
    preflight_checks: list[PreflightCheck] = field(default_factory=list)
    health_ok: bool = False
    health_detail: str = ""
    startup_logs: str = ""
    startup_logs_summary: list[str] = field(default_factory=list)
    overall_status: EnvReloadOverallStatus = EnvReloadOverallStatus.READY
    operator_actions: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "remote_host": self.remote_host,
            "remote_path": self.remote_path,
            "env_file": self.env_file,
            "env_file_exists": self.env_file_exists,
            "compose_file": self.compose_file,
            "compose_up_executed": self.compose_up_executed,
            "compose_up_output": self.compose_up_output,
            "containers_restarted": list(self.containers_restarted),
            "service_statuses": [s.to_dict() for s in self.service_statuses],
            "preflight_checks": [c.to_dict() for c in self.preflight_checks],
            "health_ok": self.health_ok,
            "health_detail": self.health_detail,
            "startup_logs": self.startup_logs,
            "startup_logs_summary": list(self.startup_logs_summary),
            "overall_status": self.overall_status.value,
            "operator_actions": list(self.operator_actions),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvReloadState:
        return cls(
            dry_run=bool(data.get("dry_run", False)),
            remote_host=data.get("remote_host", ""),
            remote_path=data.get("remote_path", ""),
            env_file=data.get("env_file", ""),
            env_file_exists=bool(data.get("env_file_exists", False)),
            compose_file=data.get("compose_file", ""),
            compose_up_executed=bool(data.get("compose_up_executed", False)),
            compose_up_output=data.get("compose_up_output", ""),
            containers_restarted=list(data.get("containers_restarted", [])),
            service_statuses=[
                ServiceStatus(
                    service=s.get("service", ""),
                    running=bool(s.get("running", False)),
                    state_line=s.get("state_line", ""),
                )
                for s in data.get("service_statuses", [])
            ],
            preflight_checks=[
                PreflightCheck(
                    key=c.get("key", ""),
                    status=EnvReloadStageStatus(c.get("status", EnvReloadStageStatus.FAIL.value)),
                    message=c.get("message", ""),
                )
                for c in data.get("preflight_checks", [])
            ],
            health_ok=bool(data.get("health_ok", False)),
            health_detail=data.get("health_detail", ""),
            startup_logs=data.get("startup_logs", ""),
            startup_logs_summary=list(data.get("startup_logs_summary", [])),
            overall_status=EnvReloadOverallStatus(
                data.get("overall_status", EnvReloadOverallStatus.BLOCKED.value)
            ),
            operator_actions=list(data.get("operator_actions", [])),
            summary=dict(data.get("summary", {})),
        )

    def preflight_has_fail(self) -> bool:
        return any(c.status == EnvReloadStageStatus.FAIL for c in self.preflight_checks)

    def services_running(self) -> bool:
        if not self.service_statuses:
            return False
        return all(s.running for s in self.service_statuses)
