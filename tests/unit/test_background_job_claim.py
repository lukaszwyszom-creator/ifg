"""Regresja: worker claim pending sync_purchase_invoices jobs."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]
if not hasattr(SQLiteTypeCompiler, "visit_UUID"):
    SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(36)"  # type: ignore[attr-defined]

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
from app.persistence.models.background_job import (
    claim_and_lock_jobs,
    claimable_jobs,
    count_claimable_jobs,
    count_pending_jobs,
    prepare_job_queue,
)
from app.worker import __main__ as worker_main
from app.worker.job_handlers.sync_purchase_invoices import JobRateLimitDeferredError


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


def _sync_purchase_job(**overrides) -> BackgroundJob:
    job_id = overrides.pop("id", uuid.uuid4())
    defaults = {
        "id": job_id,
        "job_type": "sync_purchase_invoices",
        "payload_json": {
            "job_id": str(job_id),
            "nip": "1234567890",
            "date_from": "2026-05-01",
            "date_to": "2026-05-22",
            "actor_user_id": None,
        },
        "status": "pending",
        "available_at": datetime.now(UTC),
        "attempts": 0,
        "max_attempts": 1,
    }
    defaults.update(overrides)
    return BackgroundJob(**defaults)


def _submit_invoice_job(**overrides) -> BackgroundJob:
    job_id = overrides.pop("id", uuid.uuid4())
    defaults = {
        "id": job_id,
        "job_type": "submit_invoice",
        "payload_json": {
            "transmission_id": str(uuid.uuid4()),
            "invoice_id": str(uuid.uuid4()),
        },
        "status": "pending",
        "available_at": datetime.now(UTC),
        "attempts": 0,
        "max_attempts": 5,
    }
    defaults.update(overrides)
    return BackgroundJob(**defaults)


class TestBackgroundJobClaim:
    def test_pending_sync_purchase_job_is_claimable(self, db: Session):
        job = _sync_purchase_job()
        db.add(job)
        db.flush()

        assert count_pending_jobs(db) == 1
        assert count_claimable_jobs(db) == 1

        claimed = claim_and_lock_jobs(db, batch_size=10)
        assert len(claimed) == 1
        assert claimed[0].id == job.id
        assert claimed[0].status == "processing"
        assert claimed[0].attempts == 1
        assert claimed[0].locked_by == "worker"
        assert claimed[0].locked_at is not None

    def test_future_available_at_is_not_claimed(self, db: Session):
        job = _sync_purchase_job(available_at=datetime.now(UTC) + timedelta(minutes=10))
        db.add(job)
        db.flush()

        assert count_pending_jobs(db) == 1
        assert count_claimable_jobs(db) == 0
        assert claimable_jobs(db, batch_size=10) == []

    def test_exhausted_pending_is_not_claimed(self, db: Session):
        job = _sync_purchase_job(attempts=1, max_attempts=1)
        db.add(job)
        db.flush()

        stats = prepare_job_queue(db)
        assert stats["failed_exhausted_pending"] == 1
        assert count_claimable_jobs(db) == 0
        assert claimable_jobs(db, batch_size=10) == []

    def test_stale_processing_is_released_to_pending(self, db: Session):
        job = _sync_purchase_job(
            status="processing",
            attempts=0,
            locked_at=datetime.now(UTC) - timedelta(hours=2),
            locked_by="worker",
        )
        db.add(job)
        db.flush()

        stats = prepare_job_queue(db)
        assert stats["released_stale_processing"] == 1
        db.refresh(job)
        assert job.status == "pending"
        assert job.locked_at is None
        assert job.locked_by is None


class TestWorkerJobPriority:
    def test_claim_priority_prefers_submit_over_older_sync(self, db: Session):
        sync_job = _sync_purchase_job(
            available_at=datetime.now(UTC) - timedelta(hours=2),
        )
        submit_job = _submit_invoice_job(
            available_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db.add_all([sync_job, submit_job])
        db.flush()

        claimed = worker_main.claim_priority_jobs(db, batch_size=1)
        assert len(claimed) == 1
        assert claimed[0].id == submit_job.id
        assert claimed[0].job_type == "submit_invoice"


class TestWorkerPollRegression:
    def test_process_batch_claims_sync_purchase_and_runs_handler(self, db: Session):
        job = _sync_purchase_job()
        db.add(job)
        db.flush()
        expected_payload = dict(job.payload_json)
        db.commit()

        handler = MagicMock()
        handler.handle.return_value = {
            "saved": 1,
            "received": 1,
            "skipped_existing": 0,
            "skipped_parse": 0,
            "rate_limited": False,
            "warning": None,
        }

        session_factory = sessionmaker(
            bind=db.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

        with (
            patch.object(worker_main, "SessionLocal", session_factory),
            patch.object(worker_main, "_build_ksef_session_service") as build_service,
            patch.object(worker_main, "_build_handlers") as build_handlers,
        ):
            build_service.return_value = (MagicMock(), MagicMock())
            build_handlers.return_value = {"sync_purchase_invoices": handler}

            processed = worker_main._process_batch()

        assert processed == 1
        handler.handle.assert_called_once_with(expected_payload)

        refreshed = db.get(BackgroundJob, job.id)
        assert refreshed is not None
        assert refreshed.status == "done"
        assert refreshed.attempts == 1
        assert refreshed.payload_json.get("result", {}).get("saved") == 1

    def test_sync_rate_limit_defers_job_without_consuming_attempt(self, db: Session):
        job = _sync_purchase_job(max_attempts=5)
        db.add(job)
        db.flush()
        db.commit()

        handler = MagicMock()
        handler.handle.side_effect = JobRateLimitDeferredError(
            "KSeF rate limit",
            retry_after_seconds=120.0,
        )

        session_factory = sessionmaker(
            bind=db.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

        with (
            patch.object(worker_main, "SessionLocal", session_factory),
            patch.object(worker_main, "_build_ksef_session_service") as build_service,
            patch.object(worker_main, "_build_handlers") as build_handlers,
        ):
            build_service.return_value = (MagicMock(), MagicMock())
            build_handlers.return_value = {"sync_purchase_invoices": handler}

            processed = worker_main._process_batch()

        assert processed == 1
        refreshed = db.get(BackgroundJob, job.id)
        assert refreshed is not None
        assert refreshed.status == "pending"
        assert refreshed.attempts == 0
        assert refreshed.available_at is not None

    def test_submit_invoice_runs_immediately_when_sync_is_rate_limited(self, db: Session):
        sync_job = _sync_purchase_job(
            available_at=datetime.now(UTC) - timedelta(hours=2),
        )
        submit_job = _submit_invoice_job(
            available_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db.add_all([sync_job, submit_job])
        db.flush()
        db.commit()

        sync_handler = MagicMock()
        sync_handler.handle.side_effect = JobRateLimitDeferredError(
            "KSeF rate limit",
            retry_after_seconds=300.0,
        )
        submit_handler = MagicMock()
        submit_handler.handle.return_value = None

        session_factory = sessionmaker(
            bind=db.get_bind(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

        with (
            patch.object(worker_main, "SessionLocal", session_factory),
            patch.object(worker_main, "_build_ksef_session_service") as build_service,
            patch.object(worker_main, "_build_handlers") as build_handlers,
        ):
            build_service.return_value = (MagicMock(), MagicMock())
            build_handlers.return_value = {
                "sync_purchase_invoices": sync_handler,
                "submit_invoice": submit_handler,
            }

            worker_main._process_batch()

        submit_handler.handle.assert_called_once()
        sync_handler.handle.assert_not_called()

        deferred_sync = db.get(BackgroundJob, sync_job.id)
        assert deferred_sync is not None
        assert deferred_sync.status == "pending"


class TestKSeFClientDeferRateLimit:
    def test_defer_purchase_rate_limit_raises_without_sleep(self):
        from unittest.mock import MagicMock, patch

        from app.integrations.ksef.client import KSeFClient, KSeFRateLimitDeferredError

        client = KSeFClient(environment="test", timeout_seconds=5)
        client.defer_purchase_rate_limit = True

        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "2041"}
        response.text = "Too Many Requests"

        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.get.return_value = response

        with (
            patch.object(client, "_pace_purchase_request"),
            patch("app.integrations.ksef.client.httpx.Client", return_value=mock_http),
            patch("app.integrations.ksef.client.time.sleep") as sleep_mock,
            pytest.raises(KSeFRateLimitDeferredError) as exc_info,
        ):
            client._get_purchase_invoice_xml("token", "KSEF-REF-001")

        assert exc_info.value.retry_after_seconds == 2041.0
        sleep_mock.assert_not_called()
