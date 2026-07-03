"""Audyt logów synchronizacji zakupów KSeF."""
from __future__ import annotations

import logging
from datetime import date

from app.services.ksef_purchase_sync_audit import PurchaseSyncAudit


def test_emit_window_marker(caplog) -> None:
    caplog.set_level(logging.INFO)
    audit = PurchaseSyncAudit(
        nip="1234567890",
        date_from=date(2026, 6, 28),
        date_to=date(2026, 7, 3),
    )
    from app.services.ksef_purchase_sync_audit import SyncWindowResolution

    audit.record_window(
        SyncWindowResolution(
            date_from=date(2026, 6, 28),
            date_to=date(2026, 7, 3),
            source="incremental",
            incremental=True,
            days_back=90,
            overlap_days=2,
            last_date_to=date(2026, 6, 30),
        )
    )
    assert any("KSEF_PURCHASE_SYNC_AUDIT WINDOW" in r.message for r in caplog.records)
    assert any("source=incremental" in r.message for r in caplog.records)


def test_missing_comparison_detects_metadata_not_in_db(caplog) -> None:
    caplog.set_level(logging.INFO)
    audit = PurchaseSyncAudit(
        nip="1234567890",
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 3),
    )
    audit.finalize_metadata(["KSEF-JULY-001", "KSEF-JULY-002"])
    audit.record_xml_downloaded("KSEF-JULY-001")
    audit.record_saved("KSEF-JULY-001")
    audit.db_refs_in_window = {"KSEF-JULY-001"}

    audit.emit_missing_comparison()

    assert audit.is_sync_incomplete() is True
    assert any("KSEF_PURCHASE_SYNC_AUDIT MISSING" in r.message for r in caplog.records)
    assert any("metadata_not_in_db_count=1" in r.message for r in caplog.records)
    assert any("KSEF-JULY-002" in r.message for r in caplog.records)


def test_emit_ref_lists_first_and_last_twenty(caplog) -> None:
    caplog.set_level(logging.INFO)
    audit = PurchaseSyncAudit(
        nip="1234567890",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 7, 3),
    )
    refs = [f"REF-{idx:04d}" for idx in range(55)]
    audit.finalize_metadata(refs)

    audit.emit_ref_lists()

    ref_log = next(r.message for r in caplog.records if "REFS refs_received_from_metadata" in r.message)
    assert "count=55" in ref_log
    assert "REF-0000" in ref_log
    assert "REF-0054" in ref_log


def test_emit_full_report_marks_incomplete_on_pagination_error(caplog) -> None:
    caplog.set_level(logging.INFO)
    audit = PurchaseSyncAudit(
        nip="1234567890",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 7, 3),
    )
    audit.record_pagination_error("hasMore=true but empty page")
    audit.finalize_metadata(["ONLY-50"])
    audit.db_refs_in_window = set()

    audit.emit_full_report()

    assert audit.is_sync_incomplete() is True
    assert any("SYNC_INCOMPLETE" in r.message for r in caplog.records)
    assert any("incomplete=True" in r.message for r in caplog.records)


def test_july_invoice_in_window_when_issue_date_july_first(caplog) -> None:
    """Faktura z issue_date=2026-07-01 musi mieścić się w oknie obejmującym lipiec."""
    from app.services.ksef_purchase_sync_audit import resolve_purchase_sync_window_details

    window = resolve_purchase_sync_window_details(
        None,
        date(2026, 7, 3),
        days_back=90,
        force_full=False,
        sync_state_json={"last_date_to": "2026-06-30"},
        incremental=True,
        overlap_days=2,
    )
    assert window.date_from <= date(2026, 7, 1) <= window.date_to

    audit = PurchaseSyncAudit(
        nip="1234567890",
        date_from=window.date_from,
        date_to=window.date_to,
    )
    audit.finalize_metadata(["KSEF-20260701-0001"])
    audit.record_saved("KSEF-20260701-0001")
    audit.db_refs_in_window = {"KSEF-20260701-0001"}

    caplog.set_level(logging.INFO)
    audit.emit_missing_comparison()
    assert audit.is_sync_incomplete() is False
