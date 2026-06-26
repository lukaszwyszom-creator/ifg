from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ifg_guardian.config import REPORTS_DIR


def ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def default_report_path(prefix: str) -> Path:
    ts = datetime.now(UTC).strftime("%Y_%m_%d")
    return ensure_reports_dir() / f"{prefix}_{ts}.md"


def write_report(path: Path, content: str) -> Path:
    ensure_reports_dir()
    path.write_text(content, encoding="utf-8")
    return path
