from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowType(str, Enum):
    IMPLEMENTATION = "IMPLEMENTATION"
    REVIEW = "REVIEW"
    DEPLOY = "DEPLOY"
    DIAGNOSTICS = "DIAGNOSTICS"
    RESEARCH = "RESEARCH"


class HandoffStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


VALID_WORKFLOW_TYPES = {item.value for item in WorkflowType}
VALID_HANDOFF_STATUSES = {item.value for item in HandoffStatus}


@dataclass
class HandoffMetadata:
    handoff_id: int
    previous_handoff: int | None
    parent_handoff: int | None
    project: str
    workflow: str
    workflow_type: WorkflowType
    status: HandoffStatus
    created_at: str
    source_reports: list[str] = field(default_factory=list)

    def format_id(self) -> str:
        return f"{self.handoff_id:04d}"

    def filename(self) -> str:
        return f"handoff-{self.format_id()}.md"

    def to_yaml_lines(self) -> list[str]:
        lines = [
            "---",
            "kind: handoff",
            f"handoff_id: {self.format_id()}",
        ]
        if self.previous_handoff is not None:
            lines.append(f"previous_handoff: {self.previous_handoff:04d}")
        else:
            lines.append("previous_handoff: null")
        if self.parent_handoff is not None:
            lines.append(f"parent_handoff: {self.parent_handoff:04d}")
        lines.append(f"project: {self.project}")
        lines.append(f"workflow: {self.workflow}")
        lines.append(f"workflow_type: {self.workflow_type.value}")
        lines.append(f"status: {self.status.value}")
        lines.append(f"created_at: {self.created_at}")
        lines.append("source_reports:")
        for report in self.source_reports:
            lines.append(f"  - {report}")
        lines.append("---")
        return lines

    def render_document(self, body: str) -> str:
        header = "\n".join(self.to_yaml_lines())
        body_text = body.strip()
        if not body_text:
            return header + "\n"
        return header + "\n\n" + body_text + "\n"


@dataclass
class HandoffIndex:
    schema_version: int = 1
    next_handoff_id: int = 1
    latest_handoff_id: int | None = None
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "next_handoff_id": self.next_handoff_id,
            "count": self.count,
        }
        if self.latest_handoff_id is not None:
            payload["latest_handoff_id"] = self.latest_handoff_id
        else:
            payload["latest_handoff_id"] = None
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> HandoffIndex:
        latest = raw.get("latest_handoff_id")
        return cls(
            schema_version=int(raw.get("schema_version", 1)),
            next_handoff_id=int(raw.get("next_handoff_id", 1)),
            latest_handoff_id=int(latest) if latest is not None else None,
            count=int(raw.get("count", 0)),
        )
