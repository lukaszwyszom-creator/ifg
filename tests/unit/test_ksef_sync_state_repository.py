from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.persistence.repositories.ksef_sync_state_repository import KSeFSyncStateRepository


def test_get_or_create_creates_state_when_missing() -> None:
    session = MagicMock()
    session.execute.return_value.scalar_one_or_none.return_value = None

    repo = KSeFSyncStateRepository(session)
    state = repo.get_or_create("purchase_invoices")

    assert state.scope == "purchase_invoices"
    assert state.status == "idle"
    session.add.assert_called_once()
    session.flush.assert_called_once()


def test_get_or_create_returns_existing_state() -> None:
    session = MagicMock()
    existing = SimpleNamespace(scope="purchase_invoices", status="success")
    session.execute.return_value.scalar_one_or_none.return_value = existing

    repo = KSeFSyncStateRepository(session)
    state = repo.get_or_create("purchase_invoices")

    assert state is existing
    session.add.assert_not_called()


def test_mark_running_success_error_update_status_fields() -> None:
    session = MagicMock()
    state = SimpleNamespace(
        scope="purchase_invoices",
        status="idle",
        last_success_at=None,
        last_attempt_at=None,
        last_error="old",
        state_json=None,
    )

    repo = KSeFSyncStateRepository(session)
    repo.get_or_create = MagicMock(return_value=state)

    running = repo.mark_running("purchase_invoices")
    assert running.status == "running"
    assert running.last_attempt_at is not None
    assert running.last_error is None

    success = repo.mark_success("purchase_invoices", state_json={"cursor": "ok"})
    assert success.status == "success"
    assert success.last_attempt_at is not None
    assert success.last_success_at is not None
    assert success.last_error is None
    assert success.state_json == {"cursor": "ok"}

    errored = repo.mark_error("purchase_invoices", "boom")
    assert errored.status == "error"
    assert errored.last_attempt_at is not None
    assert errored.last_error == "boom"
