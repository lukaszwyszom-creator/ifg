"""Testy ksef_token_store — metadata tokenów."""
from __future__ import annotations

from datetime import UTC, datetime

from app.services.ksef_token_store import KEY_REFRESH_VALID, build_token_metadata


def test_build_token_metadata_preserves_refresh_valid_until_on_refresh() -> None:
    """Refresh bez refresh_valid_until nie zeruje istniejącej daty ważności."""
    existing_until = "2026-12-01T10:00:00+00:00"
    existing = {
        "access_token": "old-access",
        "refresh_token": "refresh-tok",
        KEY_REFRESH_VALID: existing_until,
    }

    metadata = build_token_metadata(
        access_token="new-access",
        refresh_token="refresh-tok",
        refresh_valid_until=None,
        existing=existing,
    )

    assert metadata["access_token"] == "new-access"
    assert metadata[KEY_REFRESH_VALID] == existing_until


def test_build_token_metadata_sets_refresh_valid_until_when_provided() -> None:
    until = datetime(2026, 12, 1, 10, 0, tzinfo=UTC)
    metadata = build_token_metadata(
        access_token="access",
        refresh_token="refresh",
        refresh_valid_until=until,
    )
    assert metadata[KEY_REFRESH_VALID] == until.isoformat()


def test_build_token_metadata_null_refresh_valid_without_existing() -> None:
    metadata = build_token_metadata(
        access_token="access",
        refresh_token="refresh",
        refresh_valid_until=None,
    )
    assert metadata[KEY_REFRESH_VALID] is None
