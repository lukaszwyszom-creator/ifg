from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.handoff_journal.models import (
    ARTIFACT_FORMAT_VERSION,
    HANDOFF_FOOTER_RULE,
    HANDOFF_ID_RE,
    HANDOFF_SCHEMA_VERSION,
    VALID_HANDOFF_GENERATORS,
    VALID_HANDOFF_STATUSES,
    VALID_WORKFLOW_OUTCOMES,
    VALID_WORKFLOW_TYPES,
    HandoffIndex,
    HandoffMetadata,
    HandoffStatus,
    WorkflowType,
    format_handoff_id,
    parse_handoff_id_ref,
    status_to_workflow_outcome,
)
from ifg_guardian.core.handoff_journal.store import (
    HANDOFF_DIR,
    handoff_path,
    load_index,
)

V1_FILE_RE = re.compile(r"^HANDOFF-(\d{4})\.md$")
LEGACY_FILE_RE = re.compile(r"^handoff-(\d{4})\.md$")
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)


class IntegrityCode(str, Enum):
    OK = "OK"
    LEGACY_FORMAT = "LEGACY_FORMAT"
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
    MISSING_GENERATED_ARTIFACT = "MISSING_GENERATED_ARTIFACT"
    INVALID_SCHEMA_VERSION = "INVALID_SCHEMA_VERSION"
    INVALID_HANDOFF_SCHEMA = "INVALID_HANDOFF_SCHEMA"
    INVALID_ARTIFACT_FORMAT = "INVALID_ARTIFACT_FORMAT"
    INVALID_PROJECT_ID = "INVALID_PROJECT_ID"
    INVALID_WORKFLOW_TYPE = "INVALID_WORKFLOW_TYPE"
    MISSING_WORKFLOW_OUTCOME = "MISSING_WORKFLOW_OUTCOME"
    MISSING_NEXT_STEP = "MISSING_NEXT_STEP"
    LEGACY_YAML_FIELD = "LEGACY_YAML_FIELD"
    INVALID_HANDOFF_ID = "INVALID_HANDOFF_ID"
    MISSING_END_FOOTER = "MISSING_END_FOOTER"
    LEGACY_CHATGPT_HEADER = "LEGACY_CHATGPT_HEADER"
    TRAILING_CONTENT_AFTER_FOOTER = "TRAILING_CONTENT_AFTER_FOOTER"
    HANDOFF_ID_CONFLICT = "HANDOFF_ID_CONFLICT"
    INVALID_HANDOFF_GENERATOR = "INVALID_HANDOFF_GENERATOR"
    SOURCE_GENERATED_OVERLAP = "SOURCE_GENERATED_OVERLAP"
    INVALID_SOURCE_DESCRIPTION = "INVALID_SOURCE_DESCRIPTION"
    FILENAME_ID_MISMATCH = "FILENAME_ID_MISMATCH"


@dataclass
class IntegrityIssue:
    code: IntegrityCode
    message: str
    handoff_id: int | None = None


@dataclass
class ValidationReport:
    valid: bool
    issues: list[IntegrityIssue] = field(default_factory=list)
    legacy_notices: list[IntegrityIssue] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if self.valid else 1


@dataclass
class DoctorSummary:
    latest_handoff_id: int | None
    next_handoff_id: int
    count: int
    gaps: list[int] = field(default_factory=list)
    latest_status: str = "UNKNOWN"
    clipboard_status: str = "UNKNOWN"


@dataclass
class DoctorReport:
    issues: list[IntegrityIssue] = field(default_factory=list)
    legacy_notices: list[IntegrityIssue] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: DoctorSummary | None = None

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
        current_list_key = key if key in {"source_reports", "generated_artifacts", "generated_reports"} else None
    return fields


def _yaml_legacy_field_names(block: str) -> list[str]:
    legacy: list[str] = []
    if re.search(r"^project:\s", block, re.MULTILINE) and not re.search(r"^project_id:\s", block, re.MULTILINE):
        legacy.append("project")
    if "generated_reports:" in block and "generated_artifacts:" not in block:
        legacy.append("generated_reports")
    if "cursor_format_version:" in block and "artifact_format_version:" not in block:
        legacy.append("cursor_format_version")
    return legacy


