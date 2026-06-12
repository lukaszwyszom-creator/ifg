"""Handler joba sync_purchase_invoices — pobiera faktury zakupowe z KSeF."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.persistence.models.background_job import BackgroundJob
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.job_repository import JobRepository
from app.services.ksef_session_service import KSeFSessionService

logger = logging.getLogger(__name__)


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
        try:
            report = self._ksef_session_service.sync_purchase_invoices(
                nip=nip,
                date_from=date_from,
                date_to=date_to,
                actor_user_id=actor_id,
            )

            counts = {
                "saved": report["created"],
                "received": report["ksef_returned"],
                "skipped_existing": report["skipped_existing"],
                "skipped_parse": report["errors"],
                "rate_limited": report.get("rate_limited", False),
                "warning": report.get("warning"),
            }

            logger.info(
                "KSEF_ASYNC_SYNC_WORKER_DONE job_id=%s saved=%s received=%s rate_limited=%s",
                job_id,
                counts["saved"],
                counts["received"],
                counts["rate_limited"],
            )
            return counts
        except Exception as exc:
            logger.error(
                "KSEF_ASYNC_SYNC_WORKER_ERROR job_id=%s error=%s",
                job_id,
                exc,
            )
            raise
