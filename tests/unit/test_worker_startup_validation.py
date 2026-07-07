"""Walidacja ENV przy starcie workera."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.worker import __main__ as worker_main


def test_main_exits_when_auto_sync_enabled_without_auth_token() -> None:
    with (
        patch.object(worker_main.settings, "ksef_auto_sync_enabled", True),
        patch.object(worker_main.settings, "ksef_auth_token", None),
        patch.object(worker_main, "logging"),
        patch.object(worker_main, "signal"),
        pytest.raises(SystemExit, match="KSEF_AUTH_TOKEN"),
    ):
        worker_main.main()


def test_main_does_not_exit_when_auto_sync_disabled_without_token() -> None:
    with (
        patch.object(worker_main.settings, "ksef_auto_sync_enabled", False),
        patch.object(worker_main.settings, "ksef_auth_token", None),
        patch.object(worker_main, "logging"),
        patch.object(worker_main, "signal"),
        patch.object(worker_main, "_running", False),
    ):
        worker_main.main()