def _extract_body_section(content: str, heading: str) -> str | None:
    lines = content.splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if capture:
                break
            capture = stripped.lower() == heading.lower()
            continue
        if not capture:
            continue
        if stripped.startswith("## "):
            break
        collected.append(line.rstrip())
    text = "\n".join(collected).strip()
    return text if text else None


def _is_legacy_filename(name: str) -> bool:
    return bool(LEGACY_FILE_RE.match(name))


def _detect_legacy_content(content: str, *, filename: str) -> bool:
    if _is_legacy_filename(filename):
        return True
    if V1_FILE_RE.match(filename):
        return False
    if "# CHATGPT HANDOFF" in content:
        return True
    match = FRONT_MATTER_RE.match(content)
    if not match:
        return False
    fields = _parse_front_matter_fields(match.group(1))
    handoff_id_raw = fields.get("handoff_id", "")
    return bool(handoff_id_raw.isdigit())


def parse_handoff_metadata(content: str) -> HandoffMetadata | None:
    match = FRONT_MATTER_RE.match(content)
    if not match:
        return None
    fields = _parse_front_matter_fields(match.group(1))
    if fields.get("kind", "").lower() != "handoff":
        return None

    handoff_id = parse_handoff_id_ref(fields.get("handoff_id", ""))
    if handoff_id is None:
        return None

    previous_raw = fields.get("previous_handoff", "")
    previous = fields.get("previous_handoff") or None
    if previous_raw and previous_raw.isdigit():
        previous = format_handoff_id(int(previous_raw))
    elif previous_raw and HANDOFF_ID_RE.match(previous_raw):
        previous = previous_raw
    elif not previous_raw:
        previous = None

    parent_raw = fields.get("parent_handoff", "")
    parent = fields.get("parent_handoff") or None
    if parent_raw and parent_raw.isdigit():
        parent = format_handoff_id(int(parent_raw))
    elif parent_raw and HANDOFF_ID_RE.match(parent_raw):
        parent = parent_raw
    elif not parent_raw:
        parent = None

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
    if fields.get("source_reports"):
        source_reports = [line.strip() for line in fields["source_reports"].splitlines() if line.strip()]

    generated_artifacts: list[str] = []
    if fields.get("generated_artifacts"):
        generated_artifacts = [line.strip() for line in fields["generated_artifacts"].splitlines() if line.strip()]
    elif fields.get("generated_reports"):
        generated_artifacts = [line.strip() for line in fields["generated_reports"].splitlines() if line.strip()]

    project_id = fields.get("project_id", "").strip() or fields.get("project", "").strip()
    workflow = fields.get("workflow", "").strip()
    if not project_id or not workflow:
        return None

    handoff_schema = int(fields.get("handoff_schema", HANDOFF_SCHEMA_VERSION))
    artifact_raw = fields.get("artifact_format_version") or fields.get("cursor_format_version")
    artifact_format_version = int(artifact_raw if artifact_raw else ARTIFACT_FORMAT_VERSION)
    handoff_generator = fields.get("handoff_generator", "guardian").strip() or "guardian"

    return HandoffMetadata(
        handoff_id=handoff_id,
        previous_handoff=previous,
        parent_handoff=parent,
        project_id=project_id,
        workflow=workflow,
        workflow_type=WorkflowType(workflow_type_raw),
        status=HandoffStatus(status_raw),
        created_at=created_at,
        source_reports=source_reports,
        generated_artifacts=generated_artifacts,
        handoff_schema=handoff_schema,
        artifact_format_version=artifact_format_version,
        handoff_generator=handoff_generator,
    )


def scan_v1_handoff_files(handoff_dir: Path | None = None) -> dict[int, Path]:
    directory = handoff_dir or HANDOFF_DIR
    if not directory.is_dir():
        return {}
    found: dict[int, Path] = {}
    for path in sorted(directory.glob("HANDOFF-*.md")):
        match = V1_FILE_RE.match(path.name)
        if not match:
            continue
        handoff_id = int(match.group(1))
        found[handoff_id] = path
    return found


def scan_handoff_files(handoff_dir: Path | None = None) -> dict[int, Path]:
    directory = handoff_dir or HANDOFF_DIR
    if not directory.is_dir():
        return {}
    found: dict[int, Path] = {}
    for path in sorted(directory.glob("*.md")):
        if path.name == "latest.md":
            continue
        match = V1_FILE_RE.match(path.name) or LEGACY_FILE_RE.match(path.name)
        if not match:
            continue
        handoff_id = int(match.group(1))
        found[handoff_id] = path
    return found


