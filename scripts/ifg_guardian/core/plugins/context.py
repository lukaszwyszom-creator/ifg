from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ifg_guardian.core.plugins.registry import PluginRegistry


@dataclass(frozen=True)
class GuardianConfig:
    root: Path


class GuardianLogger:
    """Thin logging wrapper for plugins."""

    def __init__(self, name: str = "guardian") -> None:
        self._logger = logging.getLogger(name)

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)


@dataclass
class PluginContext:
    config: GuardianConfig
    logger: GuardianLogger
    registry: PluginRegistry
    metadata: dict[str, Any] = field(default_factory=dict)
