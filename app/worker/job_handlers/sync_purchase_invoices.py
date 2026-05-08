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

        nip: str = payload["nip"]
        date_from = date.fromisoformat(payload["date_from"])
        date_to = date.fromisoformat(payload["date_to"])
        actor_user_id = payload.get("actor_user_id")

        from uuid import UUID
        actor_id = UUID(actor_user_id) if actor_user_id else None

        counts = self._ksef_session_service.sync_received_invoices(
            nip=nip,
            date_from=date_from,
            date_to=date_to,
            actor_user_id=actor_id,
        )

        logger.info(
            "sync_purchase_invoices job %s done: %s",
            payload.get("job_id", "?"),
            counts,
        )
        return counts
