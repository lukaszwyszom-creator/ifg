"""Modele workflow SMTP Guardiana (GWO-GUARDIAN-0078)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SmtpStageStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class SmtpOverallStatus(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class SmtpEnvironment(str, Enum):
    REMOTE = "REMOTE"
    LOCAL = "LOCAL"


@dataclass
class ConfigCheck:
    key: str
    status: SmtpStageStatus
    message: str
    masked_value: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "status": self.status.value,
            "message": self.message,
            "masked_value": self.masked_value,
        }


@dataclass
class ConnectivityCheck:
    stage: str
    status: SmtpStageStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "status": self.status.value,
            "message": self.message,
        }


@dataclass
class TestMailResult:
    sent: bool
    status: SmtpStageStatus
    message: str
    subject: str = "IFG SMTP Test"
    recipients: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "status": self.status.value,
            "message": self.message,
            "subject": self.subject,
            "recipients": list(self.recipients),
        }


@dataclass
class SmtpState:
    mode: str = "check"
    environment: SmtpEnvironment = SmtpEnvironment.REMOTE
    remote_host: str = ""
    ssh_ok: bool = False
    env_file: str = ""
    notify_enabled: bool = False
    recipients: list[str] = field(default_factory=list)
    config_checks: list[ConfigCheck] = field(default_factory=list)
    connectivity_checks: list[ConnectivityCheck] = field(default_factory=list)
    masked_config: dict[str, str] = field(default_factory=dict)
    test_result: TestMailResult | None = None
    overall_status: SmtpOverallStatus = SmtpOverallStatus.READY
    operator_actions: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "environment": self.environment.value,
            "remote_host": self.remote_host,
            "ssh_ok": self.ssh_ok,
            "env_file": self.env_file,
            "notify_enabled": self.notify_enabled,
            "recipients": list(self.recipients),
            "config_checks": [c.to_dict() for c in self.config_checks],
            "connectivity_checks": [c.to_dict() for c in self.connectivity_checks],
            "masked_config": dict(self.masked_config),
            "test_result": self.test_result.to_dict() if self.test_result else None,
            "overall_status": self.overall_status.value,
            "operator_actions": list(self.operator_actions),
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SmtpState:
        test_raw = data.get("test_result")
        test_result = None
        if isinstance(test_raw, dict):
            test_result = TestMailResult(
                sent=bool(test_raw.get("sent", False)),
                status=SmtpStageStatus(test_raw.get("status", SmtpStageStatus.FAIL.value)),
                message=test_raw.get("message", ""),
                subject=test_raw.get("subject", "IFG SMTP Test"),
                recipients=list(test_raw.get("recipients", [])),
            )
        return cls(
            mode=data.get("mode", "check"),
            environment=SmtpEnvironment(data.get("environment", SmtpEnvironment.REMOTE.value)),
            remote_host=data.get("remote_host", ""),
            ssh_ok=bool(data.get("ssh_ok", False)),
            env_file=data.get("env_file", ""),
            notify_enabled=bool(data.get("notify_enabled", False)),
            recipients=list(data.get("recipients", [])),
            config_checks=[
                ConfigCheck(
                    key=c.get("key", ""),
                    status=SmtpStageStatus(c.get("status", SmtpStageStatus.FAIL.value)),
                    message=c.get("message", ""),
                    masked_value=c.get("masked_value", ""),
                )
                for c in data.get("config_checks", [])
            ],
            connectivity_checks=[
                ConnectivityCheck(
                    stage=c.get("stage", ""),
                    status=SmtpStageStatus(c.get("status", SmtpStageStatus.FAIL.value)),
                    message=c.get("message", ""),
                )
                for c in data.get("connectivity_checks", [])
            ],
            masked_config=dict(data.get("masked_config", {})),
            test_result=test_result,
            overall_status=SmtpOverallStatus(data.get("overall_status", SmtpOverallStatus.BLOCKED.value)),
            operator_actions=list(data.get("operator_actions", [])),
            summary=dict(data.get("summary", {})),
        )

    def config_has_fail(self) -> bool:
        return any(c.status == SmtpStageStatus.FAIL for c in self.config_checks)

    def connectivity_has_fail(self) -> bool:
        return any(c.status == SmtpStageStatus.FAIL for c in self.connectivity_checks)
