from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-123")

from app.api.deps import get_current_user, get_ksef_session_service, get_settings_service
from app.core.security import AuthenticatedUser
from app.main import app
from app.integrations.ksef.client import KSeFClientError
from app.services import ksef_session_service as ksef_status_module
from app.services.ksef_session_service import KSeFSessionService
from app.services.settings_service import SettingsService


def _make_actor() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=str(uuid4()), username="tester", role="administrator")


@pytest.fixture()
def actor() -> AuthenticatedUser:
    return _make_actor()


@pytest.fixture()
def mock_ksef_session_service() -> MagicMock:
    return MagicMock(spec=KSeFSessionService)


@pytest.fixture()
def mock_settings_service() -> MagicMock:
    return MagicMock(spec=SettingsService)


@pytest.fixture()
def client(mock_ksef_session_service, mock_settings_service, actor) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_ksef_session_service] = lambda: mock_ksef_session_service
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    patcher.stop()
    app.dependency_overrides.clear()


class TestKSeFStatusApi:
    def test_returns_connected_status(self, client, mock_ksef_session_service, mock_settings_service):
        expires_at = datetime.now(UTC) + timedelta(hours=2)
        mock_settings_service.get_settings.return_value = {"seller_nip": "1234567890"}
        mock_ksef_session_service.get_connection_status.return_value = {
            "ui_status": "CONNECTED",
            "details": {
                "reason": "UNKNOWN",
                "has_session": True,
                "session_expires_at": expires_at,
                "last_error": None,
            },
        }

        response = client.get("/api/v1/ksef/status")

        assert response.status_code == 200
        body = response.json()
        assert body["ui_status"] == "CONNECTED"
        assert body["details"]["has_session"] is True
        assert body["details"]["session_expires_at"] is not None
        mock_ksef_session_service.get_connection_status.assert_called_once_with("1234567890")

    def test_returns_disconnected_without_seller_nip(self, client, mock_ksef_session_service, mock_settings_service):
        mock_settings_service.get_settings.return_value = {"seller_nip": None}
        mock_ksef_session_service.get_connection_status.return_value = {
            "ui_status": "DISCONNECTED",
            "details": {
                "reason": "NO_SESSION",
                "has_session": False,
                "session_expires_at": None,
                "last_error": None,
            },
        }

        response = client.get("/api/v1/ksef/status")

        assert response.status_code == 200
        assert response.json()["ui_status"] == "DISCONNECTED"
        mock_ksef_session_service.get_connection_status.assert_called_once_with(None)


class TestKSeFConnectionStatusService:
    def setup_method(self):
        ksef_status_module._probe_cache.clear()

    def test_connected_for_active_non_expired_session(self):
        service = KSeFSessionService(
            session=MagicMock(),
            auth_provider=MagicMock(),
            ksef_client=MagicMock(),
            audit_service=MagicMock(),
        )
        orm = MagicMock()
        orm.expires_at = datetime.now(UTC) + timedelta(hours=1)
        service._get_active_db_session = MagicMock(return_value=orm)

        result = service.get_connection_status("1234567890")

        assert result["ui_status"] == "CONNECTED"
        assert result["details"]["has_session"] is True

    def test_disconnected_for_expired_session(self):
        session = MagicMock()
        service = KSeFSessionService(
            session=session,
            auth_provider=MagicMock(),
            ksef_client=MagicMock(),
            audit_service=MagicMock(),
        )
        orm = MagicMock()
        orm.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        service._get_active_db_session = MagicMock(return_value=orm)

        result = service.get_connection_status("1234567890")

        assert result["ui_status"] == "DISCONNECTED"
        assert result["details"]["reason"] == "SESSION_EXPIRED"
        session.flush.assert_called_once()

    def test_disconnected_for_missing_session(self):
        service = KSeFSessionService(
            session=MagicMock(),
            auth_provider=MagicMock(),
            ksef_client=MagicMock(),
            audit_service=MagicMock(),
        )
        service._get_active_db_session = MagicMock(return_value=None)

        result = service.get_connection_status("1234567890")

        assert result["ui_status"] == "DISCONNECTED"
        assert result["details"]["reason"] == "NO_SESSION"

    def test_probe_failure_below_threshold_keeps_connected_status(self):
        service = KSeFSessionService(
            session=MagicMock(),
            auth_provider=MagicMock(),
            ksef_client=MagicMock(),
            audit_service=MagicMock(),
        )
        orm = MagicMock()
        orm.expires_at = datetime.now(UTC) + timedelta(hours=1)
        service.ksef_client.check_connectivity.side_effect = KSeFClientError(
            "KSeF: błąd połączenia",
            transient=True,
        )
        service._get_active_db_session = MagicMock(return_value=orm)

        result = service.get_connection_status("1234567890")

        assert result["ui_status"] == "CONNECTED"
        assert result["details"]["has_session"] is True

    def test_network_error_after_three_probe_failures_returns_error(self):
        service = KSeFSessionService(
            session=MagicMock(),
            auth_provider=MagicMock(),
            ksef_client=MagicMock(),
            audit_service=MagicMock(),
        )
        service.ksef_client.check_connectivity.side_effect = KSeFClientError(
            "KSeF: błąd połączenia",
            transient=True,
        )
        service._get_active_db_session = MagicMock(return_value=MagicMock())

        service.get_connection_status("1234567890")
        service.get_connection_status("1234567890")
        result = service.get_connection_status("1234567890")

        assert result["ui_status"] == "ERROR"
        assert result["details"]["reason"] == "NETWORK_ERROR"

    def test_probe_counter_resets_after_success(self):
        def make_service(side_effect):
            service = KSeFSessionService(
                session=MagicMock(),
                auth_provider=MagicMock(),
                ksef_client=MagicMock(),
                audit_service=MagicMock(),
            )
            orm = MagicMock()
            orm.expires_at = datetime.now(UTC) + timedelta(hours=1)
            service._get_active_db_session = MagicMock(return_value=orm)
            service.ksef_client.check_connectivity.side_effect = side_effect
            service.ksef_client._base_url = "https://api-test.ksef.mf.gov.pl/v2"
            service._probe_cache_key = service.ksef_client._base_url
            return service

        assert make_service(KSeFClientError("KSeF: błąd połączenia", transient=True)).get_connection_status("1234567890")["ui_status"] == "CONNECTED"
        assert make_service(KSeFClientError("KSeF: błąd połączenia", transient=True)).get_connection_status("1234567890")["ui_status"] == "CONNECTED"
        assert make_service(None).get_connection_status("1234567890")["ui_status"] == "CONNECTED"

        result = make_service(KSeFClientError("KSeF: błąd połączenia", transient=True)).get_connection_status("1234567890")

        assert result["ui_status"] == "CONNECTED"