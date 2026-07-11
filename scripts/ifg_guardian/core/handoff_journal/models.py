from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

HANDOFF_ID_RE = re.compile(r"^HANDOFF-(\d{4})$")
HANDOFF_SCHEMA_VERSION = 1
ARTIFACT_FORMAT_VERSION = 1
HANDOFF_FOOTER_RULE = "----------------------------------------"
HANDOFF_GENERATOR_GUARDIAN = "guardian"
VALID_HANDOFF_GENERATORS = frozenset({"guardian", "manual", "api", "gui"})

WORKFLOW_OUTCOME_IMPLEMENTED = "IMPLEMENTED"
WORKFLOW_OUTCOME_PARTIAL = "PARTIAL"
WORKFLOW_OUTCOME_FAILED = "FAILED"
VALID_WORKFLOW_OUTCOMES = frozenset(
    {WORKFLOW_OUTCOME_IMPLEMENTED, WORKFLOW_OUTCOME_PARTIAL, WORKFLOW_OUTCOME_FAILED}
)


class WorkflowType(str, Enum):
    IMPLEMENTATION = "IMPLEMENTATION"
    REVIEW = "REVIEW"
    DEPLOY = "DEPLOY"
    DIAGNOSTICS = "DIAGNOSTICS"
    RESEARCH = "RESEARCH"
    ARCHITECTURE = "ARCHITECTURE"
    HOTFIX = "HOTFIX"


class HandoffStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


VALID_WORKFLOW_TYPES = {item.value for item in WorkflowType}
VALID_HANDOFF_STATUSES = {item.value for item in HandoffStatus}


def format_handoff_id(number: int) -> str:
    return f"HANDOFF-{number:04d}"


def parse_handoff_id_ref(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip()
    if not text or text.lower() == "null":
        return None
    match = HANDOFF_ID_RE.match(text)
    if match:
        return int(match.group(1))
    if text.isdigit():
        return int(text)
    return None


def status_to_workflow_outcome(status: HandoffStatus) -> str:
    if status == HandoffStatus.SUCCESS:
        return WORKFLOW_OUTCOME_IMPLEMENTED
    if status == HandoffStatus.PARTIAL:
        return WORKFLOW_OUTCOME_PARTIAL
    return WORKFLOW_OUTCOME_FAILED


def format_created_at_display(created_at: str) -> str:
    text = created_at.strip()
    if not text:
        return "—"
    try:
        if "T" in text:
            normalized = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            return dt.strftime("%Y-%m-%d %H:%M UTC")
        return text
    except ValueError:
        return text


@dataclass
class HandoffMetadata:
    handoff_id: int
    previous_handoff: str | None
    parent_handoff: str | None
    project_id: str
    workflow: str
    workflow_type: WorkflowType
    status: HandoffStatus
    created_at: str
    source_reports: list[str] = field(default_factory=list)
    generated_artifacts: list[str] = field(default_factory=list)
    handoff_schema: int = HANDOFF_SCHEMA_VERSION
    artifact_format_version: int = ARTIFACT_FORMAT_VERSION
    handoff_generator: str = HANDOFF_GENERATOR_GUARDIAN

    @property
    def handoff_ref(self) -> str:
        return format_handoff_id(self.handoff_id)

    def filename(self) -> str:
        return f"{self.handoff_ref}.md"

    def journal_relpath(self) -> str:
        return f"docs/handoff/{self.filename()}"

    def to_yaml_lines(self) -> list[str]:
        lines = [
            "---",
            "kind: handoff",
            f"handoff_schema: {self.handoff_schema}",
            f"handoff_id: {self.handoff_ref}",
            f"previous_handoff: {self.previous_handoff if self.previous_handoff else 'null'}",
            f"parent_handoff: {self.parent_handoff if self.parent_handoff else 'null'}",
            f"project_id: {self.project_id}",
            f"workflow: {self.workflow}",
            f"workflow_type: {self.workflow_type.value}",
            f"status: {self.status.value}",
            f"created_at: {self.created_at}",
            f"artifact_format_version: {self.artifact_format_version}",
            f"handoff_generator: {self.handoff_generator}",
            "source_reports:",
        ]
        for report in self.source_reports:
            lines.append(f"  - {report}")
        lines.append("generated_artifacts:")
        for artifact in self.generated_artifacts:
            lines.append(f"  - {artifact}")
        lines.append("---")
        return lines

    def render_title_block(self) -> str:
        return "\n".join(
            [
                f"# {self.handoff_ref}",
                "",
                "Projekt:",
                self.project_id,
                "",
                "Workflow:",
                self.workflow,
                "",
                "Typ:",
                self.workflow_type.value,
                "",
                "Status:",
                self.status.value,
                "",
                "Data:",
                format_created_at_display(self.created_at),
            ]
        )

    def render_workflow_outcome_block(self) -> str:
        return "\n".join(["## Wynik workflow", "", status_to_workflow_outcome(self.status)])

    def render_footer(self) -> str:
        return "\n".join(
            [
                HANDOFF_FOOTER_RULE,
                "",
                "END OF HANDOFF",
                "",
                self.handoff_ref,
            ]
        )

    def render_document(self, body: str) -> str:
        parts = [
            "\n".join(self.to_yaml_lines()),
            self.render_title_block(),
            self.render_workflow_outcome_block(),
            body.strip(),
            self.render_footer(),
        ]
        return "\n\n".join(part for part in parts if part) + "\n"


@dataclass
class HandoffIndex:
    schema_version: int = 1
    next_handoff_id: int = 1
    latest_handoff_id: int | None = None
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "next_handoff_id": self.next_handoff_id,
            "latest_handoff_id": self.latest_handoff_id,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> HandoffIndex:
        latest = raw.get("latest_handoff_id")
        return cls(
            schema_version=int(raw.get("schema_version", 1)),
            next_handoff_id=int(raw.get("next_handoff_id", 1)),
            latest_handoff_id=int(latest) if latest is not None else None,
            count=int(raw.get("count", 0)),
        )
