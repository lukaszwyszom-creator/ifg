from __future__ import annotations

import os
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-123")

from app.api.deps import get_current_user
from app.api.routers.mobile import get_mobile_service as mobile_service_dep
from app.core.security import AuthenticatedUser
from app.main import app
from app.services.mobile_service import MobileService


def _make_actor() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=str(uuid4()), username="tester", role="administrator")


def _mock_mobile_service() -> MagicMock:
    service = MagicMock(spec=MobileService)
    service.get_dashboard.return_value = {
        "period": "2026-05",
        "sales_net": 0,
        "purchase_net": 0,
        "vat_balance": 0,
        "vat_label": "due",
        "debtors_count": 0,
        "debtors_total_due": 0,
        "debtors_overdue_due": 0,
        "creditors_count": 0,
        "creditors_total_due": 0,
        "creditors_overdue_due": 0,
        "unassigned_payments_count": 0,
        "unassigned_payments_total": 0,
        "ksef_new_invoices_count": 0,
        "ksef_last_sync_at": None,
        "ksef_connection_status": "disconnected",
        "notifications_active_count": 0,
        "recent_purchase_invoices": [],
    }
    service.get_notifications.return_value = {"items": []}
    service.get_debtors.return_value = {"items": []}
    service.get_debtor.return_value = {
        "id": uuid4(),
        "name": "Alfa",
        "total_due": 0,
        "overdue_due": 0,
        "invoices_count": 0,
        "overdue_invoices_count": 0,
        "invoices": [],
    }
    service.get_creditors.return_value = {"items": []}
    service.get_creditor.return_value = {
        "id": uuid4(),
        "name": "Beta",
        "total_due": 0,
        "overdue_due": 0,
        "invoices_count": 0,
        "overdue_invoices_count": 0,
        "invoices": [],
    }
    return service


def test_mobile_dashboard_returns_200() -> None:
    actor = _make_actor()
    mobile_service = _mock_mobile_service()

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[mobile_service_dep] = lambda: mobile_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get("/api/v1/mobile/dashboard?period=2026-05")

        assert res.status_code == 200
        body = res.json()
        assert body["period"] == "2026-05"
        assert "sales_net" in body
        mobile_service.get_dashboard.assert_called_once_with(period="2026-05")
    finally:
        patcher.stop()
        app.dependency_overrides.clear()


def test_mobile_notifications_returns_200() -> None:
    actor = _make_actor()
    mobile_service = _mock_mobile_service()

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[mobile_service_dep] = lambda: mobile_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get("/api/v1/mobile/notifications")

        assert res.status_code == 200
        body = res.json()
        assert "items" in body
        mobile_service.get_notifications.assert_called_once_with()
    finally:
        patcher.stop()
        app.dependency_overrides.clear()


def test_mobile_debtors_returns_200() -> None:
    actor = _make_actor()
    mobile_service = _mock_mobile_service()

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[mobile_service_dep] = lambda: mobile_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get("/api/v1/mobile/debtors")

        assert res.status_code == 200
        assert "items" in res.json()
        mobile_service.get_debtors.assert_called_once_with()
    finally:
        patcher.stop()
        app.dependency_overrides.clear()


def test_mobile_debtor_details_returns_200() -> None:
    actor = _make_actor()
    mobile_service = _mock_mobile_service()
    debtor_id = uuid4()

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[mobile_service_dep] = lambda: mobile_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get(f"/api/v1/mobile/debtors/{debtor_id}")

        assert res.status_code == 200
        body = res.json()
        assert "invoices" in body
        mobile_service.get_debtor.assert_called_once_with(debtor_id)
    finally:
        patcher.stop()
        app.dependency_overrides.clear()


def test_mobile_creditors_returns_200() -> None:
    actor = _make_actor()
    mobile_service = _mock_mobile_service()

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[mobile_service_dep] = lambda: mobile_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get("/api/v1/mobile/creditors")

        assert res.status_code == 200
        assert "items" in res.json()
        mobile_service.get_creditors.assert_called_once_with()
    finally:
        patcher.stop()
        app.dependency_overrides.clear()


def test_mobile_creditor_details_returns_200() -> None:
    actor = _make_actor()
    mobile_service = _mock_mobile_service()
    creditor_id = uuid4()

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[mobile_service_dep] = lambda: mobile_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get(f"/api/v1/mobile/creditors/{creditor_id}")

        assert res.status_code == 200
        body = res.json()
        assert "invoices" in body
        mobile_service.get_creditor.assert_called_once_with(creditor_id)
    finally:
        patcher.stop()
        app.dependency_overrides.clear()