@dataclass
class RebuildIndexResult:
    ok: bool
    index: HandoffIndex = field(default_factory=HandoffIndex)
    issues: list[IntegrityIssue] = field(default_factory=list)


def rebuild_index_from_files(handoff_dir: Path | None = None, root: Path | None = None) -> HandoffIndex:
    result = rebuild_index_from_files_strict(handoff_dir=handoff_dir, root=root)
    return result.index


def rebuild_index_from_files_strict(
    handoff_dir: Path | None = None,
    root: Path | None = None,
) -> RebuildIndexResult:
    directory = handoff_dir or (root / "docs" / "handoff" if root else HANDOFF_DIR)
    files = scan_v1_handoff_files(directory)
    issues: list[IntegrityIssue] = []
    if not files:
        return RebuildIndexResult(ok=True, index=HandoffIndex())

    ids = sorted(files)
    seen_paths: dict[int, Path] = {}
    for handoff_id, path in files.items():
        if handoff_id in seen_paths:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.DUPLICATE_ID,
                    message=f"Duplicate HANDOFF id {format_handoff_id(handoff_id)}: {seen_paths[handoff_id].name} and {path.name}",
                    handoff_id=handoff_id,
                )
            )
        seen_paths[handoff_id] = path
        try:
            content = path.read_text(encoding="utf-8")
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
                    message=f"Invalid YAML in {path.name}",
                    handoff_id=handoff_id,
                )
            )
            continue
        if metadata.handoff_id != handoff_id:
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.FILENAME_ID_MISMATCH,
                    message=f"{path.name} YAML handoff_id={metadata.handoff_ref}",
                    handoff_id=handoff_id,
                )
            )

    expected = list(range(1, ids[-1] + 1))
    if ids != expected:
        missing = sorted(set(expected) - set(ids))
        issues.append(
            IntegrityIssue(
                code=IntegrityCode.GAP_IN_SEQUENCE,
                message=f"Missing handoff ids: {', '.join(format_handoff_id(i) for i in missing)}",
            )
        )

    if issues:
        return RebuildIndexResult(ok=False, issues=issues)

    return RebuildIndexResult(
        ok=True,
        index=HandoffIndex(
            schema_version=1,
            next_handoff_id=ids[-1] + 1,
            latest_handoff_id=ids[-1],
            count=len(ids),
        ),
    )


