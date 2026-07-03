"""Testy wyliczania okna synchronizacji zakupów KSeF."""
from __future__ import annotations

from datetime import date

from app.services.ksef_purchase_sync_audit import resolve_purchase_sync_window_details


class TestResolvePurchaseSyncWindow:
    def test_explicit_request_range(self) -> None:
        window = resolve_purchase_sync_window_details(
            date(2026, 6, 1),
            date(2026, 7, 3),
            days_back=90,
            force_full=False,
            sync_state_json=None,
        )
        assert window.source == "request"
        assert window.date_from == date(2026, 6, 1)
        assert window.date_to == date(2026, 7, 3)

    def test_default_days_back(self) -> None:
        window = resolve_purchase_sync_window_details(
            None,
            date(2026, 7, 3),
            days_back=90,
            force_full=False,
            sync_state_json=None,
        )
        assert window.source == "default"
        assert window.date_from == date(2026, 4, 4)
        assert window.date_to == date(2026, 7, 3)

    def test_incremental_overlap_crosses_june_july_boundary(self) -> None:
        window = resolve_purchase_sync_window_details(
            None,
            date(2026, 7, 3),
            days_back=90,
            force_full=False,
            sync_state_json={
                "last_date_from": "2026-06-01",
                "last_date_to": "2026-06-30",
                "last_success_at": "2026-07-01T10:00:00Z",
            },
            incremental=True,
            overlap_days=2,
        )
        assert window.source == "incremental"
        assert window.last_date_to == date(2026, 6, 30)
        assert window.date_from == date(2026, 6, 28)
        assert window.date_to == date(2026, 7, 3)
        assert window.date_from <= date(2026, 7, 1) <= window.date_to

    def test_force_full_uses_full_days(self) -> None:
        window = resolve_purchase_sync_window_details(
            None,
            date(2026, 7, 3),
            days_back=90,
            force_full=True,
            sync_state_json={"last_date_to": "2026-06-30"},
            incremental=True,
            full_days=365,
        )
        assert window.source == "force_full"
        assert window.date_from == date(2025, 7, 3)

    def test_resume_source_when_resume_state_present(self) -> None:
        window = resolve_purchase_sync_window_details(
            None,
            date(2026, 7, 3),
            days_back=90,
            force_full=False,
            sync_state_json={"last_date_to": "2026-06-30"},
            incremental=False,
            overlap_days=2,
            resume_state={"current_offset": 50, "invoice_refs": ["A"]},
        )
        assert window.source == "resume"
        assert window.date_from == date(2026, 6, 28)
        assert window.resume_state == {"current_offset": 50, "invoice_refs": ["A"]}
