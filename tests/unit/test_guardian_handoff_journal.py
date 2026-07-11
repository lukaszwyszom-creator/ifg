from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.handoff_journal.integrity import parse_handoff_metadata  # noqa: E402
from ifg_guardian.core.handoff_journal.models import (  # noqa: E402
    HandoffMetadata,
    HandoffStatus,
    WorkflowType,
)
from ifg_guardian.core.handoff_journal.service import HandoffJournalService, PublishStep  # noqa: E402
from ifg_guardian.core.handoff_journal.store import load_index  # noqa: E402
from ifg_guardian.modules.handoff_journal import (  # noqa: E402
    run_handoff_doctor,
    run_handoff_rebuild_index,
    run_handoff_rebuild_latest,
    run_handoff_validate,
)
from ifg_guardian.modules.ifg_handoff import run_ifg_handoff_latest  # noqa: E402


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_journal(root: Path) -> None:
    handoff_dir = root / "docs" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "index.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "next_handoff_id": 1,
                "latest_handoff_id": None,
                "count": 0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (handoff_dir / "latest.md").write_text("", encoding="utf-8")


def test_first_handoff_publish(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(
        reports / "2026-07-11_GWO-IFG-9001_A.md",
        "# GWO-IFG-9001\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
    )

    code = run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)
    assert code == 0

    handoff_file = tmp_path / "docs" / "handoff" / "handoff-0001.md"
    latest = tmp_path / "docs" / "handoff" / "latest.md"
    index = load_index(tmp_path / "docs" / "handoff" / "index.json")

    assert handoff_file.is_file()
    assert latest.read_bytes() == handoff_file.read_bytes()
    assert index.count == 1
    assert index.latest_handoff_id == 1
    assert index.next_handoff_id == 2

    metadata = parse_handoff_metadata(handoff_file.read_text(encoding="utf-8"))
    assert metadata is not None
    assert metadata.handoff_id == 1
    assert metadata.previous_handoff is None
    assert metadata.status == HandoffStatus.SUCCESS
    assert metadata.source_reports == ["docs/reports/2026-07-11_GWO-IFG-9001_A.md"]


def test_sequential_handoff_numbering(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-11_GWO-IFG-1001_A.md", "# GWO-IFG-1001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)
    _write_report(reports / "2026-07-11_GWO-IFG-1002_B.md", "# GWO-IFG-1002\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)

    index = load_index(tmp_path / "docs" / "handoff" / "index.json")
    assert index.count == 2
    assert index.latest_handoff_id == 2
    second = parse_handoff_metadata((tmp_path / "docs" / "handoff" / "handoff-0002.md").read_text(encoding="utf-8"))
    assert second is not None
    assert second.previous_handoff == 1


def test_parent_handoff_metadata(tmp_path: Path):
    _init_journal(tmp_path)
    service = HandoffJournalService(root=tmp_path)
    metadata = HandoffMetadata(
        handoff_id=1,
        previous_handoff=None,
        parent_handoff=1,
        project="IFG",
        workflow="GWO-GUARDIAN-0075",
        workflow_type=WorkflowType.IMPLEMENTATION,
        status=HandoffStatus.SUCCESS,
        created_at="2026-07-11T12:00:00Z",
        source_reports=["docs/reports/example.md"],
    )
    report = tmp_path / "docs" / "reports" / "example.md"
    _write_report(report, "# Example\n")
    result = service.publish(metadata=metadata, body="# CHATGPT HANDOFF\n\nBody", copy_to_clipboard=False)
    assert result.ok
    parsed = parse_handoff_metadata((tmp_path / "docs" / "handoff" / "handoff-0001.md").read_text(encoding="utf-8"))
    assert parsed is not None
    assert parsed.parent_handoff == 1


def test_validate_journal_ok(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-11_GWO-IFG-2001_A.md", "# GWO-IFG-2001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)
    assert run_handoff_validate(root=tmp_path) == 0


def test_rebuild_index_and_latest(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-11_GWO-IFG-3001_A.md", "# GWO-IFG-3001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)

    index_path = tmp_path / "docs" / "handoff" / "index.json"
    broken = json.loads(index_path.read_text(encoding="utf-8"))
    broken["count"] = 99
    index_path.write_text(json.dumps(broken, indent=2) + "\n", encoding="utf-8")

    assert run_handoff_rebuild_index(root=tmp_path) == 0
    rebuilt = load_index(index_path)
    assert rebuilt.count == 1

    latest = tmp_path / "docs" / "handoff" / "latest.md"
    latest.write_text("broken", encoding="utf-8")
    assert run_handoff_rebuild_latest(root=tmp_path) == 0
    assert latest.read_bytes() == (tmp_path / "docs" / "handoff" / "handoff-0001.md").read_bytes()


def test_doctor_detects_latest_mismatch(tmp_path: Path):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-11_GWO-IFG-4001_A.md", "# GWO-IFG-4001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)
    (tmp_path / "docs" / "handoff" / "latest.md").write_text("stale", encoding="utf-8")
    assert run_handoff_doctor(root=tmp_path) == 1


def test_clipboard_failure_marks_workflow_failed(tmp_path: Path, monkeypatch):
    _init_journal(tmp_path)
    reports = tmp_path / "docs" / "reports"
    _write_report(reports / "2026-07-11_GWO-IFG-5001_A.md", "# GWO-IFG-5001\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    monkeypatch.setattr(
        "ifg_guardian.core.clipboard.copy_text_to_clipboard",
        lambda _content: (False, "pbcopy exit 1"),
    )
    code = run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=True)
    assert code == 1
    index = load_index(tmp_path / "docs" / "handoff" / "index.json")
    assert index.count == 1


def test_latest_write_failure_does_not_consume_next_id(tmp_path: Path, monkeypatch):
    _init_journal(tmp_path)
    service = HandoffJournalService(root=tmp_path)
    report = tmp_path / "docs" / "reports" / "example.md"
    _write_report(report, "# Example\n")
    metadata = HandoffMetadata(
        handoff_id=1,
        previous_handoff=None,
        parent_handoff=None,
        project="IFG",
        workflow="GWO-TEST",
        workflow_type=WorkflowType.IMPLEMENTATION,
        status=HandoffStatus.SUCCESS,
        created_at="2026-07-11T12:00:00Z",
        source_reports=["docs/reports/example.md"],
    )

    def _boom(_path, _content):
        raise OSError("latest write failed")

    monkeypatch.setattr("ifg_guardian.core.handoff_journal.service.write_latest", _boom)
    result = service.publish(metadata=metadata, body="# CHATGPT HANDOFF\n\nBody", copy_to_clipboard=False)
    assert not result.ok
    assert result.failed_step == PublishStep.LATEST_UPDATED
    index = load_index(tmp_path / "docs" / "handoff" / "index.json")
    assert index.next_handoff_id == 1
    assert index.count == 0