def _validate_v1_body(
    content: str,
    metadata: HandoffMetadata,
    *,
    handoff_id: int,
    filename: str,
) -> tuple[list[IntegrityIssue], list[IntegrityIssue]]:
    errors: list[IntegrityIssue] = []
    notices: list[IntegrityIssue] = []

    if _detect_legacy_content(content, filename=filename):
        notices.append(
            IntegrityIssue(
                code=IntegrityCode.LEGACY_FORMAT,
                message=f"{metadata.handoff_ref}: legacy handoff format detected",
                handoff_id=handoff_id,
            )
        )
        if "# CHATGPT HANDOFF" in content:
            notices.append(
                IntegrityIssue(
                    code=IntegrityCode.LEGACY_CHATGPT_HEADER,
                    message=f"{metadata.handoff_ref}: contains legacy CHATGPT HANDOFF header",
                    handoff_id=handoff_id,
                )
            )
        return errors, notices

    if not content.startswith("---"):
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_YAML,
                message=f"{metadata.handoff_ref}: missing YAML front matter",
                handoff_id=handoff_id,
            )
        )

    if metadata.handoff_schema != HANDOFF_SCHEMA_VERSION:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_HANDOFF_SCHEMA,
                message=f"{metadata.handoff_ref}: handoff_schema={metadata.handoff_schema}",
                handoff_id=handoff_id,
            )
        )

    if metadata.artifact_format_version != ARTIFACT_FORMAT_VERSION:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_ARTIFACT_FORMAT,
                message=f"{metadata.handoff_ref}: artifact_format_version={metadata.artifact_format_version}",
                handoff_id=handoff_id,
            )
        )

    yaml_block = FRONT_MATTER_RE.match(content)
    if yaml_block:
        for legacy_field in _yaml_legacy_field_names(yaml_block.group(1)):
            errors.append(
                IntegrityIssue(
                    code=IntegrityCode.LEGACY_YAML_FIELD,
                    message=f"{metadata.handoff_ref}: legacy YAML field '{legacy_field}' is not allowed in v1",
                    handoff_id=handoff_id,
                )
            )

    if not metadata.project_id:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_PROJECT_ID,
                message=f"{metadata.handoff_ref}: project_id is required",
                handoff_id=handoff_id,
            )
        )

    if metadata.handoff_ref != format_handoff_id(handoff_id):
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_HANDOFF_ID,
                message=f"{metadata.handoff_ref}: filename/id mismatch",
                handoff_id=handoff_id,
            )
        )

    if "# CHATGPT HANDOFF" in content:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.LEGACY_CHATGPT_HEADER,
                message=f"{metadata.handoff_ref}: v1 handoff must not use CHATGPT HANDOFF header",
                handoff_id=handoff_id,
            )
        )

    expected_title = f"# {metadata.handoff_ref}"
    if expected_title not in content:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_YAML,
                message=f"{metadata.handoff_ref}: missing title block {expected_title}",
                handoff_id=handoff_id,
            )
        )

    footer_idx = content.rfind("END OF HANDOFF")
    if footer_idx < 0:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_END_FOOTER,
                message=f"{metadata.handoff_ref}: missing END OF HANDOFF footer",
                handoff_id=handoff_id,
            )
        )
    else:
        lines = content.splitlines()
        ref_line = -1
        for idx in range(len(lines) - 1, -1, -1):
            if lines[idx].strip() == metadata.handoff_ref:
                ref_line = idx
                break
        if ref_line < 0 or "END OF HANDOFF" not in content:
            errors.append(
                IntegrityIssue(
                    code=IntegrityCode.MISSING_END_FOOTER,
                    message=f"{metadata.handoff_ref}: invalid END OF HANDOFF footer",
                    handoff_id=handoff_id,
                )
            )
        elif any(line.strip() for line in lines[ref_line + 1 :]):
            errors.append(
                IntegrityIssue(
                    code=IntegrityCode.TRAILING_CONTENT_AFTER_FOOTER,
                    message=f"{metadata.handoff_ref}: content after footer",
                    handoff_id=handoff_id,
                )
            )

    outcome_section = _extract_body_section(content, "## Wynik workflow")
    expected_outcome = status_to_workflow_outcome(metadata.status)
    if outcome_section is None:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_WORKFLOW_OUTCOME,
                message=f"{metadata.handoff_ref}: missing ## Wynik workflow section",
                handoff_id=handoff_id,
            )
        )
    elif outcome_section.splitlines()[0].strip() not in VALID_WORKFLOW_OUTCOMES:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_WORKFLOW_OUTCOME,
                message=f"{metadata.handoff_ref}: invalid workflow outcome '{outcome_section.splitlines()[0].strip()}'",
                handoff_id=handoff_id,
            )
        )
    elif outcome_section.splitlines()[0].strip() != expected_outcome:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_WORKFLOW_OUTCOME,
                message=(
                    f"{metadata.handoff_ref}: workflow outcome mismatch "
                    f"(expected {expected_outcome})"
                ),
                handoff_id=handoff_id,
            )
        )

    next_step = _extract_body_section(content, "## Następny oczekiwany krok")
    if next_step is None:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_NEXT_STEP,
                message=f"{metadata.handoff_ref}: missing ## Następny oczekiwany krok section",
                handoff_id=handoff_id,
            )
        )

    if not metadata.generated_artifacts:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.MISSING_GENERATED_ARTIFACT,
                message=f"{metadata.handoff_ref}: generated_artifacts is empty",
                handoff_id=handoff_id,
            )
        )

    if metadata.handoff_generator not in VALID_HANDOFF_GENERATORS:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.INVALID_HANDOFF_GENERATOR,
                message=f"{metadata.handoff_ref}: invalid handoff_generator={metadata.handoff_generator!r}",
                handoff_id=handoff_id,
            )
        )

    overlap = set(metadata.source_reports) & set(metadata.generated_artifacts)
    overlap -= {"docs/handoff/latest.md"}
    if overlap:
        errors.append(
            IntegrityIssue(
                code=IntegrityCode.SOURCE_GENERATED_OVERLAP,
                message=f"{metadata.handoff_ref}: source_reports overlap generated_artifacts: {sorted(overlap)}",
                handoff_id=handoff_id,
            )
        )

    sources_section = _extract_body_section(content, "## Źródła")
    if sources_section is not None:
        for block in re.split(r"\n###\s+", sources_section):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            description = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if not description or description.lower().strip(".") == "brak":
                source_path = lines[0].strip()
                errors.append(
                    IntegrityIssue(
                        code=IntegrityCode.INVALID_SOURCE_DESCRIPTION,
                        message=f"{metadata.handoff_ref}: invalid source description for {source_path}",
                        handoff_id=handoff_id,
                    )
                )

    return errors, notices


