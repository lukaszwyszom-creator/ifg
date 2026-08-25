from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ifg_guardian.core.deploy_config import DS723Config


@dataclass
class DeployExecutorContext:
    remote_host: str | None = None
    remote_path: str | None = None
    ds723: DS723Config | None = None
    executed_commands: list[str] = field(default_factory=list)
    # Immutable git-archive snapshot used as local build/rsync root (optional).
    build_root: Path | None = None
    build_commit: str = ""
    build_source: str = ""

    def config(self) -> DS723Config:
        if self.ds723 is None:
            self.ds723 = DS723Config.from_context(
                remote_host=self.remote_host,
                remote_path=self.remote_path,
            )
        return self.ds723

    def record(self, command: str) -> None:
        self.executed_commands.append(command)

    def local_build_root(self, fallback: Path) -> Path:
        return self.build_root if self.build_root is not None else fallback
