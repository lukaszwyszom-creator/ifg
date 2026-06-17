"""Regresja: poll_ksef_status znajduje aktywną sesję KSeF."""
from __future__ import annotations

import base64
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]
if not hasattr(SQLiteTypeCompiler, "visit_UUID"):
    SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(36)"  # type: ignore[attr-defined]

from app.domain.enums import InvoiceStatus, TransmissionStatus
from app.domain.models.invoice import Invoice, InvoiceItem
from app.integrations.ksef.client import InvoiceStatusResult
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
from app.persistence.repositories.transmission_repository import TransmissionRepository
from app.services.audit_service import AuditService
from app.persistence.repositories.audit_repository import AuditRepository
from app.services.ksef_session_service import (
    SESSION_ACTIVE,
    KSeFSessionService,
    _normalize_session_nip,
)
from app.worker.job_handlers.poll_ksef_status import PollKSeFStatusJobHandler


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


def _session_service(db: Session) -> KSeFSessionService:
    auth = MagicMock()
    auth.environment = "test"
    return KSeFSessionService(
        session=db,
        auth_provider=auth,
        ksef_client=MagicMock(),
        audit_service=AuditService(session=db, audit_repository=AuditRepository(db)),
    )


def _active_session_orm(nip: str = "9670402857") -> KSeFSessionORM:
    now = datetime.now(UTC)
    return KSeFSessionORM(
        id=uuid.uuid4(),
        nip=nip,
        environment="test",
        auth_method="token",
        session_reference="sess-ref-001",
        token_metadata_json={
            "access_token": "acc-token",
            "symmetric_key": base64.b64encode(b"k" * 32).decode("ascii"),
            "initialization_vector": base64.b64encode(b"i" * 16).decode("ascii"),
        },
        status=SESSION_ACTIVE,
        expires_at=now + timedelta(hours=1),
        created_at=now,
        updated_at=now,
    )


def _sale_invoice(*, seller_nip: str) -> Invoice:
    now = datetime.now(UTC)
    return Invoice(
        id=uuid.uuid4(),
        number_local="FV/1/06/2026",
        status=InvoiceStatus.SENDING,
        issue_date=date(2026, 6, 17),
        sale_date=date(2026, 6, 17),
        currency="PLN",
        seller_snapshot={
            "nip": seller_nip,
            "name": "Sprzedawca",
            "street": "ul. Test",
            "building_no": "1",
            "postal_code": "00-001",
            "city": "Warszawa",
        },
        buyer_snapshot={
            "nip": "1234563218",
            "name": "Nabywca",
            "street": "ul. Nabywcy",
            "building_no": "2",
            "postal_code": "30-001",
            "city": "Krakow",
        },
        items=[
            InvoiceItem(
                name="Towar",
                quantity=Decimal("1"),
                unit="szt.",
                unit_price_net=Decimal("100"),
                vat_rate=Decimal("23"),
                net_total=Decimal("100"),
                vat_total=Decimal("23"),
                gross_total=Decimal("123"),
                sort_order=1,
            )
        ],
        total_net=Decimal("100"),
        total_vat=Decimal("23"),
        total_gross=Decimal("123"),
        created_at=now,
        updated_at=now,
    )


class TestSessionNipNormalization:
    def test_normalize_strips_pl_prefix_and_dashes(self):
        assert _normalize_session_nip("PL9670402857") == "9670402857"
        assert _normalize_session_nip("967-040-28-57") == "9670402857"


class TestActiveSessionLookup:
    def test_get_session_context_finds_active_session(self, db: Session):
        db.add(_active_session_orm())
        db.flush()
        svc = _session_service(db)

        ctx = svc.get_session_context("9670402857")

        assert ctx.access_token == "acc-token"
        assert ctx.session_reference == "sess-ref-001"

    def test_get_session_context_finds_session_with_formatted_nip(self, db: Session):
        db.add(_active_session_orm("9670402857"))
        db.flush()
        svc = _session_service(db)

        ctx = svc.get_session_context("PL9670402857")

        assert ctx.session_reference == "sess-ref-001"


class TestPollHandlerSessionLookup:
    def test_poll_uses_active_session_when_snapshot_nip_formatted(self, db: Session):
        db.add(_active_session_orm("9670402857"))
        db.flush()

        invoice = _sale_invoice(seller_nip="PL9670402857")
        invoice_repo = InvoiceRepository(db)
        saved = invoice_repo.add(invoice)

        transmission = TransmissionORM(
            id=uuid.uuid4(),
            invoice_id=saved.id,
            channel="ksef",
            operation_type="submit",
            status=TransmissionStatus.SUBMITTED.value,
            attempt_no=1,
            idempotency_key="key-1",
            external_reference="EXT-REF-1",
            created_at=datetime.now(UTC),
        )
        db.add(transmission)
        db.flush()

        ksef_svc = _session_service(db)
        ksef_client = MagicMock()
        ksef_client.get_invoice_status.return_value = InvoiceStatusResult(
            processing_code=200,
            processing_description="OK",
            ksef_reference_number="KSEF-123",
            upo_url=None,
        )

        handler = PollKSeFStatusJobHandler(
            session=db,
            transmission_repository=TransmissionRepository(db),
            invoice_repository=invoice_repo,
            job_repository=MagicMock(),
            ksef_client=ksef_client,
            ksef_session_service=ksef_svc,
        )

        handler.handle(
            {
                "transmission_id": str(transmission.id),
                "reference_number": "EXT-REF-1",
            }
        )

        ksef_client.get_invoice_status.assert_called_once()
        assert transmission.status == TransmissionStatus.SUCCESS
