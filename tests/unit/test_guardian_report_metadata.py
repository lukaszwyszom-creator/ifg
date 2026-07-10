from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.report_metadata import (  # noqa: E402
    ReportMetadata,
    metadata_created_on,
    parse_created_at_epoch,
    parse_report_metadata,
    report_sort_epoch,
)


def test_parse_report_metadata_minimal():
    content = """---
kind: gwo
project: IFG
workflow: GWO-IFG-0064
handoff: true
created_at: 2026-07-10
---

# Report
"""
    meta = parse_report_metadata(content)
    assert meta == ReportMetadata(
        kind="gwo",
        project="IFG",
        workflow="GWO-IFG-0064",
        handoff=True,
        created_at="2026-07-10",
    )


def test_parse_report_metadata_without_front_matter_returns_none():
    assert parse_report_metadata("# Report\n\nBody") is None


def test_parse_report_metadata_handoff_false():
    content = """---
kind: adr
project: IFG
workflow: ADR-0065
handoff: false
created_at: 2026-07-11T12:00:00Z
---
"""
    meta = parse_report_metadata(content)
    assert meta is not None
    assert meta.handoff is False


def test_parse_report_metadata_incomplete_returns_none():
    content = """---
kind: gwo
project: IFG
---
"""
    assert parse_report_metadata(content) is None


def test_parse_created_at_epoch_supports_date_and_datetime():
    assert parse_created_at_epoch("2026-07-11") is not None
    assert parse_created_at_epoch("2026-07-11T10:30:00Z") is not None
    assert parse_created_at_epoch("invalid") is None


def test_metadata_created_on():
    assert metadata_created_on("2026-07-11", today=dt.date(2026, 7, 11)) is True
    assert metadata_created_on("2026-07-10", today=dt.date(2026, 7, 11)) is False
    assert metadata_created_on("2026-07-11T08:00:00Z", today=dt.date(2026, 7, 11)) is True


def test_report_sort_epoch_prefers_created_at(tmp_path: Path):
    path = tmp_path / "docs" / "reports" / "task.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        """---
kind: gwo
project: IFG
workflow: GWO-TEST-0001
handoff: true
created_at: 2026-07-11T23:59:00Z
---
""",
        encoding="utf-8",
    )
    epoch = report_sort_epoch(path)
    assert epoch == parse_created_at_epoch("2026-07-11T23:59:00Z")
