"""Regresja: get_next_sequence_number liczy wyłącznie faktury sale."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]

from app.persistence.base import Base
from app.persistence.models import (  # noqa: F401
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
from app.persistence.repositories.invoice_repository import InvoiceRepository


@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(sqlite_engine):
    connection = sqlite_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    trans.rollback()
    connection.close()


def _invoice_snapshot() -> dict:
    return {
        "nip": "1234567890",
        "name": "Kontrahent",
        "street": "ul. Test",
        "building_no": "1",
        "postal_code": "00-001",
        "city": "Warszawa",
    }


def _add_invoice(
    db: Session,
    *,
    direction: str,
    number_local: str | None,
    issue_date: date = date(2026, 4, 15),
) -> InvoiceORM:
    inv = InvoiceORM(
        id=uuid.uuid4(),
        status="accepted",
        payment_status="unpaid",
        seller_snapshot_json=_invoice_snapshot(),
        buyer_snapshot_json=_invoice_snapshot(),
        totals_json={"total_net": "100", "total_vat": "23", "total_gross": "123"},
        issue_date=issue_date,
        sale_date=issue_date,
        direction=direction,
        number_local=number_local,
        currency="PLN",
    )
    db.add(inv)
    db.flush()
    return inv


def test_get_next_sequence_number_ignores_purchase_invoices(db: Session) -> None:
    repo = InvoiceRepository(db)

    _add_invoice(db, direction="sale", number_local="FV/1/04/2026")
    _add_invoice(db, direction="purchase", number_local="FV/DOSTAWCA/1")
    _add_invoice(db, direction="purchase", number_local="FV/DOSTAWCA/2")

    assert repo.get_next_sequence_number(2026, 4) == 2
