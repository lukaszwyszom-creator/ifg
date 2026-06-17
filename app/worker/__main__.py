"""
Worker loop: pobiera joby z PostgreSQL i deleguje do handlerów.

Uruchomienie:
    python -m app.worker
"""
from __future__ import annotations

import logging
import signal
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, or_, select

from app.core.config import settings
from app.integrations.ksef.auth import KSeFAuthProvider
from app.integrations.ksef.client import KSeFClient, RetryConfig
from app.persistence.db import SessionLocal
from app.persistence.models.background_job import BackgroundJob, prepare_job_queue
from app.persistence.models.background_job import _utcnow
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.job_repository import JobRepository
from app.persistence.repositories.transmission_repository import TransmissionRepository
from app.services.audit_service import AuditService
from app.persistence.repositories.audit_repository import AuditRepository
from app.services.ksef_session_service import KSeFSessionService
from app.worker.job_handlers.submit_invoice import SubmitInvoiceJobHandler
from app.worker.job_handlers.poll_ksef_status import PollKSeFStatusJobHandler
from app.worker.job_handlers.sync_purchase_invoices import (
    JobRateLimitDeferredError,
    SyncPurchaseInvoicesJobHandler,
)

logger = logging.getLogger("app.worker")

POLL_INTERVAL_SECONDS = int(getattr(settings, "worker_poll_interval_seconds", 5))
BATCH_SIZE = 1

_JOB_TYPE_PRIORITY = case(
    (BackgroundJob.job_type == "submit_invoice", 0),
    (BackgroundJob.job_type == "poll_ksef_status", 1),
    (BackgroundJob.job_type == "sync_purchase_invoices", 2),
    else_=99,
)

_running = True


