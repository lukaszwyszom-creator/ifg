from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.handoff_journal.integrity import (  # noqa: E402
    IntegrityCode,
    parse_handoff_metadata,
    rebuild_index_from_files_strict,
    validate_journal,
)
from ifg_guardian.core.handoff_journal.models import (
    ARTIFACT_FORMAT_VERSION,
    HANDOFF_GENERATOR_GUARDIAN,
    HANDOFF_SCHEMA_VERSION,
    HandoffMetadata,
    HandoffStatus,
    WorkflowType,
    format_handoff_id,
)
from ifg_guardian.core.handoff_journal.service import (
    HandoffJournalService,
    PublishStep,
    default_generated_artifacts,
    infer_workflow_type,
)
from ifg_guardian.core.handoff_journal.store import load_index
from ifg_guardian.modules.handoff_journal import (
    run_handoff_doctor,
    run_handoff_rebuild_index,
    run_handoff_rebuild_latest,
    run_handoff_validate,
)
from ifg_guardian.modules.ifg_handoff import run_ifg_handoff_latest


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


def _sample_body(*, next_step: str = "Brak.") -> str:
    return (
        "## Streszczenie\n\n"
        "Test body\n\n"
        "## Co wymaga decyzji ChatGPT\n\n"
        "Brak decyzji wymagających oceny ChatGPT.\n\n"
        "## Źródła\n\n"
        "### docs/reports/example.md\n\n"
        "Przeanalizowano; raport nie zawiera decyzji wymagających eskalacji.\n\n"
        "## Następny oczekiwany krok\n\n"
        f"{next_step}\n"
    )


def _publish_report(root: Path, name: str) -> int:
    _write_report(
        root / "docs" / "reports" / name,
        f"# GWO-TEST\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
    )
    return run_ifg_handoff_latest(root=root, copy_to_clipboard=False)


def test_sequential_numbering_three_handoffs(tmp_path: Path):
    _init_journal(tmp_path)
    assert _publish_report(tmp_path, "2026-07-11_GWO-TEST-0001_A.md") == 0
    assert _publish_report(tmp_path, "2026-07-11_GWO-TEST-0002_B.md") == 0
    assert _publish_report(tmp_path, "2026-07-11_GWO-TEST-0003_C.md") == 0

    index = load_index(tmp_path / "docs" / "handoff" / "index.json")
    assert index.count == 3
    assert index.latest_handoff_id == 3
    assert index.next_handoff_id == 4
    assert (tmp_path / "docs" / "handoff" / "HANDOFF-0001.md").is_file()
    assert (tmp_path / "docs" / "handoff" / "HANDOFF-0002.md").is_file()
    assert (tmp_path / "docs" / "handoff" / "HANDOFF-0003.md").is_file()

    second = parse_handoff_metadata((tmp_path / "docs" / "handoff" / "HANDOFF-0002.md").read_text(encoding="utf-8"))
    third = parse_handoff_metadata((tmp_path / "docs" / "handoff" / "HANDOFF-0003.md").read_text(encoding="utf-8"))
    assert second is not None and second.previous_handoff == "HANDOFF-0001"
    assert third is not None and third.previous_handoff == "HANDOFF-0002"


def test_restart_process_does_not_reset_index(tmp_path: Path):
    _init_journal(tmp_path)
    _publish_report(tmp_path, "2026-07-11_GWO-TEST-1001_A.md")
    index_path = tmp_path / "docs" / "handoff" / "index.json"
    saved = index_path.read_text(encoding="utf-8")

    service = HandoffJournalService(root=tmp_path)
    service.initialize()
    assert index_path.read_text(encoding="utf-8") == saved
    assert load_index(index_path).next_handoff_id == 2


def test_handoff_id_conflict_when_target_exists(tmp_path: Path):
    _init_journal(tmp_path)
    _write_report(tmp_path / "docs" / "reports" / "2026-07-11_GWO-TEST-2001_A.md", "# GWO\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    (tmp_path / "docs" / "handoff" / "HANDOFF-0001.md").write_text("existing\n", encoding="utf-8")
    assert run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False) == 1
    assert load_index(tmp_path / "docs" / "handoff" / "index.json").next_handoff_id == 1


