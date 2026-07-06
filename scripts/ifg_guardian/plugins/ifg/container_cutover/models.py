from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CutoverRunState:
    dry_run: bool = True
    rollback_commit: str = ""
    backup_file: str = ""
    compose_config_ok: bool = False
    safety_gate: str = ""
    cutover_executed: bool = False
    health_ok: bool = False
    guardian_verify_ok: bool = False
    functional_confirmed: bool = False
    cleanup_executed: bool = False
    warnings: list[str] = field(default_factory=list)
    rollback_command: str = ""
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "rollback_commit": self.rollback_commit,
            "backup_file": self.backup_file,
            "compose_config_ok": self.compose_config_ok,
            "safety_gate": self.safety_gate,
            "cutover_executed": self.cutover_executed,
            "health_ok": self.health_ok,
            "guardian_verify_ok": self.guardian_verify_ok,
            "functional_confirmed": self.functional_confirmed,
            "cleanup_executed": self.cleanup_executed,
            "warnings": list(self.warnings),
            "rollback_command": self.rollback_command,
            "summary": dict(self.summary),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CutoverRunState:
        return cls(
            dry_run=bool(data.get("dry_run", True)),
            rollback_commit=str(data.get("rollback_commit", "")),
            backup_file=str(data.get("backup_file", "")),
            compose_config_ok=bool(data.get("compose_config_ok")),
            safety_gate=str(data.get("safety_gate", "")),
            cutover_executed=bool(data.get("cutover_executed")),
            health_ok=bool(data.get("health_ok")),
            guardian_verify_ok=bool(data.get("guardian_verify_ok")),
            functional_confirmed=bool(data.get("functional_confirmed")),
            cleanup_executed=bool(data.get("cleanup_executed")),
            warnings=list(data.get("warnings", [])),
            rollback_command=str(data.get("rollback_command", "")),
            summary=dict(data.get("summary", {})),
        )
