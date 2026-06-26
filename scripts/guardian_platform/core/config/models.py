from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectConfig:
    schema: str = "guardian_project_v1"
    root: Path = field(default_factory=Path.cwd)
    active_profiles: list[str] = field(default_factory=lambda: ["ifg_scaffold", "psag_scaffold"])
    reports_dir: Path = field(default_factory=lambda: Path("docs/guardian"))
    log_level: str = "INFO"

    @classmethod
    def defaults(cls, root: Path | None = None) -> ProjectConfig:
        base = root or Path.cwd()
        return cls(root=base.resolve(), reports_dir=(base / "docs/guardian").resolve())
