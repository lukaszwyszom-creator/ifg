from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-123")

from app.api.deps import get_current_user, get_ksef_session_service, get_ksef_sync_service
from app.core.security import AuthenticatedUser
from app.main import app
from app.services.ksef_session_service import KSeFSessionService
from app.services.ksef_sync_service import KSeFSyncService


@pytest.fixture()
def actor() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=str(uuid4()), username="tester", role="administrator")


@pytest.fixture()
def mock_ksef_sync_service() -> MagicMock:
    return MagicMock(spec=KSeFSyncService)


@pytest.fixture()
def mock_ksef_session_service() -> MagicMock:
    return MagicMock(spec=KSeFSessionService)


@pytest.fixture()
def client(mock_ksef_sync_service, mock_ksef_session_service, actor) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_ksef_sync_service] = lambda: mock_ksef_sync_service
    app.dependency_overrides[get_ksef_session_service] = lambda: mock_ksef_session_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    patcher.stop()
    app.dependency_overrides.clear()


def _sample_sync_report() -> dict:
    return {
        "status": "ok",
        "date_from": "2026-05-01",
        "date_to": "2026-06-09",
        "subject_type": "subject2",
        "ksef_returned": 4,
        "created": 2,
        "skipped_existing": 2,
        "errors": 0,
        "error_samples": [],
    }


def test_get_ksef_sync_status_returns_last_success_and_error_fields(client, mock_ksef_sync_service):
    now = datetime.now(UTC)
    mock_ksef_sync_service.get_sync_status.return_value = {
        "scope": "purchase_invoices",
        "status": "error",
        "last_success_at": now,
        "last_attempt_at": now,
        "last_error": "KSeF timeout",
        "state_json": {"last_date_to": "2026-05-10"},
    }

    response = client.get("/api/v1/ksef/sync/status")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "purchase_invoices"
    assert body["status"] == "error"
    assert body["last_success_at"] is not None
    assert body["last_error"] == "KSeF timeout"


def test_post_ksef_sync_purchases_without_body_uses_defaults(
    client, mock_ksef_session_service, actor
):
    mock_ksef_session_service.sync_purchase_invoices.return_value = _sample_sync_report()

    response = client.post("/api/v1/ksef/sync/purchases")

    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 2
    assert body["ksef_returned"] == 4
    mock_ksef_session_service.sync_purchase_invoices.assert_called_once_with(
        nip=None,
        date_from=None,
        date_to=None,
        days_back=None,
        force_full=False,
        incremental=False,
        actor_user_id=actor.user_id,
    )


def test_post_ksef_sync_purchases_accepts_legacy_force_field(
    client, mock_ksef_session_service, actor
):
    mock_ksef_session_service.sync_purchase_invoices.return_value = _sample_sync_report()

    response = client.post("/api/v1/ksef/sync/purchases", json={"force": True})

    assert response.status_code == 200
    mock_ksef_session_service.sync_purchase_invoices.assert_called_once_with(
        nip=None,
        date_from=None,
        date_to=None,
        days_back=None,
        force_full=True,
        incremental=False,
        actor_user_id=actor.user_id,
    )


def test_post_ksef_sync_purchases_accepts_force_full_body(
    client, mock_ksef_session_service, actor
):
    mock_ksef_session_service.sync_purchase_invoices.return_value = _sample_sync_report()

    response = client.post(
        "/api/v1/ksef/sync/purchases",
        json={"force_full": False, "incremental": False, "nip": "9670402857"},
    )

    assert response.status_code == 200
    mock_ksef_session_service.sync_purchase_invoices.assert_called_once_with(
        nip="9670402857",
        date_from=None,
        date_to=None,
        days_back=None,
        force_full=False,
        incremental=False,
        actor_user_id=actor.user_id,
    )
