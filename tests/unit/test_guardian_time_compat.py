"""Unit tests for Python 3.8-compatible UTC alias."""
from __future__ import annotations

import sys
from datetime import timezone
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ifg_guardian.core.time_compat import UTC, datetime  # noqa: E402


def test_utc_is_timezone_utc():
    assert UTC is timezone.utc


def test_datetime_now_utc_has_tzinfo():
    stamp = datetime.now(UTC)
    assert stamp.tzinfo is timezone.utc
