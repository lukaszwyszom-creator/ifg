from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ifg_guardian.config import ROOT
from ifg_guardian.core.handoff_journal.models import (
    VALID_HANDOFF_STATUSES,
    VALID_WORKFLOW_TYPES,
    HandoffIndex,
    HandoffMetadata,
    HandoffStatus,
    WorkflowType,
)
from ifg_guardian.core.handoff_journal.store import (
    HANDOFF_DIR,
    INDEX_PATH,
    LATEST_PATH,
    handoff_path,
    load_index,
)

HANDOFF_FILE_RE = re.compile(r"^handoff-(\d{4})\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)


class IntegrityCode(str, Enum):
    OK = "OK"
    DUPLICATE_ID = "DUPLICATE_ID"
    INVALID_INDEX = "INVALID_INDEX"
    LATEST_MISMATCH = "LATEST_MISMATCH"
    MISSING_LATEST = "MISSING_LATEST"
    MISSING_HANDOFF = "MISSING_HANDOFF"
    INVALID_YAML = "INVALID_YAML"
    INVALID_PREVIOUS = "INVALID_PREVIOUS"
    INVALID_PARENT = "INVALID_PARENT"
    GAP_IN_SEQUENCE = "GAP_IN_SEQUENCE"
    MISSING_SOURCE_REPORT = "MISSING_SOURCE_REPORT"
    INVALID_SCHEMA_VERSION = "INVALID_SCHEMA_VERSION"


@dataclass
class IntegrityIssue:
    code: IntegrityCode
    message: str
    handoff_id: int | None = None


@dataclass
class ValidationReport:
    valid: bool
    issues: list[IntegrityIssue] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.valid else 1


@dataclass
class DoctorReport:
    issues: list[IntegrityIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.issues


def _parse_front_matter_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_list_key: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list_key:
            fields.setdefault(current_list_key, "")
            existing = fields[current_list_key]
            item = stripped[2:].strip()
            fields[current_list_key] = f"{existing}\n{item}" if existing else item
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if value.lower() == "null":
            fields[key] = ""
        else:
            fields[key] = value
        current_list_key = key if key == "source_reports" else None
    return fields


def parse_handoff_metadata(content: str) -> HandoffMetadata | None:
    match = FRONT_MATTER_RE.match(content)
    if not match:
        return None
    fields = _parse_front_matter_fields(match.group(1))
    if fields.get("kind", "").lower() != "handoff":
        return None
    handoff_id_raw = fields.get("handoff_id", "")
    if not handoff_id_raw.isdigit():
        return None
    handoff_id = int(handoff_id_raw)

    previous_raw = fields.get("previous_handoff", "")
    previous = int(previous_raw) if previous_raw.isdigit() else None

    parent_raw = fields.get("parent_handoff", "")
    parent = int(parent_raw) if parent_raw.isdigit() else None

    workflow_type_raw = fields.get("workflow_type", WorkflowType.IMPLEMENTATION.value)
    if workflow_type_raw not in VALID_WORKFLOW_TYPES:
        return None

    status_raw = fields.get("status", HandoffStatus.SUCCESS.value)
    if status_raw not in VALID_HANDOFF_STATUSES:
        return None

    created_at = fields.get("created_at", "").strip()
    if not created_at:
        return None

    source_reports: list[str] = []
    if "source_reports" in fields and fields["source_reports"]:
        source_reports = [line.strip() for line in fields["source_reports"].splitlines() if line.strip()]

    project = fields.get("project", "").strip()
    workflow = fields.get("workflow", "").strip()
    if not project or not workflow:
        return None

    return HandoffMetadata(
        handoff_id=handoff_id,
        previous_handoff=previous,
        parent_handoff=parent,
        project=project,
        workflow=workflow,
        workflow_type=WorkflowType(workflow_type_raw),
        status=HandoffStatus(status_raw),
        created_at=created_at,
        source_reports=source_reports,
    )


def scan_handoff_files(handoff_dir: Path | None = None) -> dict[int, Path]:
    directory = handoff_dir or HANDOFF_DIR
    if not directory.is_dir():
        return {}
    found: dict[int, Path] = {}
    for path in sorted(directory.glob("handoff-*.md")):
        match = HANDOFF_FILE_RE.match(path.name)
        if not match:
            continue
        handoff_id = int(match.group(1))
        found[handoff_id] = path
    return found


def rebuild_index_from_files(handoff_dir: Path | None = None, root: Path | None = None) -> HandoffIndex:
    directory = handoff_dir or (root / "docs" / "handoff" if root else HANDOFF_DIR)
    files = scan_handoff_files(directory)
    if not files:
        return HandoffIndex()
    ids = sorted(files)
    return HandoffIndex(
        schema_version=1,
        next_handoff_id=ids[-1] + 1,
        latest_handoff_id=ids[-1],
        count=len(ids),
    )


def validate_journal(*, root: Path | None = None) -> ValidationReport:
    issues: list[IntegrityIssue] = []
    handoff_dir = (root / "docs" / "handoff" if root else HANDOFF_DIR)
    index_path = handoff_dir / "index.json"
    latest_path = handoff_dir / "latest.md"

    try:
        index = load_index(index_path)
    except Exception as exc:
        issues.append(IntegrityIssue(code=IntegrityCode.INVALID_INDEX, message=str(exc)))
        return ValidationReport(valid=False, issues=issues)

    if index.schema_version < 1:
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_SCHEMA_VERSION,
                message=f"Unsupported schema_version: {index.schema_version}",
            )
        )

    files = scan_handoff_files(handoff_dir)
    file_ids = sorted(files)

    if index.count != len(file_ids):
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_INDEX,
                message=f"index.count={index.count}, files={len(file_ids)}",
            )
        )

    if index.latest_handoff_id is not None and index.latest_handoff_id not in files:
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_HANDOFF,
                message=f"latest_handoff_id {index.latest_handoff_id:04d} missing on disk",
                handoff_id=index.latest_handoff_id,
            )
        )

    if file_ids and index.next_handoff_id != file_ids[-1] + 1:
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_INDEX,
                message=f"next_handoff_id={index.next_handoff_id}, expected={file_ids[-1] + 1}",
            )
        )

    seen: set[int] = set()
    for handoff_id in file_ids:
        if handoff_id in seen:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.DUPLICATE_ID,
                    message=f"Duplicate handoff id {handoff_id:04d}",
                    handoff_id=handoff_id,
                )
            )
        seen.add(handoff_id)

    if file_ids:
        expected = list(range(1, file_ids[-1] + 1))
        if file_ids != expected:
            missing = sorted(set(expected) - set(file_ids))
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.GAP_IN_SEQUENCE,
                    message=f"Missing handoff ids: {', '.join(f'{i:04d}' for i in missing)}",
                )
            )

    parsed: dict[int, HandoffMetadata] = {}
    for handoff_id, path in files.items():
        try:
            content = path.read_bytes().decode("utf-8")
        except OSError as exc:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.MISSING_HANDOFF,
                    message=f"Cannot read {path.name}: {exc}",
                    handoff_id=handoff_id,
                )
            )
            continue
        metadata = parse_handoff_metadata(content)
        if metadata is None:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_YAML,
                    message=f"Invalid handoff YAML in {path.name}",
                    handoff_id=handoff_id,
                )
            )
            continue
        if metadata.handoff_id != handoff_id:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_YAML,
                    message=f"Filename/id mismatch in {path.name}",
                    handoff_id=handoff_id,
                )
            )
        parsed[handoff_id] = metadata

    for handoff_id, metadata in parsed.items():
        if metadata.previous_handoff is not None:
            if metadata.previous_handoff >= handoff_id:
                issues.append(
                    IntegrityIssue(
                        code=IntegrityCode.INVALID_PREVIOUS,
                        message=f"{metadata.format_id()}: previous_handoff must be lower",
                        handoff_id=handoff_id,
                    )
                )
            elif metadata.previous_handoff not in parsed and metadata.previous_handoff != 0:
                issues.append(
                    IntegrityIssue(
                        code=IntegrityCode.INVALID_PREVIOUS,
                        message=f"{metadata.format_id()}: previous_handoff {metadata.previous_handoff:04d} missing",
                        handoff_id=handoff_id,
                    )
                )
        elif handoff_id > 1:
            expected_prev = handoff_id - 1
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_PREVIOUS,
                    message=f"{metadata.format_id()}: expected previous_handoff {expected_prev:04d}",
                    handoff_id=handoff_id,
                )
            )

        if metadata.parent_handoff is not None and metadata.parent_handoff not in parsed:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_PARENT,
                    message=f"{metadata.format_id()}: parent_handoff {metadata.parent_handoff:04d} missing",
                    handoff_id=handoff_id,
                )
            )

        for report_rel in metadata.source_reports:
            report_path = (root or ROOT) / report_rel
            if not report_path.is_file():
                issues.append(
                    IntegrityIssue(
                        code=IntegrityCode.MISSING_SOURCE_REPORT,
                        message=f"{metadata.format_id()}: missing source report {report_rel}",
                        handoff_id=handoff_id,
                    )
                )

    if index.count > 0:
        if not latest_path.is_file():
            issues.append(
                IntegrityIssue(code=IntegrityCode.MISSING_LATEST, message="latest.md is missing")
            )
        elif index.latest_handoff_id is not None:
            latest_handoff = files.get(index.latest_handoff_id)
            if latest_handoff is not None:
                try:
                    handoff_bytes = latest_handoff.read_bytes()
                    latest_bytes = latest_path.read_bytes()
                    if handoff_bytes != latest_bytes:
                        issues.append(
                            IntegrityIssue(
                                code=IntegrityCode.LATEST_MISMATCH,
                                message=(
                                    f"latest.md is not byte-identical to "
                                    f"handoff-{index.latest_handoff_id:04d}.md"
                                ),
                                handoff_id=index.latest_handoff_id,
                            )
                        )
                except OSError as exc:
                    issues.append(
                        IntegrityIssue(
                            code=IntegrityCode.LATEST_MISMATCH,
                            message=f"Cannot compare latest.md: {exc}",
                        )
                    )

    return ValidationReport(valid=not issues, issues=issues)


def doctor_journal(*, root: Path | None = None) -> DoctorReport:
    report = validate_journal(root=root)
    suggestions: list[str] = []
    for issue in report.issues:
        if issue.code == IntegrityCode.INVALID_INDEX:
            suggestions.append("Run: guardian handoff rebuild-index")
        if issue.code in {IntegrityCode.LATEST_MISMATCH, IntegrityCode.MISSING_LATEST}:
            suggestions.append("Run: guardian handoff rebuild-latest")
        if issue.code == IntegrityCode.GAP_IN_SEQUENCE:
            suggestions.append("Inspect missing handoff files manually; rebuild-index will not invent content")
    return DoctorReport(issues=report.issues, suggestions=sorted(set(suggestions)))