def claim_priority_jobs(
    session,
    batch_size: int = BATCH_SIZE,
    *,
    locked_by: str = "worker",
) -> list[BackgroundJob]:
    """Pobiera joby z priorytetem: submit_invoice > poll_ksef_status > sync zakupów."""
    stmt = (
        select(BackgroundJob)
        .where(
            BackgroundJob.status == "pending",
            BackgroundJob.attempts < BackgroundJob.max_attempts,
            or_(
                BackgroundJob.available_at.is_(None),
                BackgroundJob.available_at <= _utcnow(),
            ),
        )
        .order_by(_JOB_TYPE_PRIORITY.asc(), BackgroundJob.available_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    jobs = list(session.execute(stmt).scalars())
    if not jobs:
        return []

    now = datetime.now(UTC)
    for job in jobs:
        job.status = "processing"
        job.locked_at = now
        job.locked_by = locked_by
        job.attempts += 1
    session.flush()
    return jobs


def _build_handlers(session, ksef_client, ksef_session_service):
    transmission_repo = TransmissionRepository(session)
    invoice_repo = InvoiceRepository(session)
    job_repo = JobRepository(session)
    return {
        "submit_invoice": SubmitInvoiceJobHandler(
            session=session,
            transmission_repository=transmission_repo,
            invoice_repository=invoice_repo,
            job_repository=job_repo,
            ksef_client=ksef_client,
            ksef_session_service=ksef_session_service,
        ),
        "poll_ksef_status": PollKSeFStatusJobHandler(
            session=session,
            transmission_repository=transmission_repo,
            invoice_repository=invoice_repo,
            job_repository=job_repo,
            ksef_client=ksef_client,
            ksef_session_service=ksef_session_service,
        ),
        "sync_purchase_invoices": SyncPurchaseInvoicesJobHandler(
            session=session,
            invoice_repository=invoice_repo,
            job_repository=job_repo,
            ksef_session_service=ksef_session_service,
        ),
    }


def _build_ksef_session_service(session):
    ksef_client = KSeFClient(
        environment=settings.ksef_environment,
        timeout_seconds=settings.ksef_timeout_seconds,
        retry_config=RetryConfig(),
    )
    audit_service = AuditService(
        session=session,
        audit_repository=AuditRepository(session),
    )
    return KSeFSessionService(
        session=session,
        auth_provider=KSeFAuthProvider(
            environment=settings.ksef_environment,
            timeout_seconds=settings.ksef_timeout_seconds,
            auth_redeem_timeout_seconds=settings.ksef_auth_redeem_timeout_seconds,
        ),
        ksef_client=ksef_client,
        audit_service=audit_service,
        invoice_repository=InvoiceRepository(session),
    ), ksef_client


def _log_poll_tick(queue_stats: dict[str, int]) -> None:
    pending_count = queue_stats["pending_count"]
    claimable_count = queue_stats["claimable_count"]
    if pending_count == 0 and claimable_count == 0:
        return

    logger.info(
        "WORKER_POLL_TICK pending_count=%s claimable_count=%s processing=%s",
        pending_count,
        claimable_count,
        queue_stats["processing"],
    )
    if pending_count > 0 and claimable_count == 0:
        logger.warning(
            "WORKER_JOB_SKIPPED reason=no_claimable_jobs future_available_at=%s "
            "exhausted_attempts=%s processing=%s",
            queue_stats["future_available_at"],
            queue_stats["exhausted_attempts"],
            queue_stats["processing"],
        )


def _release_job_to_pending(job: BackgroundJob, *, error: str) -> None:
    job.last_error = error[:1024]
    job.status = "pending"
    job.locked_at = None
    job.locked_by = None


def _process_batch() -> int:
    session = SessionLocal()
    try:
        queue_stats = prepare_job_queue(session)
        _log_poll_tick(queue_stats)

        jobs = claim_priority_jobs(session, BATCH_SIZE)
        if not jobs:
            session.commit()
            return 0

        for job in jobs:
            logger.info(
                "WORKER_JOB_CLAIMED job_id=%s job_type=%s attempts=%s",
                job.id,
                job.job_type,
                job.attempts,
            )

        try:
            ksef_session_service, ksef_client = _build_ksef_session_service(session)
            handlers = _build_handlers(session, ksef_client, ksef_session_service)
        except Exception as exc:
            logger.exception("WORKER_JOB_SKIPPED reason=worker_init_failed error=%s", exc)
            for job in jobs:
                job.last_error = f"Inicjalizacja workera nie powiodła się: {exc}"[:1024]
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                else:
                    job.status = "pending"
                job.locked_at = None
                job.locked_by = None
            session.commit()
            return 0

        processed = 0
        for job in jobs:
            handler = handlers.get(job.job_type)
            if handler is None:
                logger.warning(
                    "WORKER_JOB_SKIPPED reason=unknown_job_type job_id=%s job_type=%s",
                    job.id,
                    job.job_type,
                )
                job.status = "failed"
                job.last_error = f"Nieznany job_type: {job.job_type}"
                session.flush()
                session.commit()
                processed += 1
                continue

            try:
                result = handler.handle(job.payload_json)
                if isinstance(result, dict):
                    job.payload_json = {**job.payload_json, "result": result}
                job.status = "done"
                job.locked_at = None
                job.locked_by = None
                logger.info("Job %s (%s) zakończony.", job.id, job.job_type)
            except JobRateLimitDeferredError as exc:
                logger.warning(
                    "WORKER_JOB_DEFERRED job_id=%s job_type=%s retry_after_seconds=%.2f",
                    job.id,
                    job.job_type,
                    exc.retry_after_seconds,
                )
                _release_job_to_pending(job, error=str(exc))
                job.available_at = datetime.now(UTC) + timedelta(
                    seconds=exc.retry_after_seconds
                )
                if job.attempts > 0:
                    job.attempts -= 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("Job %s (%s) BŁĄD: %s", job.id, job.job_type, exc)
                job.last_error = str(exc)[:1024]
                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                else:
                    job.status = "pending"
                    job.locked_at = None
                    job.locked_by = None

            session.flush()
            session.commit()
            processed += 1

        return processed
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _handle_signal(signum, frame):  # noqa: ARG001
    global _running
    logger.info("Sygnał %s — zatrzymuję worker.", signum)
    _running = False


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": "%(message)s"}',
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("Worker startuje. poll_interval=%ss batch=%s", POLL_INTERVAL_SECONDS, BATCH_SIZE)
    while _running:
        try:
            n = _process_batch()
            if n:
                logger.info("Przetworzone joby: %s", n)
        except Exception:  # noqa: BLE001
            logger.exception("Błąd podczas przetwarzania batcha — kontynuuję.")
        if _running:
            time.sleep(POLL_INTERVAL_SECONDS)

    logger.info("Worker zatrzymany.")


if __name__ == "__main__":
    main()
