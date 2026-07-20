"""Testy e-maila podsumowującego sesję synchronizacji zakupów KSeF."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]
if not hasattr(SQLiteTypeCompiler, "visit_UUID"):
    SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(36)"  # type: ignore[attr-defined]

from app.domain.enums import KSeFOperationType
from app.integrations.email.smtp_client import SmtpConfig, SmtpSendError
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
    PurchaseSyncNotificationORM,
    TransmissionORM,
    UserORM,
)
from app.persistence.models.purchase_sync_notification import PurchaseSyncNotificationORM as NotifyORM
from app.persistence.repositories.purchase_sync_notification_repository import (
    PurchaseSyncNotificationRepository,
)
from app.services.ksef_purchase_sync_audit import PurchaseSyncAudit
from app.services.purchase_sync_email_notifier import PurchaseSyncEmailNotifier


def _settings_mock(**kwargs):
    defaults = {
        "purchase_sync_notify_enabled": True,
        "purchase_sync_notify_recipients": "ops@ifg.test",
        "purchase_sync_notify_email": None,
        "purchase_sync_notify_max_attempts": 5,
        "smtp_host": "smtp.test",
        "smtp_port": 587,
        "smtp_from": "ifg@test",
        "smtp_user": None,
        "smtp_password": None,
        "smtp_use_tls": True,
    }
    defaults.update(kwargs)
    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _make_audit(*, saved_ids: list[uuid.UUID], saved_count: int | None = None) -> PurchaseSyncAudit:
    audit = PurchaseSyncAudit(
        nip="9670402857",
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 10),
    )
    for idx, inv_id in enumerate(saved_ids):
        audit.record_saved(f"KSEF-REF-{idx}", invoice_id=inv_id)
    if saved_count is not None:
        audit.saved = saved_count
    return audit


def _insert_purchase_invoice(session: Session, *, number: str, gross: str = "123.00") -> uuid.UUID:
    inv_id = uuid.uuid4()
    session.add(
        InvoiceORM(
            id=inv_id,
            status="accepted",
            payment_status="unpaid",
            seller_snapshot_json={"name": "Kontrahent SA", "nip": "1112223344"},
            buyer_snapshot_json={"name": "Nabywca", "nip": "9670402857"},
            totals_json={"total_gross": gross, "total_net": "100.00", "total_vat": "23.00"},
            issue_date=date(2026, 7, 5),
            sale_date=date(2026, 7, 5),
            payment_method="transfer",
            currency="PLN",
            direction="purchase",
            number_local=number,
            ksef_reference_number=f"KSEF-{number}",
        )
    )
    session.flush()
    return inv_id


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
def test_zero_new_invoices_no_enqueue(mock_settings, db_session: Session) -> None:
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[], saved_count=0)
    row = notifier.maybe_enqueue_after_sync(
        correlation_id=uuid.uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    assert row is None


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
def test_enqueue_stores_snapshot(mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/1/2026", gross="100.00")
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    started = datetime(2026, 7, 11, 6, 0, tzinfo=UTC)
    finished = datetime(2026, 7, 11, 6, 5, tzinfo=UTC)
    row = notifier.maybe_enqueue_after_sync(
        correlation_id=uuid.uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=started,
        finished_at=finished,
    )
    db_session.commit()
    assert row is not None
    assert row.invoice_count == 1
    assert row.gross_sum == Decimal("100.00")
    assert row.skipped_duplicates == 0
    assert row.started_at.replace(tzinfo=UTC) == started
    assert row.finished_at.replace(tzinfo=UTC) == finished


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_first_attempt_success(mock_send, mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/OK/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    assert row.status == "SENT"
    assert row.attempt_count == 1
    mock_send.assert_called_once()


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_first_failure_sets_attempt_count(mock_send, mock_settings, db_session: Session) -> None:
    mock_send.side_effect = SmtpSendError("fail")
    inv_id = _insert_purchase_invoice(db_session, number="FV/F1/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    assert row.attempt_count == 1
    assert row.status == "FAILED"
    assert row.next_attempt_at is not None


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_no_retry_before_next_attempt_at(mock_send, mock_settings, db_session: Session) -> None:
    mock_send.side_effect = SmtpSendError("fail")
    inv_id = _insert_purchase_invoice(db_session, number="FV/WAIT/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    row.next_attempt_at = datetime.now(UTC) + timedelta(minutes=30)
    db_session.commit()

    mock_send.reset_mock()
    notifier.process_pending()
    mock_send.assert_not_called()


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_retry_after_next_attempt_at(mock_send, mock_settings, db_session: Session) -> None:
    mock_send.side_effect = [SmtpSendError("fail"), None]
    inv_id = _insert_purchase_invoice(db_session, number="FV/RETRY/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    notifier.process_pending()
    db_session.commit()
    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    assert row.status == "SENT"
    assert mock_send.call_count == 2


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_fifth_failure_is_permanent(mock_send, mock_settings, db_session: Session) -> None:
    mock_send.side_effect = SmtpSendError("fail")
    inv_id = _insert_purchase_invoice(db_session, number="FV/PERM/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()

    for _ in range(5):
        row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()
        notifier.process_pending()
        db_session.commit()

    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    assert row.status == "FAILED_PERMANENT"
    assert row.attempt_count == 5


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_permanent_not_retried(mock_send, mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/NO/2026")
    corr_id = uuid.uuid4()
    repo = PurchaseSyncNotificationRepository(db_session)
    row = NotifyORM(
        id=uuid.uuid4(),
        correlation_id=corr_id,
        status="FAILED_PERMANENT",
        sync_status="SUCCESS",
        new_invoice_ids=[str(inv_id)],
        invoice_count=1,
        gross_sum=Decimal("123.00"),
        recipient_email="ops@ifg.test",
        attempt_count=5,
        max_attempts=5,
    )
    repo.add(row)
    db_session.commit()

    notifier = PurchaseSyncEmailNotifier(db_session, notification_repository=repo)
    notifier.process_pending()
    mock_send.assert_not_called()


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_sent_not_resent(mock_send, mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/SENT/2026")
    corr_id = uuid.uuid4()
    repo = PurchaseSyncNotificationRepository(db_session)
    row = NotifyORM(
        id=uuid.uuid4(),
        correlation_id=corr_id,
        status="SENT",
        sync_status="SUCCESS",
        new_invoice_ids=[str(inv_id)],
        invoice_count=1,
        gross_sum=Decimal("123.00"),
        recipient_email="ops@ifg.test",
        notification_sent_at=datetime.now(UTC),
        attempt_count=1,
        max_attempts=5,
    )
    repo.add(row)
    db_session.commit()

    notifier = PurchaseSyncEmailNotifier(db_session, notification_repository=repo)
    notifier.process_pending()
    mock_send.assert_not_called()


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock(
    purchase_sync_notify_recipients="a@test.com,b@test.com",
))
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_multiple_recipients_csv(mock_send, mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/MULTI/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    assert mock_send.call_args.kwargs["to_addrs"] == ["a@test.com", "b@test.com"]


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock(
    purchase_sync_notify_recipients=None,
    purchase_sync_notify_email="legacy@ifg.test",
))
def test_fallback_legacy_email(mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/LEG/2026")
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    row = notifier.maybe_enqueue_after_sync(
        correlation_id=uuid.uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    assert row is not None
    assert row.recipient_email == "legacy@ifg.test"


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
def test_manual_sync_no_enqueue(mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/MAN/2026")
    audit = _make_audit(saved_ids=[inv_id])
    notifier = PurchaseSyncEmailNotifier(db_session)
    assert notifier.maybe_enqueue_after_sync(
        correlation_id=uuid.uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_MANUAL,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    ) is None


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
def test_incomplete_sync_no_enqueue(mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/INC/2026")
    audit = _make_audit(saved_ids=[inv_id])
    audit.incomplete = True
    notifier = PurchaseSyncEmailNotifier(db_session)
    assert notifier.maybe_enqueue_after_sync(
        correlation_id=uuid.uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    ) is None


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
def test_duplicates_only_no_enqueue(mock_settings, db_session: Session) -> None:
    audit = PurchaseSyncAudit(nip="9670402857", date_from=date(2026, 7, 1), date_to=date(2026, 7, 10))
    audit.record_skipped_existing("KSEF-DUP-1")
    notifier = PurchaseSyncEmailNotifier(db_session)
    assert notifier.maybe_enqueue_after_sync(
        correlation_id=uuid.uuid4(),
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    ) is None


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
def test_same_session_no_second_enqueue(mock_settings, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/DUP/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    started = datetime.now(UTC)
    finished = datetime.now(UTC)
    first = notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=started,
        finished_at=finished,
    )
    second = notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=started,
        finished_at=finished,
    )
    assert first is not None
    assert second is None


def test_claim_excludes_future_next_attempt(db_session: Session) -> None:
    repo = PurchaseSyncNotificationRepository(db_session)
    row = NotifyORM(
        id=uuid.uuid4(),
        correlation_id=uuid.uuid4(),
        status="FAILED",
        sync_status="SUCCESS",
        new_invoice_ids=[],
        recipient_email="ops@ifg.test",
        next_attempt_at=datetime.now(UTC) + timedelta(hours=1),
        attempt_count=1,
        max_attempts=5,
    )
    repo.add(row)
    db_session.commit()
    assert repo.claim_processable(limit=5) == []


@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock())
@patch("app.services.purchase_sync_email_notifier.send_email")
def test_smtp_failure_does_not_affect_sync_status(mock_send, mock_settings, db_session: Session) -> None:
    """Awaria SMTP nie zmienia sync_status w kolejce."""
    mock_send.side_effect = SmtpSendError("smtp down")
    inv_id = _insert_purchase_invoice(db_session, number="FV/SYNC/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()
    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    assert row.sync_status == "SUCCESS"
    assert row.status == "FAILED"


@patch("app.integrations.email.smtp_client.smtplib.SMTP")
@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock(
    smtp_from='IFG [DS 723+] <ds723@ikonastudio.pl>',
    purchase_sync_notify_recipients="lukasz@ikonastudio.pl",
))
def test_notifier_recipient_not_swapped_with_envelope_sender(mock_settings, mock_smtp_cls, db_session: Session) -> None:
    """Regression: production recipient must not become SMTP envelope sender."""
    instance = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = instance

    inv_id = _insert_purchase_invoice(db_session, number="FV/PROD/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    _, kwargs = instance.send_message.call_args
    assert kwargs["from_addr"] == "ds723@ikonastudio.pl"
    assert kwargs["to_addrs"] == ["lukasz@ikonastudio.pl"]
    assert kwargs["from_addr"] not in kwargs["to_addrs"]


@patch("app.integrations.email.smtp_client.smtplib.SMTP")
@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock(
    smtp_from='IFG [DS 723+] <ds723@ikonastudio.pl>',
))
def test_notifier_uses_parsed_envelope_sender(mock_settings, mock_smtp_cls, db_session: Session) -> None:
    instance = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = instance

    inv_id = _insert_purchase_invoice(db_session, number="FV/ENV/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()

    _, kwargs = instance.send_message.call_args
    assert kwargs["from_addr"] == "ds723@ikonastudio.pl"
    message = instance.send_message.call_args.args[0]
    assert message["From"] == '"IFG [DS 723+]" <ds723@ikonastudio.pl>'


@patch("app.integrations.email.smtp_client.smtplib.SMTP")
@patch("app.services.purchase_sync_email_notifier.settings", new_callable=lambda: _settings_mock(
    smtp_from="IFG",
))
def test_notifier_invalid_smtp_from_no_send(mock_settings, mock_smtp_cls, db_session: Session) -> None:
    inv_id = _insert_purchase_invoice(db_session, number="FV/BADFROM/2026")
    corr_id = uuid.uuid4()
    notifier = PurchaseSyncEmailNotifier(db_session)
    audit = _make_audit(saved_ids=[inv_id])
    notifier.maybe_enqueue_after_sync(
        correlation_id=corr_id,
        operation_type=KSeFOperationType.PURCHASE_SYNC_AUTO,
        audit=audit,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.commit()
    notifier.process_pending()
    db_session.commit()
    mock_smtp_cls.assert_not_called()
    row = db_session.execute(select(NotifyORM).where(NotifyORM.correlation_id == corr_id)).scalar_one()
    assert row.status == "FAILED"
