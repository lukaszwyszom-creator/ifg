"""Testy konfiguracji powiadomień e-mail sync zakupów KSeF."""
from __future__ import annotations

from datetime import UTC, datetime

from app.services.purchase_sync_notify_config import (
    infer_session_slot_label,
    parse_notify_recipients,
    retry_delay_seconds,
)


def test_parse_single_recipient() -> None:
    result = parse_notify_recipients(
        recipients_csv="ops@example.com",
        legacy_email=None,
    )
    assert result == ["ops@example.com"]


def test_parse_multiple_csv_recipients() -> None:
    result = parse_notify_recipients(
        recipients_csv=" a@x.com , b@y.com ,a@x.com,  ",
        legacy_email=None,
    )
    assert result == ["a@x.com", "b@y.com"]


def test_parse_skips_empty_csv_parts() -> None:
    result = parse_notify_recipients(
        recipients_csv=", , invalid, c@z.com,",
        legacy_email=None,
    )
    assert result == ["c@z.com"]


def test_fallback_legacy_email() -> None:
    result = parse_notify_recipients(
        recipients_csv=None,
        legacy_email="legacy@example.com",
    )
    assert result == ["legacy@example.com"]


def test_recipients_preferred_over_legacy() -> None:
    result = parse_notify_recipients(
        recipients_csv="new@example.com",
        legacy_email="legacy@example.com",
    )
    assert result == ["new@example.com"]


def test_retry_delay_schedule() -> None:
    assert retry_delay_seconds(1) == 5 * 60
    assert retry_delay_seconds(2) == 15 * 60
    assert retry_delay_seconds(3) == 30 * 60
    assert retry_delay_seconds(4) == 60 * 60


def test_infer_session_slot_08() -> None:
    finished = datetime(2026, 7, 11, 6, 5, tzinfo=UTC)  # 08:05 Warsaw (CEST +2)
    assert infer_session_slot_label(finished) == "08:00"


def test_infer_session_slot_14() -> None:
    finished = datetime(2026, 7, 11, 12, 10, tzinfo=UTC)  # 14:10 Warsaw
    assert infer_session_slot_label(finished) == "14:00"


def test_infer_session_slot_unknown() -> None:
    finished = datetime(2026, 7, 11, 10, 0, tzinfo=UTC)
    assert infer_session_slot_label(finished) is None