def validate_journal(
    *,
    root: Path | None = None,
    index_override: HandoffIndex | None = None,
) -> ValidationReport:
    issues: list[IntegrityIssue] = []
    legacy_notices: list[IntegrityIssue] = []
    handoff_dir = root / "docs" / "handoff" if root else HANDOFF_DIR
    index_path = handoff_dir / "index.json"
    latest_path = handoff_dir / "latest.md"

    try:
        index = index_override if index_override is not None else load_index(index_path)
    except Exception as exc:
        issues.append(IntegrityIssue(code=IntegrityCode.INVALID_INDEX, message=str(exc)))
        return ValidationReport(valid=False, issues=issues, legacy_notices=legacy_notices)

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
                message=f"latest_handoff_id {format_handoff_id(index.latest_handoff_id)} missing on disk",
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
                    message=f"Duplicate handoff id {format_handoff_id(handoff_id)}",
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
                    message=f"Missing handoff ids: {', '.join(format_handoff_id(i) for i in missing)}",
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

        if _is_legacy_filename(path.name):
            legacy_notices.append(
                IntegrityIssue(
                    code=IntegrityCode.LEGACY_FORMAT,
                    message=f"Legacy filename: {path.name}",
                    handoff_id=handoff_id,
                )
            )

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
                    code=IntegrityCode.INVALID_HANDOFF_ID,
                    message=f"Filename/id mismatch in {path.name}",
                    handoff_id=handoff_id,
                )
            )
        parsed[handoff_id] = metadata

        body_errors, body_notices = _validate_v1_body(
            content,
            metadata,
            handoff_id=handoff_id,
            filename=path.name,
        )
        for item in body_errors:
            issues.append(item)
        for item in body_notices:
            legacy_notices.append(item)

    for handoff_id, metadata in parsed.items():
        is_legacy = any(n.handoff_id == handoff_id for n in legacy_notices)
        if metadata.previous_handoff is not None:
            prev_num = parse_handoff_id_ref(metadata.previous_handoff)
            if prev_num is None or prev_num >= handoff_id:
                target = IntegrityCode.INVALID_PREVIOUS
                bucket = legacy_notices if is_legacy else issues
                bucket.append(
                    IntegrityIssue(
                        code=target,
                        message=f"{metadata.handoff_ref}: invalid previous_handoff",
                        handoff_id=handoff_id,
                    )
                )
            elif prev_num not in parsed:
                bucket = legacy_notices if is_legacy else issues
                bucket.append(
                    IntegrityIssue(
                        code=IntegrityCode.INVALID_PREVIOUS,
                        message=f"{metadata.handoff_ref}: previous_handoff {metadata.previous_handoff} missing",
                        handoff_id=handoff_id,
                    )
                )
        elif handoff_id > 1 and not is_legacy:
            expected_prev = format_handoff_id(handoff_id - 1)
            issues.append(
                IntegrityIssue(
                    code=IntegrityCode.INVALID_PREVIOUS,
                    message=f"{metadata.handoff_ref}: expected previous_handoff {expected_prev}",
                    handoff_id=handoff_id,
                )
            )

        if metadata.parent_handoff is not None:
            parent_num = parse_handoff_id_ref(metadata.parent_handoff)
            if parent_num is None:
                bucket = legacy_notices if is_legacy else issues
                bucket.append(
                    IntegrityIssue(
                        code=IntegrityCode.INVALID_PARENT,
                        message=f"{metadata.handoff_ref}: invalid parent_handoff {metadata.parent_handoff}",
                        handoff_id=handoff_id,
                    )
                )

        repo_root = root or ROOT
        for report_rel in metadata.source_reports:
            if not (repo_root / report_rel).is_file():
                issues.append(
                    IntegrityIssue(
                        code=IntegrityCode.MISSING_SOURCE_REPORT,
                        message=f"{metadata.handoff_ref}: missing source report {report_rel}",
                        handoff_id=handoff_id,
                    )
                )

        if not is_legacy:
            for artifact_rel in metadata.generated_artifacts:
                if not (repo_root / artifact_rel).is_file() and artifact_rel != "docs/handoff/latest.md":
                    issues.append(
                        IntegrityIssue(
                            code=IntegrityCode.MISSING_GENERATED_ARTIFACT,
                            message=f"{metadata.handoff_ref}: missing generated artifact {artifact_rel}",
                            handoff_id=handoff_id,
                        )
                    )

    if index.count > 0:
        if not latest_path.is_file():
            issues.append(IntegrityIssue(code=IntegrityCode.MISSING_LATEST, message="latest.md is missing"))
        elif index.latest_handoff_id is not None:
            latest_handoff = files.get(index.latest_handoff_id)
            if latest_handoff is not None:
                try:
                    if latest_handoff.read_bytes() != latest_path.read_bytes():
                        issues.append(
                            IntegrityIssue(
                                code=IntegrityCode.LATEST_MISMATCH,
                                message=(
                                    f"latest.md is not byte-identical to "
                                    f"{format_handoff_id(index.latest_handoff_id)}.md"
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

    return ValidationReport(valid=not issues, issues=issues, legacy_notices=legacy_notices)


def doctor_journal(*, root: Path | None = None) -> DoctorReport:
    handoff_dir = root / "docs" / "handoff" if root else HANDOFF_DIR
    report = validate_journal(root=root)
    suggestions: list[str] = []
    for issue in report.issues:
        if issue.code == IntegrityCode.INVALID_INDEX:
            suggestions.append("Run: guardian handoff rebuild-index")
        if issue.code == IntegrityCode.HANDOFF_ID_CONFLICT:
            suggestions.append("Resolve HANDOFF_ID_CONFLICT manually or run rebuild-index after cleanup")
        if issue.code in {IntegrityCode.LATEST_MISMATCH, IntegrityCode.MISSING_LATEST}:
            suggestions.append("Run: guardian handoff rebuild-latest")
        if issue.code == IntegrityCode.GAP_IN_SEQUENCE:
            suggestions.append("Inspect missing handoff files manually; rebuild-index will not invent content")

    summary = _build_doctor_summary(handoff_dir=handoff_dir, report=report)
    return DoctorReport(
        issues=report.issues,
        legacy_notices=report.legacy_notices,
        suggestions=sorted(set(suggestions)),
        summary=summary,
    )


def _build_doctor_summary(*, handoff_dir: Path, report: ValidationReport) -> DoctorSummary:
    gaps: list[int] = []
    latest_status = "MISSING"
    try:
        index = load_index(handoff_dir / "index.json")
    except Exception:
        index = HandoffIndex()

    v1_files = scan_v1_handoff_files(handoff_dir)
    ids = sorted(v1_files)
    if ids:
        expected = list(range(1, ids[-1] + 1))
        gaps = sorted(set(expected) - set(ids))

    latest_path = handoff_dir / "latest.md"
    if index.latest_handoff_id is not None and latest_path.is_file():
        source = v1_files.get(index.latest_handoff_id)
        if source is None:
            latest_status = "MISSING_SOURCE"
        else:
            try:
                latest_status = "OK" if source.read_bytes() == latest_path.read_bytes() else "MISMATCH"
            except OSError:
                latest_status = "READ_ERROR"
    elif index.count == 0:
        latest_status = "EMPTY_JOURNAL"

    clipboard_status = "UNKNOWN"
    try:
        import shutil

        if shutil.which("pbpaste") or shutil.which("xclip") or shutil.which("wl-paste"):
            clipboard_status = "AVAILABLE"
        else:
            clipboard_status = "UNAVAILABLE"
    except Exception:
        clipboard_status = "UNKNOWN"

    return DoctorSummary(
        latest_handoff_id=index.latest_handoff_id,
        next_handoff_id=index.next_handoff_id,
        count=index.count,
        gaps=gaps,
        latest_status=latest_status,
        clipboard_status=clipboard_status,
    )
