from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from guardian_platform.profiles.ifg.config.defaults import REPO_ROOT


REPORTS_DIR = REPO_ROOT / "docs" / "reports"


def ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def deploy_report_path(prefix: str = "guardian_deploy") -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    return ensure_reports_dir() / f"{prefix}_{ts}.md"


def recover_report_path(prefix: str = "guardian_recover") -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M")
    return ensure_reports_dir() / f"{prefix}_{ts}.md"


def write_report(path: Path, content: str) -> Path:
    ensure_reports_dir()
    path.write_text(content, encoding="utf-8")
    return path