def test_parallel_publish_allocates_distinct_ids(tmp_path: Path):
    _init_journal(tmp_path)
    results: list[int] = []
    errors: list[str] = []

    def _worker(report_name: str) -> None:
        root = tmp_path
        _write_report(
            root / "docs" / "reports" / report_name,
            f"# {report_name}\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
        )
        service = HandoffJournalService(root=root)
        metadata = HandoffMetadata(
            handoff_id=0,
            previous_handoff=None,
            parent_handoff=None,
            project_id="IFG",
            workflow="GWO-PARALLEL",
            workflow_type=WorkflowType.IMPLEMENTATION,
            status=HandoffStatus.SUCCESS,
            created_at="2026-07-11T12:00:00Z",
            source_reports=[f"docs/reports/{report_name}"],
            generated_artifacts=[],
            handoff_generator=HANDOFF_GENERATOR_GUARDIAN,
        )
        result = service.publish(metadata=metadata, body=_sample_body(), copy_to_clipboard=False)
        if result.ok and result.handoff_id is not None:
            results.append(result.handoff_id)
        else:
            errors.append(result.message)

    threads = [
        threading.Thread(target=_worker, args=(f"2026-07-11_GWO-PAR-{idx}.md",))
        for idx in range(1, 3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 2
    assert sorted(results) == [1, 2]
    assert load_index(tmp_path / "docs" / "handoff" / "index.json").count == 2


def test_first_handoff_publish_v1(tmp_path: Path):
    _init_journal(tmp_path)
    _write_report(
        tmp_path / "docs" / "reports" / "2026-07-11_GWO-IFG-9001_A.md",
        "# GWO-IFG-9001\n\n## Decyzje dla ChatGPT\n\nBrak.\n",
    )
    assert run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False) == 0

    handoff_file = tmp_path / "docs" / "handoff" / "HANDOFF-0001.md"
    text = handoff_file.read_text(encoding="utf-8")
    assert "artifact_format_version: 1" in text
    assert "handoff_generator: guardian" in text
    assert "generated_artifacts:" in text
    assert "docs/reports/2026-07-11_GWO-IFG-9001_A.md" not in text.split("generated_artifacts:")[1].split("---")[0]
    assert "## Wynik workflow" in text
    assert "IMPLEMENTED" in text
    assert "Przeanalizowano" in text

    metadata = parse_handoff_metadata(text)
    assert metadata is not None
    assert metadata.generated_artifacts == default_generated_artifacts(1)
    assert metadata.handoff_generator == HANDOFF_GENERATOR_GUARDIAN
    assert metadata.artifact_format_version == ARTIFACT_FORMAT_VERSION
    assert metadata.handoff_schema == HANDOFF_SCHEMA_VERSION


def test_parent_handoff_metadata(tmp_path: Path):
    _init_journal(tmp_path)
    service = HandoffJournalService(root=tmp_path)
    _write_report(tmp_path / "docs" / "reports" / "example.md", "# Example\n")
    metadata = HandoffMetadata(
        handoff_id=0,
        previous_handoff=None,
        parent_handoff="HANDOFF-0099",
        project_id="IFG",
        workflow="GWO-GUARDIAN-0075C",
        workflow_type=WorkflowType.IMPLEMENTATION,
        status=HandoffStatus.SUCCESS,
        created_at="2026-07-11T12:00:00Z",
        source_reports=["docs/reports/example.md"],
        generated_artifacts=[],
        handoff_generator=HANDOFF_GENERATOR_GUARDIAN,
    )
    result = service.publish(metadata=metadata, body=_sample_body(), copy_to_clipboard=False)
    assert result.ok
    parsed = parse_handoff_metadata((tmp_path / "docs" / "handoff" / "HANDOFF-0001.md").read_text(encoding="utf-8"))
    assert parsed is not None
    assert parsed.parent_handoff == "HANDOFF-0099"
    assert "docs/reports/example.md" not in parsed.generated_artifacts


def test_validate_v1_journal(tmp_path: Path):
    _init_journal(tmp_path)
    _publish_report(tmp_path, "2026-07-11_GWO-IFG-2001_A.md")
    assert run_handoff_validate(root=tmp_path) == 0


def test_workflow_type_enum_architecture_hotfix():
    assert infer_workflow_type("GWO-GUARDIAN-ADR-ARCHITECTURE") == WorkflowType.ARCHITECTURE
    assert infer_workflow_type("GWO-IFG-HOTFIX-001") == WorkflowType.HOTFIX


def test_next_step_extracted_from_source_report(tmp_path: Path):
    _init_journal(tmp_path)
    _write_report(
        tmp_path / "docs" / "reports" / "2026-07-11_GWO-IFG-8001_A.md",
        "# GWO-IFG-8001\n\n## Decyzje dla ChatGPT\n\nBrak.\n\nE. Następny krok\n\nGWO-IFG-0082 — powiadomienia.\n",
    )
    run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False)
    text = (tmp_path / "docs" / "handoff" / "HANDOFF-0001.md").read_text(encoding="utf-8")
    assert "GWO-IFG-0082" in text


