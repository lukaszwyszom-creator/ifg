"""Handler joba sync_purchase_invoices — pobiera faktury zakupowe z KSeF."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError
from app.integrations.ksef.client import KSeFRateLimitDeferredError
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.job_repository import JobRepository
from app.services.ksef_session_service import KSeFSessionService

logger = logging.getLogger(__name__)

_DEFAULT_RATE_LIMIT_DEFER_SECONDS = 120.0


class JobRateLimitDeferredError(Exception):
    """Sync zakupów odroczony — worker ustawia available_at bez sleep."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: float,
        *,
        resume: dict | None = None,
        partial_result: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.resume = resume
        self.partial_result = partial_result


class SyncPurchaseInvoicesJobHandler:
    def __init__(
        self,
        session: Session,
        invoice_repository: InvoiceRepository,
        job_repository: JobRepository,
        ksef_session_service: KSeFSessionService,
    ) -> None:
        self.session = session
        self._invoice_repo = invoice_repository
        self._job_repo = job_repository
        self._ksef_session_service = ksef_session_service

    def handle(self, payload: dict) -> dict:
        from datetime import date

        job_id = payload.get("job_id", "?")
        nip: str = payload["nip"]
        date_from = date.fromisoformat(payload["date_from"])
        date_to = date.fromisoformat(payload["date_to"])
        actor_user_id = payload.get("actor_user_id")

        from uuid import UUID
        actor_id = UUID(actor_user_id) if actor_user_id else None

        logger.info("KSEF_ASYNC_SYNC_WORKER_START job_id=%s nip=%s", job_id, nip)
        ksef_client = self._ksef_session_service.ksef_client
        ksef_client.defer_purchase_rate_limit = True
        try:
            report = self._ksef_session_service.sync_purchase_invoices(
                nip=nip,
                date_from=date_from,
                date_to=date_to,
                actor_user_id=actor_id,
                resume_state=payload.get("resume"),
            )

            counts = {
                "saved": report["created"],
                "received": report["ksef_returned"],
                "skipped_existing": report["skipped_existing"],
                "skipped_parse": report["errors"],
                "rate_limited": report.get("rate_limited", False),
                "warning": report.get("warning"),
            }

            if report.get("rate_limit_deferred"):
                raise JobRateLimitDeferredError(
                    report.get("warning")
                    or f"KSeF rate limit podczas sync zakupów (job_id={job_id})",
                    report.get("retry_after_seconds", _DEFAULT_RATE_LIMIT_DEFER_SECONDS),
                    resume=report.get("resume_state"),
                    partial_result=counts,
                )

            if counts["rate_limited"]:
                raise JobRateLimitDeferredError(
                    f"KSeF rate limit podczas sync zakupów (job_id={job_id})",
                    _DEFAULT_RATE_LIMIT_DEFER_SECONDS,
                )

            logger.info(
                "KSEF_ASYNC_SYNC_WORKER_DONE job_id=%s saved=%s received=%s rate_limited=%s",
                job_id,
                counts["saved"],
                counts["received"],
                counts["rate_limited"],
            )
            return counts
        except JobRateLimitDeferredError:
            raise
        except ExternalServiceError as exc:
            cause = exc.__cause__
            if isinstance(cause, KSeFRateLimitDeferredError):
                raise JobRateLimitDeferredError(
                    str(exc),
                    cause.retry_after_seconds,
                ) from exc
            logger.error(
                "KSEF_ASYNC_SYNC_WORKER_ERROR job_id=%s error=%s",
                job_id,
                exc,
            )
            raise
        except Exception as exc:
            logger.error(
                "KSEF_ASYNC_SYNC_WORKER_ERROR job_id=%s error=%s",
                job_id,
                exc,
            )
            raise
        finally:
            ksef_client.defer_purchase_rate_limit = False
