from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EnvironmentInfo:
    hostname: str
    platform: str
    python_version: str
    cwd: str
    ci: bool


def detect_environment(root: Path) -> EnvironmentInfo:
    return EnvironmentInfo(
        hostname=platform.node(),
        platform=platform.platform(),
        python_version=sys.version.split()[0],
        cwd=str(root.resolve()),
        ci=os.environ.get("CI", "").lower() in ("1", "true", "yes"),
    )