def test_legacy_format_accepted_with_notice(tmp_path: Path):
    _init_journal(tmp_path)
    legacy = tmp_path / "docs" / "handoff" / "handoff-0001.md"
    legacy.write_text(
        """---
kind: handoff
handoff_id: 0001
previous_handoff: null
parent_handoff: null
project: IFG
workflow: GWO-LEGACY
workflow_type: IMPLEMENTATION
status: SUCCESS
created_at: 2026-07-10T10:00:00Z
source_reports:
  - docs/reports/legacy.md
---

# CHATGPT HANDOFF 2026-07-10

Legacy body
""",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reports" / "legacy.md").write_text("# legacy\n", encoding="utf-8")
    (tmp_path / "docs" / "handoff" / "index.json").write_text(
        json.dumps({"schema_version": 1, "next_handoff_id": 2, "latest_handoff_id": 1, "count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "handoff" / "latest.md").write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")

    report = validate_journal(root=tmp_path)
    assert report.valid
    assert any(item.code == IntegrityCode.LEGACY_FORMAT for item in report.legacy_notices)


def test_rebuild_index_and_latest(tmp_path: Path):
    _init_journal(tmp_path)
    _publish_report(tmp_path, "2026-07-11_GWO-IFG-3001_A.md")

    index_path = tmp_path / "docs" / "handoff" / "index.json"
    broken = json.loads(index_path.read_text(encoding="utf-8"))
    broken["count"] = 99
    index_path.write_text(json.dumps(broken, indent=2) + "\n", encoding="utf-8")

    assert run_handoff_rebuild_index(root=tmp_path) == 0
    assert load_index(index_path).count == 1

    latest = tmp_path / "docs" / "handoff" / "latest.md"
    latest.write_text("broken", encoding="utf-8")
    assert run_handoff_rebuild_latest(root=tmp_path) == 0
    assert latest.read_bytes() == (tmp_path / "docs" / "handoff" / "HANDOFF-0001.md").read_bytes()


def test_rebuild_index_detects_duplicate_conflict(tmp_path: Path):
    _init_journal(tmp_path)
    handoff_dir = tmp_path / "docs" / "handoff"
    body = """---
kind: handoff
handoff_schema: 1
handoff_id: HANDOFF-0001
previous_handoff: null
parent_handoff: null
project_id: IFG
workflow: GWO-DUP
workflow_type: IMPLEMENTATION
status: SUCCESS
created_at: 2026-07-11T12:00:00Z
artifact_format_version: 1
handoff_generator: guardian
source_reports:
  - docs/reports/x.md
generated_artifacts:
  - docs/handoff/HANDOFF-0001.md
  - docs/handoff/latest.md
---

# HANDOFF-0001

## Wynik workflow

IMPLEMENTED

## Następny oczekiwany krok

Brak.
"""
    (handoff_dir / "HANDOFF-0001.md").write_text(body, encoding="utf-8")
    mismatch = body.replace("handoff_id: HANDOFF-0001", "handoff_id: HANDOFF-0099")
    (handoff_dir / "HANDOFF-0002.md").write_text(mismatch, encoding="utf-8")
    (tmp_path / "docs" / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reports" / "x.md").write_text("# x\n", encoding="utf-8")
    result = rebuild_index_from_files_strict(handoff_dir)
    assert not result.ok
    assert any(item.code == IntegrityCode.FILENAME_ID_MISMATCH for item in result.issues)
    assert run_handoff_rebuild_index(root=tmp_path) == 1


def test_doctor_shows_next_expected_id(tmp_path: Path, capsys):
    _init_journal(tmp_path)
    _publish_report(tmp_path, "2026-07-11_GWO-IFG-4001_A.md")
    assert run_handoff_doctor(root=tmp_path) == 0
    output = capsys.readouterr().out
    assert "next=HANDOFF-0002" in output
    assert "count=1" in output


def test_doctor_detects_latest_mismatch(tmp_path: Path):
    _init_journal(tmp_path)
    _publish_report(tmp_path, "2026-07-11_GWO-IFG-4002_A.md")
    (tmp_path / "docs" / "handoff" / "latest.md").write_text("stale", encoding="utf-8")
    assert run_handoff_doctor(root=tmp_path) == 1


def test_clipboard_failure_marks_workflow_failed(tmp_path: Path, monkeypatch):
    _init_journal(tmp_path)
    _write_report(tmp_path / "docs" / "reports" / "2026-07-11_GWO-IFG-5001_A.md", "# GWO\n\n## Decyzje dla ChatGPT\n\nBrak.\n")
    monkeypatch.setattr(
        "ifg_guardian.core.clipboard.copy_text_to_clipboard",
        lambda _content: (False, "pbcopy exit 1"),
    )
    assert run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=True) == 1
    assert load_index(tmp_path / "docs" / "handoff" / "index.json").next_handoff_id == 1


def test_latest_write_failure_does_not_consume_next_id(tmp_path: Path, monkeypatch):
    _init_journal(tmp_path)
    service = HandoffJournalService(root=tmp_path)
    _write_report(tmp_path / "docs" / "reports" / "example.md", "# Example\n")
    metadata = HandoffMetadata(
        handoff_id=0,
        previous_handoff=None,
        parent_handoff=None,
        project_id="IFG",
        workflow="GWO-TEST",
        workflow_type=WorkflowType.IMPLEMENTATION,
        status=HandoffStatus.SUCCESS,
        created_at="2026-07-11T12:00:00Z",
        source_reports=["docs/reports/example.md"],
        generated_artifacts=[],
        handoff_generator=HANDOFF_GENERATOR_GUARDIAN,
    )

    def _boom(_path, _content):
        raise OSError("latest write failed")

    monkeypatch.setattr("ifg_guardian.core.handoff_journal.service.write_latest", _boom)
    result = service.publish(metadata=metadata, body=_sample_body(), copy_to_clipboard=False)
    assert not result.ok
    assert result.failed_step == PublishStep.LATEST_UPDATED
    index = load_index(tmp_path / "docs" / "handoff" / "index.json")
    assert index.next_handoff_id == 1
    assert index.count == 0


def test_v1_rejects_legacy_yaml_fields(tmp_path: Path):
    _init_journal(tmp_path)
    bad = tmp_path / "docs" / "handoff" / "HANDOFF-0001.md"
    bad.write_text(
        """---
kind: handoff
handoff_schema: 1
handoff_id: HANDOFF-0001
previous_handoff: null
parent_handoff: null
project: IFG
workflow: GWO-BAD
workflow_type: IMPLEMENTATION
status: SUCCESS
created_at: 2026-07-11T12:00:00Z
cursor_format_version: 1
handoff_generator: guardian
source_reports:
  - docs/reports/x.md
generated_reports:
  - docs/handoff/HANDOFF-0001.md
  - docs/handoff/latest.md
---

# HANDOFF-0001

## Wynik workflow

IMPLEMENTED

## Źródła

### docs/reports/x.md

Przeanalizowano raport źródłowy.

## Następny oczekiwany krok

Brak.
""",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "reports").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "reports" / "x.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "docs" / "handoff" / "index.json").write_text(
        json.dumps({"schema_version": 1, "next_handoff_id": 2, "latest_handoff_id": 1, "count": 1}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "handoff" / "latest.md").write_bytes(bad.read_bytes())

    report = validate_journal(root=tmp_path)
    assert not report.valid
    assert any(item.code == IntegrityCode.LEGACY_YAML_FIELD for item in report.issues)


def test_publish_fails_when_validate_would_fail(tmp_path: Path, monkeypatch):
    _init_journal(tmp_path)
    _write_report(tmp_path / "docs" / "reports" / "2026-07-11_GWO-IFG-6001_A.md", "# GWO\n\n## Decyzje dla ChatGPT\n\nBrak.\n")

    def _broken_validate(*, root, index_override=None):
        from ifg_guardian.core.handoff_journal.integrity import IntegrityIssue, ValidationReport

        return ValidationReport(
            valid=False,
            issues=[IntegrityIssue(code=IntegrityCode.INVALID_INDEX, message="forced validation failure")],
        )

    monkeypatch.setattr("ifg_guardian.core.handoff_journal.service.validate_journal", _broken_validate)
    assert run_ifg_handoff_latest(root=tmp_path, copy_to_clipboard=False) == 1
    assert load_index(tmp_path / "docs" / "handoff" / "index.json").next_handoff_id == 1


def test_source_description_cannot_be_only_brak(tmp_path: Path):
    _init_journal(tmp_path)
    service = HandoffJournalService(root=tmp_path)
    _write_report(tmp_path / "docs" / "reports" / "example.md", "# Example\n")
    metadata = HandoffMetadata(
        handoff_id=0,
        previous_handoff=None,
        parent_handoff=None,
        project_id="IFG",
        workflow="GWO-TEST",
        workflow_type=WorkflowType.IMPLEMENTATION,
        status=HandoffStatus.SUCCESS,
        created_at="2026-07-11T12:00:00Z",
        source_reports=["docs/reports/example.md"],
        generated_artifacts=[],
        handoff_generator=HANDOFF_GENERATOR_GUARDIAN,
    )
    bad_body = (
        "## Streszczenie\n\nBody\n\n"
        "## Co wymaga decyzji ChatGPT\n\nBrak.\n\n"
        "## Źródła\n\n### docs/reports/example.md\n\nBrak.\n\n"
        "## Następny oczekiwany krok\n\nBrak.\n"
    )
    result = service.publish(metadata=metadata, body=bad_body, copy_to_clipboard=False)
    assert not result.ok
    assert result.failed_step == PublishStep.JOURNAL_VALIDATED
