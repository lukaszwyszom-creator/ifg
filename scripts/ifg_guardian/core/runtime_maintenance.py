"""Maintenance mode marker — Mac mini orchestration state (not in Git)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ifg_guardian.core.runtime_store import atomic_write_json, delete_state, load_or_default, read_json, state_path

MAINTENANCE_FILE = state_path("maintenance.json")
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MaintenanceMarker:
    active: bool
    operation_id: str
    started_at_utc: str
    actor: str
    hostname: str
    reason: str | None
    commit: str
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active": self.active,
            "operation_id": self.operation_id,
            "started_at_utc": self.started_at_utc,
            "actor": self.actor,
            "hostname": self.hostname,
            "reason": self.reason,
            "commit": self.commit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MaintenanceMarker | None:
        if not data.get("active"):
            return None
        operation_id = data.get("operation_id")
        started = data.get("started_at_utc")
        if not operation_id or not started:
            return None
        return cls(
            active=True,
            operation_id=str(operation_id),
            started_at_utc=str(started),
            actor=str(data.get("actor", "")),
            hostname=str(data.get("hostname", "")),
            reason=data.get("reason"),
            commit=str(data.get("commit", "")),
            schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        )


def load_maintenance_marker() -> MaintenanceMarker | None:
    data = read_json(MAINTENANCE_FILE)
    if not data:
        return None
    return MaintenanceMarker.from_dict(data)


def save_maintenance_marker(marker: MaintenanceMarker) -> None:
    atomic_write_json(MAINTENANCE_FILE, marker.to_dict())


def clear_maintenance_marker() -> bool:
    return delete_state(MAINTENANCE_FILE)


def maintenance_is_active() -> bool:
    return load_maintenance_marker() is not None
