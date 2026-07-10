from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilitySet:
    """Backend capability declaration — Etap 4 (not implemented)."""

    supports_project: bool = False
    supports_build: bool = False
    supports_restart: bool = False
    supports_logs: bool = False
    supports_stream: bool = False
    supports_snapshot: bool = False
    supports_backup: bool = False
    supports_restore: bool = False
    supports_health: bool = False
    supports_shell: bool = False
    supports_exec: bool = False
    supports_scaling: bool = False
    supports_rolling_update: bool = False


class CapabilityEngine:
    """Validate operation against backend capabilities — Etap 4 (not implemented)."""

    def can_execute(self, backend_name: str, operation: str, capabilities: CapabilitySet) -> bool:
        raise NotImplementedError("Capability Engine — planned for Etap 4")
