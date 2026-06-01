"""Integracja: wpłata przy tworzeniu faktury sprzedaży."""
from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "initial-payment-test-secret-key!!")
os.environ.setdefault("SELLER_NIP", "1234567890")
os.environ.setdefault("SELLER_NAME", "Test Sp. z o.o.")
os.environ.setdefault("SELLER_STREET", "ul. Testowa")
os.environ.setdefault("SELLER_BUILDING_NO", "1")
os.environ.setdefault("SELLER_POSTAL_CODE", "00-001")
os.environ.setdefault("SELLER_CITY", "Warszawa")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]

from app.core.security import hash_password
from app.main import app
from app.persistence.base import Base
from app.persistence.models import (  # noqa: F401
    BankTransactionORM,
    ContractorORM,
    InvoiceORM,
    PaymentAllocationORM,
    UserORM,
)


@pytest.fixture(scope="module")
def client():
    import app.persistence.db as db_module
    from app.core.config import settings

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)

    orig_engine = db_module.engine
    orig_session_local = db_module.SessionLocal
    orig_admin = settings.initial_admin_username
    db_module.engine = eng
    db_module.SessionLocal = sessionmaker(
        bind=eng, autoflush=False, autocommit=False, expire_on_commit=False
    )
    settings.initial_admin_username = ""

    session = db_module.SessionLocal()
    user_id = uuid.uuid4()
    session.add(
        UserORM(
            id=user_id,
            username="admin",
            password_hash=hash_password("admin123"),
            role="administrator",
            is_active=True,
            created_at=datetime.now(UTC),
        )
    )
    buyer_id = uuid.uuid4()
    session.add(
        ContractorORM(
            id=buyer_id,
            nip="9876543210",
            name="Nabywca Test",
            street="ul. Nabywcy",
            building_no="2",
            postal_code="00-002",
            city="Kraków",
            country="PL",
            source="manual",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    session.commit()
    session.close()

    with TestClient(app, raise_server_exceptions=True) as test_client:
        login = test_client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        test_client._buyer_id = str(buyer_id)  # type: ignore[attr-defined]
        yield test_client

    settings.initial_admin_username = orig_admin
    db_module.engine = orig_engine
    db_module.SessionLocal = orig_session_local
    eng.dispose()


def test_create_invoice_with_amount_paid_persists_allocation(client: TestClient):
    today = date.today().isoformat()
    due = (date.today() + __import__("datetime").timedelta(days=14)).isoformat()

    create_res = client.post(
        "/api/v1/invoices/",
        json={
            "buyer_id": client._buyer_id,
            "issue_date": today,
            "sale_date": today,
            "due_date": due,
            "payment_method": "cash",
            "amount_paid": "500.00",
            "currency": "PLN",
            "items": [
                {
                    "name": "Usługa",
                    "quantity": "1",
                    "unit": "szt.",
                    "unit_price_net": "1000.00",
                    "vat_rate": "23",
                }
            ],
        },
    )
    assert create_res.status_code == 201, create_res.text
    body = create_res.json()
    assert Decimal(body["total_gross"]) == Decimal("1230.00")
    assert Decimal(body["paid_amount"]) == Decimal("500.00")
    assert Decimal(body["remaining_amount"]) == Decimal("730.00")

    get_res = client.get(f"/api/v1/invoices/{body['id']}")
    assert get_res.status_code == 200
    fetched = get_res.json()
    assert Decimal(fetched["paid_amount"]) == Decimal("500.00")
    assert Decimal(fetched["remaining_amount"]) == Decimal("730.00")
    assert Decimal(fetched["form_paid_amount"]) == Decimal("500.00")

    update_res = client.put(
        f"/api/v1/invoices/{body['id']}",
        json={
            "buyer_id": client._buyer_id,
            "issue_date": today,
            "sale_date": today,
            "due_date": due,
            "payment_method": "cash",
            "amount_paid": "800.00",
            "currency": "PLN",
            "items": [
                {
                    "name": "Usługa",
                    "quantity": "1",
                    "unit": "szt.",
                    "unit_price_net": "1000.00",
                    "vat_rate": "23",
                }
            ],
        },
    )
    assert update_res.status_code == 200, update_res.text
    updated = update_res.json()
    assert Decimal(updated["form_paid_amount"]) == Decimal("800.00")
    assert Decimal(updated["paid_amount"]) == Decimal("800.00")
    assert Decimal(updated["remaining_amount"]) == Decimal("430.00")

    update_res_2 = client.put(
        f"/api/v1/invoices/{body['id']}",
        json={
            "buyer_id": client._buyer_id,
            "issue_date": today,
            "sale_date": today,
            "due_date": due,
            "payment_method": "cash",
            "amount_paid": "950.00",
            "currency": "PLN",
            "items": [
                {
                    "name": "Usługa",
                    "quantity": "1",
                    "unit": "szt.",
                    "unit_price_net": "1000.00",
                    "vat_rate": "23",
                }
            ],
        },
    )
    assert update_res_2.status_code == 200, update_res_2.text
    updated_2 = update_res_2.json()
    assert Decimal(updated_2["form_paid_amount"]) == Decimal("950.00")

    get_res_2 = client.get(f"/api/v1/invoices/{body['id']}")
    assert get_res_2.status_code == 200
    assert Decimal(get_res_2.json()["form_paid_amount"]) == Decimal("950.00")
