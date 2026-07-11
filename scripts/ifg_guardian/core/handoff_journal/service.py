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
    rebuild_index_from_files_strict,
    scan_handoff_files,
    validate_journal,
)
from ifg_guardian.core.handoff_journal.models import (
    HANDOFF_GENERATOR_GUARDIAN,
    HandoffIndex,
    HandoffMetadata,
    HandoffStatus,
    WorkflowType,
    format_handoff_id,
)
from ifg_guardian.core.handoff_journal.store import (
    HANDOFF_DIR,
    HandoffJournalRebuildError,
    HandoffStoreError,
    ensure_handoff_dir,
    handoff_path,
    load_index,
    save_index,
    write_latest,
    _atomic_write_text,
)


class PublishStep(str, Enum):
    REPORT_SAVED = "report_saved"
    HANDOFF_GENERATED = "handoff_generated"
    HANDOFF_SAVED = "handoff_saved"
    LATEST_UPDATED = "latest_updated"
    INDEX_UPDATED = "index_updated"
    CLIPBOARD_UPDATED = "clipboard_updated"
    JOURNAL_VALIDATED = "journal_validated"


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
    def __init__(self, *, lock_path: Path, timeout_seconds: float = 10.0) -> None:
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
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


def default_generated_artifacts(handoff_id: int) -> list[str]:
    handoff_ref = format_handoff_id(handoff_id)
    return [
        f"docs/handoff/{handoff_ref}.md",
        "docs/handoff/latest.md",
    ]


