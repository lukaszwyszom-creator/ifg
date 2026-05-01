"""Test integracyjny dla GET /api/v1/invoices?view=open.

Weryfikuje, że summary.total_receivables i summary.total_payables są liczone
po stronie backendu na podstawie realnych remaining_amount (bez mocków):

  - 2 faktury sale: unpaid 1000 + partially_paid 1000 (alokacja 400 → remaining 600)
  - 1 faktura purchase: unpaid 500
  - oczekiwane: total_receivables == 1600, total_payables == 500
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

# Środowisko musi być ustawione PRZED importem aplikacji.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "open-view-test-secret-key-32-chars!!")
os.environ.setdefault("SELLER_NIP", "1234567890")
os.environ.setdefault("SELLER_NAME", "Open View Sp. z o.o.")
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

# Patch JSONB → JSON dla SQLite (musi być przed importem modeli).
if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]

from app.core.security import hash_password
from app.main import app
from app.persistence.base import Base
from app.persistence.models import (  # noqa: F401 — rejestracja modeli
    AuditLog,
    BackgroundJob,
    BankTransactionORM,
    ContractorORM,
    ContractorOverrideORM,
    IdempotencyKeyORM,
    InvoiceItemORM,
    InvoiceORM,
    KSeFSessionORM,
    PaymentAllocationORM,
    TransmissionORM,
    UserORM,
)


@pytest.fixture(scope="module")
def engine():
    import app.persistence.db as db_module

    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(eng)

    orig_engine = db_module.engine
    orig_session_local = db_module.SessionLocal
    db_module.engine = eng
    db_module.SessionLocal = sessionmaker(
        bind=eng, autoflush=False, autocommit=False, expire_on_commit=False
    )
    try:
        yield eng
    finally:
        db_module.engine = orig_engine
        db_module.SessionLocal = orig_session_local
        eng.dispose()


@pytest.fixture(scope="module")
def db_session(engine):
    import app.persistence.db as db_module

    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="module")
def client(engine):
    from app.core.config import settings

    # Wyłączamy bootstrap admina aby uniknąć kolizji z seedem testu.
    orig = {
        "initial_admin_username": settings.initial_admin_username,
        "initial_admin_password": settings.initial_admin_password,
    }
    object.__setattr__(settings, "initial_admin_username", None)
    object.__setattr__(settings, "initial_admin_password", None)
    try:
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        for k, v in orig.items():
            object.__setattr__(settings, k, v)


def _make_invoice(
    *,
    direction: str,
    payment_status: str,
    total_gross: Decimal,
    number_local: str,
    issue_date: date,
    due_date: date | None,
    created_by: uuid.UUID,
) -> InvoiceORM:
    total_net = (total_gross / Decimal("1.23")).quantize(Decimal("0.01"))
    total_vat = (total_gross - total_net).quantize(Decimal("0.01"))
    return InvoiceORM(
        id=uuid.uuid4(),
        number_local=number_local,
        status="ready_for_submission",
        payment_status=payment_status,
        seller_snapshot_json={"nip": "1234567890", "name": "Sprzedawca"},
        buyer_snapshot_json={"nip": "9876543210", "name": "Nabywca"},
        totals_json={
            "total_net": str(total_net),
            "total_vat": str(total_vat),
            "total_gross": str(total_gross),
        },
        issue_date=issue_date,
        sale_date=issue_date,
        due_date=due_date,
        currency="PLN",
        direction=direction,
        created_by=created_by,
    )


@pytest.fixture(scope="module")
def seeded(db_session, client):
    """Seed: admin + kontrahent + 5 faktur + 1 alokacja częściowa."""
    admin = UserORM(
        username="open_view_admin",
        password_hash=hash_password("Admin1234!"),
        role="administrator",
        is_active=True,
    )
    buyer = ContractorORM(
        nip="9876543210",
        name="Nabywca Otwartych",
        city="Warszawa",
        source="manual",
    )
    db_session.add_all([admin, buyer])
    db_session.commit()
    db_session.refresh(admin)

    today = date.today()

    sale_unpaid = _make_invoice(
        direction="sale",
        payment_status="unpaid",
        total_gross=Decimal("1000.00"),
        number_local="FV/OPEN/1",
        issue_date=today,
        due_date=today - timedelta(days=10),
        created_by=admin.id,
    )
    sale_partial = _make_invoice(
        direction="sale",
        payment_status="partially_paid",
        total_gross=Decimal("1000.00"),
        number_local="FV/OPEN/2",
        issue_date=today,
        due_date=today - timedelta(days=45),
        created_by=admin.id,
    )
    purchase_unpaid = _make_invoice(
        direction="purchase",
        payment_status="unpaid",
        total_gross=Decimal("500.00"),
        number_local="FZ/OPEN/1",
        issue_date=today,
        due_date=today - timedelta(days=90),
        created_by=admin.id,
    )
    sale_due_today = _make_invoice(
        direction="sale",
        payment_status="unpaid",
        total_gross=Decimal("200.00"),
        number_local="FV/OPEN/3",
        issue_date=today,
        due_date=today,
        created_by=admin.id,
    )
    purchase_no_due = _make_invoice(
        direction="purchase",
        payment_status="unpaid",
        total_gross=Decimal("300.00"),
        number_local="FZ/OPEN/2",
        issue_date=today,
        due_date=None,
        created_by=admin.id,
    )

    # Pojedynczy item per faktura (wymaga go relacja, choć agregaty czytają totals_json).
    items = [
        InvoiceItemORM(
            invoice_id=sale_unpaid.id, name="Item",
            quantity=Decimal("1"), unit="szt.",
            unit_price_net=Decimal("813.01"), vat_rate=Decimal("23"),
            net_amount=Decimal("813.01"), vat_amount=Decimal("186.99"),
            gross_amount=Decimal("1000.00"), sort_order=1,
        ),
        InvoiceItemORM(
            invoice_id=sale_partial.id, name="Item",
            quantity=Decimal("1"), unit="szt.",
            unit_price_net=Decimal("813.01"), vat_rate=Decimal("23"),
            net_amount=Decimal("813.01"), vat_amount=Decimal("186.99"),
            gross_amount=Decimal("1000.00"), sort_order=1,
        ),
        InvoiceItemORM(
            invoice_id=purchase_unpaid.id, name="Item",
            quantity=Decimal("1"), unit="szt.",
            unit_price_net=Decimal("406.50"), vat_rate=Decimal("23"),
            net_amount=Decimal("406.50"), vat_amount=Decimal("93.50"),
            gross_amount=Decimal("500.00"), sort_order=1,
        ),
        InvoiceItemORM(
            invoice_id=sale_due_today.id, name="Item",
            quantity=Decimal("1"), unit="szt.",
            unit_price_net=Decimal("162.60"), vat_rate=Decimal("23"),
            net_amount=Decimal("162.60"), vat_amount=Decimal("37.40"),
            gross_amount=Decimal("200.00"), sort_order=1,
        ),
        InvoiceItemORM(
            invoice_id=purchase_no_due.id, name="Item",
            quantity=Decimal("1"), unit="szt.",
            unit_price_net=Decimal("243.90"), vat_rate=Decimal("23"),
            net_amount=Decimal("243.90"), vat_amount=Decimal("56.10"),
            gross_amount=Decimal("300.00"), sort_order=1,
        ),
    ]

    # Bank transaction + alokacja 400 PLN dla sale_partial → remaining = 600.
    bank_tx = BankTransactionORM(
        id=uuid.uuid4(),
        external_id="OPEN-VIEW-TX-1",
        transaction_date=today,
        amount=Decimal("400.00"),
        currency="PLN",
        match_status="partial",
        remaining_amount=Decimal("0.00"),
    )
    db_session.add_all(
        [
            sale_unpaid,
            sale_partial,
            purchase_unpaid,
            sale_due_today,
            purchase_no_due,
            *items,
            bank_tx,
        ]
    )
    db_session.flush()

    allocation = PaymentAllocationORM(
        id=uuid.uuid4(),
        transaction_id=bank_tx.id,
        invoice_id=sale_partial.id,
        allocated_amount=Decimal("400.00"),
        match_method="manual",
        is_reversed=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(allocation)
    db_session.commit()

    # Login → token.
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "open_view_admin", "password": "Admin1234!"},
    )
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}}


def test_open_view_summary_aggregates_receivables_and_payables(client, seeded):
    res = client.get("/api/v1/invoices/?view=open", headers=seeded["headers"])
    assert res.status_code == 200, res.text
    data = res.json()

    # W widoku 'open' summary nie może być None.
    assert data["summary"] is not None
    receivables = data["summary"]["total_receivables"]
    payables = data["summary"]["total_payables"]
    overdue_0_30 = data["summary"]["overdue_0_30"]
    overdue_30_60 = data["summary"]["overdue_30_60"]
    overdue_60_plus = data["summary"]["overdue_60_plus"]

    # Decimal w JSON ma pozostać stringiem, nie floatem.
    assert isinstance(receivables, str)
    assert isinstance(payables, str)
    assert isinstance(overdue_0_30, str)
    assert isinstance(overdue_30_60, str)
    assert isinstance(overdue_60_plus, str)
    assert not isinstance(receivables, float)
    assert not isinstance(payables, float)
    assert not isinstance(overdue_0_30, float)
    assert not isinstance(overdue_30_60, float)
    assert not isinstance(overdue_60_plus, float)

    assert receivables == "1800.00"
    assert payables == "800.00"
    # Aging: 10 dni -> 0_30, 45 dni -> 30_60, 90 dni -> 60_plus,
    # 0 dni oraz due_date=None nie trafiają do żadnej kategorii.
    assert overdue_0_30 == "1000.00"
    assert overdue_30_60 == "600.00"
    assert overdue_60_plus == "500.00"
    # Brak podwójnego liczenia między bucketami.
    assert (
        Decimal(overdue_0_30) + Decimal(overdue_30_60) + Decimal(overdue_60_plus)
        == Decimal("2100.00")
    )

    # Wszystkie 5 faktur powinno być widocznych w widoku 'open'.
    assert data["total"] == 5
    remaining_by_number = {
        item["number_local"]: Decimal(item["remaining_amount"])
        for item in data["items"]
    }
    assert remaining_by_number["FV/OPEN/1"] == Decimal("1000.00")
    assert remaining_by_number["FV/OPEN/2"] == Decimal("600.00")
    assert remaining_by_number["FZ/OPEN/1"] == Decimal("500.00")
    assert remaining_by_number["FV/OPEN/3"] == Decimal("200.00")
    assert remaining_by_number["FZ/OPEN/2"] == Decimal("300.00")
