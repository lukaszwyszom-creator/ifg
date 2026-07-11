"""Append-only JSON Lines audit trail for Guardian production runtime operations."""
from __future__ import annotations

import getpass
import json
import os
import re
import socket
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ifg_guardian.config import DEFAULT_REMOTE_PATH, ROOT, TARGET_BRANCH
from ifg_guardian.core.runtime_store import STATE_DIR, ensure_state_dir

AUDIT_SCHEMA_VERSION = 1
AUDIT_FILE = STATE_DIR / "runtime_audit.jsonl"
AUDIT_MAX_BYTES = 5 * 1024 * 1024
SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|token|api[_-]?key|authorization)\s*[:=]\s*\S+"),
)


@dataclass(frozen=True)
class AuditActor:
    user: str
    hostname: str
    pid: int

    @classmethod
    def current(cls) -> AuditActor:
        return cls(
            user=getpass.getuser(),
            hostname=socket.gethostname(),
            pid=os.getpid(),
        )


def _git_field(command: str) -> str:
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", *command.split()],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def new_operation_id() -> str:
    return str(uuid.uuid4())


def sanitize_text(value: str | None) -> str | None:
    if not value:
        return value
    redacted = value
    # Bearer before generic authorization — avoids partial redaction leaving token tail.
    redacted = re.sub(r"(?i)bearer\s+\S+", "[REDACTED]", redacted)
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _rotate_if_needed(path: Path) -> None:
    if not path.is_file():
        return
    try:
        if path.stat().st_size <= AUDIT_MAX_BYTES:
            return
        rotated = path.with_suffix(path.suffix + ".1")
        if rotated.is_file():
            rotated.unlink()
        path.rename(rotated)
    except OSError:
        pass


def append_audit_record(record: dict[str, Any]) -> Path:
    ensure_state_dir()
    _rotate_if_needed(AUDIT_FILE)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    fd = os.open(str(AUDIT_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        os.close(fd)
        raise
    return AUDIT_FILE


def build_audit_record(
    *,
    operation_id: str,
    event_type: str,
    workflow: str,
    phase: str,
    result: str | None = None,
    reason: str | None = None,
    error_summary: str | None = None,
    target: str = DEFAULT_REMOTE_PATH,
    actor: AuditActor | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    who = actor or AuditActor.current()
    payload: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "timestamp_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "operation_id": operation_id,
        "event_type": event_type,
        "workflow": workflow,
        "phase": phase,
        "actor": who.user,
        "hostname": who.hostname,
        "pid": who.pid,
        "repository": str(ROOT),
        "branch": _git_field("branch --show-current") or TARGET_BRANCH,
        "commit": _git_field("rev-parse --short HEAD"),
        "target": target,
        "reason": sanitize_text(reason),
        "result": result,
        "error_summary": sanitize_text(error_summary),
    }
    if extra:
        payload["extra"] = {k: sanitize_text(v) if isinstance(v, str) else v for k, v in extra.items()}
    return payload


def record_audit_event(**kwargs: Any) -> Path:
    return append_audit_record(build_audit_record(**kwargs))


class RuntimeAuditSession:
    """Context helper for started/completed/failed audit phases."""

    def __init__(
        self,
        *,
        workflow: str,
        event_type: str,
        reason: str | None = None,
        target: str = DEFAULT_REMOTE_PATH,
        operation_id: str | None = None,
    ) -> None:
        self.workflow = workflow
        self.event_type = event_type
        self.reason = reason
        self.target = target
        self.operation_id = operation_id or new_operation_id()

    def started(self, extra: dict[str, Any] | None = None) -> Path:
        return record_audit_event(
            operation_id=self.operation_id,
            event_type=self.event_type,
            workflow=self.workflow,
            phase="started",
            reason=self.reason,
            target=self.target,
            extra=extra,
        )

    def completed(self, result: str = "ok", extra: dict[str, Any] | None = None) -> Path:
        return record_audit_event(
            operation_id=self.operation_id,
            event_type=self.event_type,
            workflow=self.workflow,
            phase="completed",
            result=result,
            reason=self.reason,
            target=self.target,
            extra=extra,
        )

    def failed(self, error_summary: str, extra: dict[str, Any] | None = None) -> Path:
        return record_audit_event(
            operation_id=self.operation_id,
            event_type=self.event_type,
            workflow=self.workflow,
            phase="failed",
            result="error",
            reason=self.reason,
            error_summary=error_summary,
            target=self.target,
            extra=extra,
        )


def read_audit_records(
    *,
    last: int | None = None,
    since_hours: float | None = None,
) -> list[dict[str, Any]]:
    if not AUDIT_FILE.is_file():
        return []
    records: list[dict[str, Any]] = []
    cutoff: datetime | None = None
    if since_hours is not None:
        cutoff = datetime.now(UTC).timestamp() - since_hours * 3600
    try:
        for line in AUDIT_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            if cutoff is not None:
                ts = item.get("timestamp_utc", "")
                try:
                    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if parsed.timestamp() < cutoff:
                        continue
                except ValueError:
                    pass
            records.append(item)
    except OSError:
        return []
    if last is not None and last > 0:
        return records[-last:]
    return records
