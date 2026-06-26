from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RecoverState:
    dry_run: bool = True
    assume_yes: bool = False
    remote_host: str = ""
    remote_path: str = ""
    git_branch: str = ""
    git_head: str = ""
    db_ok: bool = False
    api_ok: bool = False
    worker_ok: bool = False
    health_ok: bool = False
    health_body: str = ""
    ksef_ok: bool = False
    aborted: bool = False
    abort_reason: str = ""
    notes: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "assume_yes": self.assume_yes,
            "remote_host": self.remote_host,
            "remote_path": self.remote_path,
            "git_branch": self.git_branch,
            "git_head": self.git_head,
            "db_ok": self.db_ok,
            "api_ok": self.api_ok,
            "worker_ok": self.worker_ok,
            "health_ok": self.health_ok,
            "health_body": self.health_body,
            "ksef_ok": self.ksef_ok,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "notes": list(self.notes),
            "summary": dict(self.summary),
        }
