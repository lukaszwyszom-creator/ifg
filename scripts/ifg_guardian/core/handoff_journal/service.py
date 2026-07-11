from __future__ import annotations

import fcntl
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from ifg_guardian.config import ROOT
from ifg_guardian.core.handoff_journal.integrity import (
    DoctorReport,
    ValidationReport,
    doctor_journal,
    rebuild_index_from_files,
    validate_journal,
)
from ifg_guardian.core.handoff_journal.models import HandoffIndex, HandoffMetadata, HandoffStatus, WorkflowType
from ifg_guardian.core.handoff_journal.store import (
    HANDOFF_DIR,
    INDEX_PATH,
    LATEST_PATH,
    ensure_handoff_dir,
    handoff_path,
    load_index,
    save_index,
    write_latest,
    _atomic_write_text,
)

LOCK_PATH = ROOT / ".state" / "handoff_journal.lock"
LOCK_TIMEOUT_SECONDS = 10.0
LOCK_POLL_SECONDS = 0.05


class PublishStep(str, Enum):
    REPORT_SAVED = "report_saved"
    HANDOFF_GENERATED = "handoff_generated"
    HANDOFF_SAVED = "handoff_saved"
    LATEST_UPDATED = "latest_updated"
    INDEX_UPDATED = "index_updated"
    CLIPBOARD_UPDATED = "clipboard_updated"


@dataclass
class PublishResult:
    ok: bool
    handoff_id: int | None = None
    handoff_path: Path | None = None
    completed_steps: list[PublishStep] = field(default_factory=list)
    failed_step: PublishStep | None = None
    message: str = ""

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1


class HandoffJournalLockError(RuntimeError):
    pass


class HandoffJournalLock:
    def __init__(self, *, lock_path: Path = LOCK_PATH, timeout_seconds: float = LOCK_TIMEOUT_SECONDS) -> None:
        self.lock_path = lock_path
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> HandoffJournalLock:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    os.close(self._fd)
                    self._fd = None
                    raise HandoffJournalLockError(
                        f"Handoff journal lock timeout after {self.timeout_seconds}s"
                    ) from exc
                time.sleep(LOCK_POLL_SECONDS)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


