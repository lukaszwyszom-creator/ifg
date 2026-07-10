from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
VALID_KINDS = frozenset(
    {"gwo", "adr", "fd", "rfc", "review", "guardian", "report", "lamus"}
)


@dataclass(frozen=True)
class ReportMetadata:
    kind: str
    project: str
    workflow: str
    handoff: bool
    created_at: str | None = None

    @property
    def sort_epoch(self) -> float | None:
        return parse_created_at_epoch(self.created_at)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_front_matter_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key:
            fields[key] = _unquote(value.strip())
    return fields


def parse_report_metadata(content: str) -> ReportMetadata | None:
    """Parse YAML front matter from a markdown report.

    Returns ``None`` when the document has no front matter block.
    """
    match = FRONT_MATTER_RE.match(content)
    if not match:
        return None
    fields = _parse_front_matter_block(match.group(1))
    if not fields:
        return None

    kind = fields.get("kind", "").strip().lower()
    project = fields.get("project", "").strip()
    workflow = fields.get("workflow", "").strip()
    if not kind or not project or not workflow:
        return None
    if "handoff" not in fields:
        return None

    try:
        handoff = _parse_bool(fields["handoff"])
    except ValueError:
        return None

    created_at = fields.get("created_at")
    if created_at is not None:
        created_at = created_at.strip() or None

    return ReportMetadata(
        kind=kind,
        project=project,
        workflow=workflow,
        handoff=handoff,
        created_at=created_at,
    )


def parse_created_at_epoch(value: str | None) -> float | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if "T" in text:
            normalized = text.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return None


def read_report_metadata(path: Path) -> ReportMetadata | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_report_metadata(content)


def report_sort_epoch(path: Path, *, metadata: ReportMetadata | None = None) -> float:
    meta = metadata if metadata is not None else read_report_metadata(path)
    if meta is not None:
        epoch = meta.sort_epoch
        if epoch is not None:
            return epoch
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def metadata_created_on(value: str | None, *, today: date) -> bool:
    if not value:
        return False
    text = value.strip()
    if not text:
        return False
    if "T" in text:
        try:
            normalized = text.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).date() == today
        except ValueError:
            return False
    return text.startswith(today.isoformat())
