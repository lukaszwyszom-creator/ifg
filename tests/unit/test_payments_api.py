from __future__ import annotations

import os
from unittest import mock
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-123")

from app.api.deps import get_current_user, get_payment_service
from app.core.security import AuthenticatedUser
from app.main import app
from app.services.payment_service import PaymentService


def _make_actor() -> AuthenticatedUser:
    return AuthenticatedUser(user_id=str(uuid4()), username="tester", role="administrator")


def test_get_settlements_returns_200_and_payload() -> None:
    actor = _make_actor()
    payment_service = MagicMock(spec=PaymentService)
    payment_service.get_settlement_summary.return_value = {
        "debtors": [
            {
                "invoice_id": str(uuid4()),
                "number_local": "FV/1/04/2026",
                "contractor_name": "Alfa",
                "issue_date": "2026-04-01",
                "gross_total": "1000.00",
                "paid_amount": "100.00",
                "remaining_amount": "900.00",
                "payment_status": "partially_paid",
                "invoice_type": "VAT",
                "side": "sale",
            }
        ],
        "creditors": [],
    }

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_payment_service] = lambda: payment_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get("/api/v1/payments/settlements?side=all&month=2026-04")

        assert res.status_code == 200
        body = res.json()
        assert "debtors" in body
        assert "creditors" in body
        assert body["debtors"][0]["number_local"] == "FV/1/04/2026"

        payment_service.get_settlement_summary.assert_called_once_with(side="all", month="2026-04")
    finally:
        patcher.stop()
        app.dependency_overrides.clear()


def test_get_settlements_rejects_invalid_month() -> None:
    actor = _make_actor()
    payment_service = MagicMock(spec=PaymentService)

    app.dependency_overrides[get_current_user] = lambda: actor
    app.dependency_overrides[get_payment_service] = lambda: payment_service
    patcher = mock.patch("app.services.auth_service.AuthService.bootstrap_initial_admin")
    patcher.start()

    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            res = client.get("/api/v1/payments/settlements?month=2026-13")

        assert res.status_code == 422
    finally:
        patcher.stop()
        app.dependency_overrides.clear()
