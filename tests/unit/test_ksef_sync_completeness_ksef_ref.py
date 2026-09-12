"""Regression: sync completeness keyed by ksef_reference_number (not issue_date window)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.domain.enums import KSeFOperationType
from app.services.ksef_purchase_sync_audit import PurchaseSyncAudit
from app.services.ksef_session_service import KSeFSessionService
from app.services.purchase_sync_email_notifier import PurchaseSyncEmailNotifier


def test_metadata_ref_with_earlier_issue_date_is_complete() -> None:
    """Alior-style: metadata in sync window, DB row exists with earlier issue_date."""
    audit = PurchaseSyncAudit(
        nip="9670402857",
        date_from=date(2026, 8, 30),
        date_to=date(2026, 9, 12),
    )
    ref_early = "5223027866-20260831-65EA58C00109-02"
    ref_new = "9512120077-20260912-0805490004A8-9F"
    audit.finalize_metadata([ref_early, ref_new])
    audit.record_skipped_existing(ref_early)
    audit.record_xml_downloaded(ref_new)
    audit.record_saved(ref_new)
    # Completeness set = exact refs present in DB (issue_date irrelevant).
    audit.db_refs_in_window = {ref_early, ref_new}

    audit.emit_missing_comparison()
    assert audit.is_sync_incomplete() is False


def test_metadata_ref_missing_from_db_is_incomplete(caplog) -> None:
    caplog.set_level(logging.INFO)
    audit = PurchaseSyncAudit(
        nip="9670402857",
        date_from=date(2026, 8, 30),
        date_to=date(2026, 9, 12),
    )
    present = "REF-PRESENT"
    missing = "REF-MISSING"
    audit.finalize_metadata([present, missing])
    audit.record_xml_downloaded(present)
    audit.record_saved(present)
    audit.db_refs_in_window = {present}

    audit.emit_missing_comparison()
    assert audit.is_sync_incomplete() is True
    assert any("metadata_not_in_db_count=1" in r.message for r in caplog.records)
    assert any(missing in r.message for r in caplog.records)


def test_finalize_uses_exact_ksef_lookup_not_issue_range() -> None:
    repo = MagicMock()
    repo.list_existing_ksef_purchase_refs.return_value = [
        "5223027866-20260831-65EA58C00109-02",
        "9512120077-20260912-0805490004A8-9F",
    ]
    service = object.__new__(KSeFSessionService)
    service.invoice_repository = repo
    service._journal_service = None

    audit = PurchaseSyncAudit(
        nip="9670402857",
        date_from=date(2026, 8, 30),
        date_to=date(2026, 9, 12),
    )
    early = "5223027866-20260831-65EA58C00109-02"
    new = "9512120077-20260912-0805490004A8-9F"
    audit.finalize_metadata([early, new])
    audit.record_skipped_existing(early)
    audit.record_saved(new)

    service._finalize_purchase_sync_audit(
        audit,
        date_from=date(2026, 8, 30),
        date_to=date(2026, 9, 12),
        nip="9670402857",
    )

    repo.list_existing_ksef_purchase_refs.assert_called_once()
    called_refs = set(repo.list_existing_ksef_purchase_refs.call_args.args[0])
    assert early in called_refs and new in called_refs
    repo.list_ksef_purchase_refs_in_issue_range.assert_not_called()
    assert audit.is_sync_incomplete() is False
    assert audit.final_database_count == 2


def test_enqueue_when_saved_and_complete(monkeypatch) -> None:
    session = MagicMock()
    repo = MagicMock()
    repo.get_by_correlation_id.return_value = None
    notifier = PurchaseSyncEmailNotifier(session, notification_repository=repo)
    monkeypatch.setattr(notifier, "_is_enabled", lambda: True)
    monkeypatch.setattr(notifier, "_resolve_recipients", lambda: ["ops@test"])
    monkeypatch.setattr(notifier, "_compute_gross_sum", lambda ids: 0)

    audit = PurchaseSyncAudit(nip="1", date_from=date(2026, 9, 1), date_to=date(2026, 9, 12))
    inv_id = uuid4()
    audit.saved_invoice_ids = [inv_id]
    audit.saved = 1
    audit.incomplete = False

    row = notifier.maybe_enqueue_after_sync(
        correlation_id=uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    assert row is not None
    repo.add.assert_called_once()


def test_enqueue_blocked_when_real_incomplete(monkeypatch) -> None:
    session = MagicMock()
    repo = MagicMock()
    notifier = PurchaseSyncEmailNotifier(session, notification_repository=repo)
    monkeypatch.setattr(notifier, "_is_enabled", lambda: True)

    audit = PurchaseSyncAudit(nip="1", date_from=date(2026, 9, 1), date_to=date(2026, 9, 12))
    audit.saved_invoice_ids = [uuid4()]
    audit.saved = 1
    audit.incomplete = True

    assert (
        notifier.maybe_enqueue_after_sync(
            correlation_id=uuid4(),
            operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
            audit=audit,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        is None
    )
    repo.add.assert_not_called()


def test_enqueue_blocked_when_saved_zero(monkeypatch) -> None:
    session = MagicMock()
    repo = MagicMock()
    notifier = PurchaseSyncEmailNotifier(session, notification_repository=repo)
    monkeypatch.setattr(notifier, "_is_enabled", lambda: True)

    audit = PurchaseSyncAudit(nip="1", date_from=date(2026, 9, 1), date_to=date(2026, 9, 12))
    audit.saved = 0
    audit.saved_invoice_ids = []
    audit.incomplete = False

    assert (
        notifier.maybe_enqueue_after_sync(
            correlation_id=uuid4(),
            operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
            audit=audit,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        is None
    )
    repo.add.assert_not_called()
