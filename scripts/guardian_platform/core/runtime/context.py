from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from guardian_platform.core.config.models import ProjectConfig
from guardian_platform.core.runtime.mode import ExecutionMode


@dataclass
class CommandContext:
    root: Path
    config: ProjectConfig
    argv: list[str]
    dry_run: bool = False
    assume_yes: bool = False
    output_format: str = "terminal"
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def execution_mode(self) -> ExecutionMode:
        if self.dry_run:
            return ExecutionMode.DRY_RUN
        return ExecutionMode.LIVE