class HandoffJournalService:
    def __init__(self, *, root: Path = ROOT) -> None:
        self.root = root
        self.handoff_dir = root / "docs" / "handoff"
        self.index_path = self.handoff_dir / "index.json"
        self.latest_path = self.handoff_dir / "latest.md"
        self.lock_path = root / ".state" / "handoff_journal.lock"

    def _lock(self) -> HandoffJournalLock:
        return HandoffJournalLock(lock_path=self.lock_path)

    def initialize(self) -> None:
        ensure_handoff_dir(self.handoff_dir)
        journal_files = scan_handoff_files(self.handoff_dir)
        if not self.index_path.is_file():
            if journal_files:
                raise HandoffStoreError(
                    "index.json missing but handoff journal files exist; run: guardian handoff rebuild-index"
                )
            save_index(HandoffIndex(), self.index_path)
        if not self.latest_path.is_file():
            write_latest("", self.latest_path)

    def validate(self) -> ValidationReport:
        return validate_journal(root=self.root)

    def doctor(self) -> DoctorReport:
        return doctor_journal(root=self.root)

    def rebuild_index(self) -> HandoffIndex:
        with self._lock():
            rebuilt = rebuild_index_from_files_strict(self.handoff_dir, root=self.root)
            if not rebuilt.ok:
                raise HandoffJournalRebuildError(rebuilt.issues)
            save_index(rebuilt.index, self.index_path)
            return rebuilt.index

    def rebuild_latest(self) -> Path:
        with self._lock():
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
            if self.latest_path.read_bytes() != content:
                raise HandoffStoreError("rebuild-latest failed: latest.md not byte-identical to source")
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
        try:
            self.initialize()
        except HandoffStoreError as exc:
            return PublishResult(
                ok=False,
                failed_step=PublishStep.REPORT_SAVED,
                message=str(exc),
            )

        completed: list[PublishStep] = []
        if not report_saved:
            return PublishResult(
                ok=False,
                failed_step=PublishStep.REPORT_SAVED,
                message="Source report was not saved",
            )
        completed.append(PublishStep.REPORT_SAVED)

        if not body.strip():
            return PublishResult(
                ok=False,
                completed_steps=completed,
                failed_step=PublishStep.HANDOFF_GENERATED,
                message="Generated handoff body is empty",
            )
        completed.append(PublishStep.HANDOFF_GENERATED)

        allocated_id: int | None = None
        target: Path | None = None
        document = ""
        index_before: HandoffIndex | None = None

        try:
            with self._lock():
                index_before = load_index(self.index_path)
                handoff_id = index_before.next_handoff_id
                target = handoff_path(handoff_id, self.handoff_dir)
                if target.exists():
                    return PublishResult(
                        ok=False,
                        completed_steps=completed,
                        failed_step=PublishStep.HANDOFF_SAVED,
                        message=f"HANDOFF_ID_CONFLICT: {target.name} already exists",
                    )

                generated = default_generated_artifacts(handoff_id)
                committed = HandoffMetadata(
                    handoff_id=handoff_id,
                    previous_handoff=(
                        format_handoff_id(index_before.latest_handoff_id)
                        if index_before.latest_handoff_id
                        else None
                    ),
                    parent_handoff=metadata.parent_handoff,
                    project_id=metadata.project_id,
                    workflow=metadata.workflow,
                    workflow_type=metadata.workflow_type,
                    status=metadata.status,
                    created_at=metadata.created_at,
                    source_reports=list(metadata.source_reports),
                    generated_artifacts=generated,
                    handoff_generator=metadata.handoff_generator or HANDOFF_GENERATOR_GUARDIAN,
                )
                document = committed.render_document(body)
                _atomic_write_text(target, document)
                completed.append(PublishStep.HANDOFF_SAVED)

                write_latest(document, self.latest_path)
                completed.append(PublishStep.LATEST_UPDATED)
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

        assert target is not None and allocated_id is not None and index_before is not None
        if not target.is_file():
            return PublishResult(
                ok=False,
                handoff_id=allocated_id,
                handoff_path=target,
                completed_steps=completed,
                failed_step=PublishStep.HANDOFF_SAVED,
                message=f"Missing handoff file {target.name}",
            )
        if not self.latest_path.is_file():
            return PublishResult(
                ok=False,
                handoff_id=allocated_id,
                handoff_path=target,
                completed_steps=completed,
                failed_step=PublishStep.LATEST_UPDATED,
                message="Missing docs/handoff/latest.md",
            )
        try:
            if target.read_bytes() != self.latest_path.read_bytes():
                return PublishResult(
                    ok=False,
                    handoff_id=allocated_id,
                    handoff_path=target,
                    completed_steps=completed,
                    failed_step=PublishStep.LATEST_UPDATED,
                    message="latest.md is not byte-identical to handoff journal entry",
                )
        except OSError as exc:
            return PublishResult(
                ok=False,
                handoff_id=allocated_id,
                handoff_path=target,
                completed_steps=completed,
                failed_step=PublishStep.LATEST_UPDATED,
                message=str(exc),
            )

        projected = HandoffIndex(
            schema_version=1,
            next_handoff_id=allocated_id + 1,
            latest_handoff_id=allocated_id,
            count=index_before.count + 1,
        )
        validation = validate_journal(root=self.root, index_override=projected)
        if not validation.valid:
            first = validation.issues[0] if validation.issues else None
            message = first.message if first else "handoff journal validation failed"
            return PublishResult(
                ok=False,
                handoff_id=allocated_id,
                handoff_path=target,
                completed_steps=completed,
                failed_step=PublishStep.JOURNAL_VALIDATED,
                message=message,
            )

        try:
            with self._lock():
                current = load_index(self.index_path)
                if current.next_handoff_id != allocated_id:
                    return PublishResult(
                        ok=False,
                        handoff_id=allocated_id,
                        handoff_path=target,
                        completed_steps=completed,
                        failed_step=PublishStep.INDEX_UPDATED,
                        message=(
                            f"HANDOFF_ID_CONFLICT: expected next_handoff_id={allocated_id}, "
                            f"found {current.next_handoff_id}"
                        ),
                    )
                save_index(projected, self.index_path)
                completed.append(PublishStep.INDEX_UPDATED)
        except Exception as exc:
            return PublishResult(
                ok=False,
                handoff_id=allocated_id,
                handoff_path=target,
                completed_steps=completed,
                failed_step=PublishStep.INDEX_UPDATED,
                message=str(exc),
            )

        final_validation = validate_journal(root=self.root)
        if not final_validation.valid:
            try:
                with self._lock():
                    save_index(index_before, self.index_path)
            except Exception:
                pass
            first = final_validation.issues[0] if final_validation.issues else None
            message = first.message if first else "post-index validation failed"
            return PublishResult(
                ok=False,
                handoff_id=allocated_id,
                handoff_path=target,
                completed_steps=completed,
                failed_step=PublishStep.JOURNAL_VALIDATED,
                message=message,
            )

        completed.append(PublishStep.JOURNAL_VALIDATED)
        return PublishResult(
            ok=True,
            handoff_id=allocated_id,
            handoff_path=target,
            completed_steps=completed,
            message=f"Published {format_handoff_id(allocated_id)}.md",
        )


def infer_workflow_type(workflow: str) -> WorkflowType:
    upper = workflow.upper()
    if "HOTFIX" in upper:
        return WorkflowType.HOTFIX
    if "ARCHITECTURE" in upper or "ADR" in upper:
        return WorkflowType.ARCHITECTURE
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
