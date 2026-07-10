from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RuntimeContext:
    """Detected runtime environment (Etap 3+)."""

    host: str = ""
    platform: str = ""
    suggested_backend: str = ""
    confidence: str = "low"
    raw: dict[str, Any] | None = None


class DiscoveryEngine:
    """Auto-detect target environment and suggest backend — Etap 3 (not implemented)."""

    def discover(self) -> RuntimeContext:
        raise NotImplementedError("Discovery Engine — planned for Etap 3")