class HandoffJournalService:
    def __init__(self, *, root: Path = ROOT) -> None:
        self.root = root
        self.handoff_dir = root / "docs" / "handoff"
        self.index_path = self.handoff_dir / "index.json"
        self.latest_path = self.handoff_dir / "latest.md"

    def initialize(self) -> None:
        ensure_handoff_dir(self.handoff_dir)
        if not self.index_path.is_file():
            save_index(HandoffIndex(), self.index_path)
        if not self.latest_path.is_file():
            write_latest("", self.latest_path)

    def validate(self) -> ValidationReport:
        return validate_journal(root=self.root)

    def doctor(self) -> DoctorReport:
        return doctor_journal(root=self.root)

    def rebuild_index(self) -> HandoffIndex:
        with HandoffJournalLock():
            rebuilt = rebuild_index_from_files(self.handoff_dir, root=self.root)
            save_index(rebuilt, self.index_path)
            return rebuilt

    def rebuild_latest(self) -> Path | None:
        with HandoffJournalLock():
            index = load_index(self.index_path)
            if index.latest_handoff_id is None:
                write_latest("", self.latest_path)
                return self.latest_path
            source = handoff_path(index.latest_handoff_id, self.handoff_dir)
            if not source.is_file():
                raise FileNotFoundError(f"Missing {source.name}")
            content = source.read_bytes()
            ensure_handoff_dir(self.handoff_dir)
            from ifg_guardian.core.handoff_journal.store import _atomic_write_bytes

            _atomic_write_bytes(self.latest_path, content)
            return self.latest_path

    def publish(
        self,
        *,
        metadata: HandoffMetadata,
        body: str,
        report_saved: bool = True,
        copy_to_clipboard: bool = True,
        clipboard_fn=None,
    ) -> PublishResult:
        self.initialize()
        completed: list[PublishStep] = []
        if not report_saved:
            return PublishResult(
                ok=False,
                failed_step=PublishStep.REPORT_SAVED,
                message="Source report was not saved",
            )
        completed.append(PublishStep.REPORT_SAVED)

        document = metadata.render_document(body)
        if not document.strip():
            return PublishResult(
                ok=False,
                completed_steps=completed,
                failed_step=PublishStep.HANDOFF_GENERATED,
                message="Generated handoff body is empty",
            )
        completed.append(PublishStep.HANDOFF_GENERATED)

        try:
            with HandoffJournalLock():
                index = load_index(self.index_path)
                handoff_id = index.next_handoff_id
                if metadata.handoff_id != handoff_id:
                    metadata = HandoffMetadata(
                        handoff_id=handoff_id,
                        previous_handoff=index.latest_handoff_id,
                        parent_handoff=metadata.parent_handoff,
                        project=metadata.project,
                        workflow=metadata.workflow,
                        workflow_type=metadata.workflow_type,
                        status=metadata.status,
                        created_at=metadata.created_at,
                        source_reports=list(metadata.source_reports),
                    )
                document = metadata.render_document(body)
                target = handoff_path(handoff_id, self.handoff_dir)
                _atomic_write_text(target, document)
                completed.append(PublishStep.HANDOFF_SAVED)

                write_latest(document, self.latest_path)
                completed.append(PublishStep.LATEST_UPDATED)

                updated = HandoffIndex(
                    schema_version=1,
                    next_handoff_id=handoff_id + 1,
                    latest_handoff_id=handoff_id,
                    count=index.count + 1,
                )
                save_index(updated, self.index_path)
                completed.append(PublishStep.INDEX_UPDATED)
                allocated_id = handoff_id
        except Exception as exc:
            failed = completed[-1] if completed else PublishStep.HANDOFF_SAVED
            next_failed = {
                PublishStep.REPORT_SAVED: PublishStep.HANDOFF_SAVED,
                PublishStep.HANDOFF_GENERATED: PublishStep.HANDOFF_SAVED,
                PublishStep.HANDOFF_SAVED: PublishStep.LATEST_UPDATED,
                PublishStep.LATEST_UPDATED: PublishStep.INDEX_UPDATED,
            }.get(failed, PublishStep.HANDOFF_SAVED)
            return PublishResult(
                ok=False,
                handoff_id=metadata.handoff_id,
                completed_steps=completed,
                failed_step=next_failed,
                message=str(exc),
            )

        if copy_to_clipboard:
            from ifg_guardian.core.clipboard import copy_text_to_clipboard

            copy_fn = clipboard_fn or copy_text_to_clipboard
            copied, reason = copy_fn(document)
            if not copied:
                return PublishResult(
                    ok=False,
                    handoff_id=allocated_id,
                    handoff_path=target,
                    completed_steps=completed,
                    failed_step=PublishStep.CLIPBOARD_UPDATED,
                    message=reason or "clipboard copy failed",
                )
            completed.append(PublishStep.CLIPBOARD_UPDATED)

        return PublishResult(
            ok=True,
            handoff_id=allocated_id,
            handoff_path=target,
            completed_steps=completed,
            message=f"Published handoff-{allocated_id:04d}.md",
        )


def infer_workflow_type(workflow: str) -> WorkflowType:
    upper = workflow.upper()
    if "DEPLOY" in upper:
        return WorkflowType.DEPLOY
    if "REVIEW" in upper or "EVALUATE" in upper:
        return WorkflowType.REVIEW
    if "DIAG" in upper or "DOCTOR" in upper:
        return WorkflowType.DIAGNOSTICS
    if "RESEARCH" in upper or "FOUNDATION" in upper or "ANALYSIS" in upper:
        return WorkflowType.RESEARCH
    return WorkflowType.IMPLEMENTATION


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
