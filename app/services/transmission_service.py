from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.domain.enums import InvoiceStatus, TransmissionStatus
from app.domain.exceptions import (
    InvalidInvoiceError,
    InvalidStatusTransitionError,
    KSeFNotConnectedError,
    NoKSeFSessionError,
)
from app.integrations.ksef.mapper import KSeFMapper
from app.persistence.models.background_job import BackgroundJob
from app.persistence.models.transmission import TransmissionORM
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.job_repository import JobRepository
from app.persistence.repositories.transmission_repository import TransmissionRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (
    TransmissionStatus.QUEUED,
    TransmissionStatus.PROCESSING,
    TransmissionStatus.SUBMITTED,
    TransmissionStatus.WAITING_STATUS,
)
_RETRYABLE_STATUSES = (TransmissionStatus.FAILED_RETRYABLE, TransmissionStatus.FAILED_TEMPORARY)
_IDEMPOTENT_REUSE_STATUSES = (
    TransmissionStatus.QUEUED,
    TransmissionStatus.PROCESSING,
    TransmissionStatus.SUBMITTED,
    TransmissionStatus.WAITING_STATUS,
    TransmissionStatus.SUCCESS,
)

MAX_RETRY_ATTEMPTS = 5


class TransmissionService:
    def __init__(
        self,
        session: Session,
        transmission_repository: TransmissionRepository,
        invoice_repository: InvoiceRepository,
        job_repository: JobRepository,
        audit_service: AuditService,
        ksef_session_service=None,
    ) -> None:
        self.session = session
        self._transmission_repo = transmission_repository
        self._invoice_repo = invoice_repository
        self._job_repo = job_repository
        self._audit_service = audit_service
        self._ksef_session_service = ksef_session_service

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_idempotency_key(invoice) -> str:
        xml_bytes = KSeFMapper.invoice_to_xml(invoice)
        return KSeFMapper.xml_content_hash(xml_bytes)

    def _try_reuse_idempotent_transmission(self, invoice, invoice_id: UUID):
        idempotency_key = self._build_idempotency_key(invoice)
        existing = self._transmission_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None and existing.status in _IDEMPOTENT_REUSE_STATUSES:
            logger.info(
                "submit_invoice: reuse transmission %s for invoice %s with idempotency key %s",
                existing.id,
                invoice_id,
                idempotency_key,
            )
            return existing
        return None

    def _try_reuse_by_idempotency_key(self, invoice_id: UUID, idempotency_key: str):
        existing = self._transmission_repo.get_by_idempotency_key(idempotency_key)
        if existing is not None and existing.status in _IDEMPOTENT_REUSE_STATUSES:
            logger.info(
                "submit_invoice: reuse transmission %s for invoice %s with idempotency key %s",
                existing.id,
                invoice_id,
                idempotency_key,
            )
            return existing
        return None

    def _ensure_invoice_can_be_submitted(self, invoice) -> None:
        if not invoice.can_transition_to(InvoiceStatus.SENDING):
            raise InvalidStatusTransitionError(
                f"Faktura musi mieć status 'ready_for_submission' "
                f"(aktualnie: '{invoice.status.value}')."
            )

    def _ensure_no_active_transmission(self, invoice_id: UUID) -> None:
        active = self._transmission_repo.get_active_for_invoice(invoice_id, _ACTIVE_STATUSES)
        if active is None:
            return
        raise InvalidInvoiceError(
            f"Faktura {invoice_id} ma już aktywną transmisję {active.id} "
            f"(status: {active.status})."
        )

    def _ensure_ksef_session_connected(self, invoice) -> None:
        if self._ksef_session_service is None:
            return

        seller_nip = (invoice.seller_snapshot or {}).get("nip", "")
        if not seller_nip:
            return

        status = self._ksef_session_service.get_connection_status(seller_nip)
        if status["ui_status"] == "CONNECTED":
            return

        reason = status["details"]["reason"]
        if reason in {"NO_SESSION", "SESSION_EXPIRED"}:
            raise NoKSeFSessionError(
                f"Brak aktywnej sesji KSeF dla NIP sprzedawcy {seller_nip}. "
                "Utwórz sesję przez POST /api/v1/ksef-sessions/ przed wysyłką."
            )
        raise KSeFNotConnectedError("KSeF not connected")

    def _validate_invoice_before_enqueue(self, invoice) -> None:
        invoice.validate_for_ksef()
        self._ensure_ksef_session_connected(invoice)

    def _create_queued_transmission(self, invoice_id: UUID, idempotency_key: str, now: datetime) -> TransmissionORM:
        transmission = TransmissionORM(
            id=uuid4(),
            invoice_id=invoice_id,
            channel="ksef",
            operation_type="submit",
            status=TransmissionStatus.QUEUED,
            attempt_no=1,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        return self._transmission_repo.add(transmission)

    def _mark_invoice_as_sending(self, invoice_id: UUID, invoice, now: datetime) -> None:
        invoice.transition_to(InvoiceStatus.SENDING)
        invoice.updated_at = now
        self._invoice_repo.update(invoice_id, invoice)

    def _enqueue_submit_invoice_job(self, transmission_id: UUID, invoice_id: UUID, now: datetime) -> None:
        self._job_repo.add(
            BackgroundJob(
                id=uuid4(),
                job_type="submit_invoice",
                status="pending",
                payload_json={
                    "transmission_id": str(transmission_id),
                    "invoice_id": str(invoice_id),
                },
                created_at=now,
            )
        )

    def _record_submit_audit(self, actor: AuthenticatedUser, transmission_id: UUID, invoice_id: UUID) -> None:
        self._audit_service.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="transmission.created",
            entity_type="transmission",
            entity_id=str(transmission_id),
            after={"status": TransmissionStatus.QUEUED.value},
        )
        self._audit_service.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="invoice.status_changed",
            entity_type="invoice",
            entity_id=str(invoice_id),
            after={"status": InvoiceStatus.SENDING.value},
        )

    def submit_invoice(
        self, invoice_id: UUID, actor: AuthenticatedUser
    ) -> TransmissionORM:
        invoice = self._invoice_repo.lock_for_update(invoice_id)
        if invoice is None:
            raise NotFoundError(f"Nie znaleziono faktury {invoice_id}.")

        if invoice.status == InvoiceStatus.SENDING:
            reused = self._try_reuse_idempotent_transmission(invoice, invoice_id)
            if reused is not None:
                return reused

        self._ensure_invoice_can_be_submitted(invoice)
        self._ensure_no_active_transmission(invoice_id)
        self._validate_invoice_before_enqueue(invoice)

        idempotency_key = self._build_idempotency_key(invoice)
        reused = self._try_reuse_by_idempotency_key(invoice_id, idempotency_key)
        if reused is not None:
            return reused

        now = datetime.now(UTC)
        saved_transmission = self._create_queued_transmission(invoice_id, idempotency_key, now)
        self._mark_invoice_as_sending(invoice_id, invoice, now)
        self._enqueue_submit_invoice_job(saved_transmission.id, invoice_id, now)

        self.session.flush()
        self._record_submit_audit(actor, saved_transmission.id, invoice_id)

        return saved_transmission

    def retry_transmission(
        self, transmission_id: UUID, actor: AuthenticatedUser
    ) -> TransmissionORM:
        transmission = self._transmission_repo.lock_for_update(transmission_id)
        if transmission is None:
            raise NotFoundError(f"Nie znaleziono transmisji {transmission_id}.")

        if transmission.status not in _RETRYABLE_STATUSES:
            raise InvalidInvoiceError(
                f"Nie można wykonać retry transmisji w statusie "
                f"'{transmission.status}' — dozwolone: {_RETRYABLE_STATUSES}."
            )

        if transmission.attempt_no >= MAX_RETRY_ATTEMPTS:
            raise InvalidInvoiceError(
                f"Przekroczono maksymalną liczbę prób ({MAX_RETRY_ATTEMPTS}) "
                f"dla transmisji {transmission_id}."
            )

        # Guard: blokuj retry gdy inna transmisja dla tej faktury jest już aktywna
        other_active = self._transmission_repo.get_active_for_invoice(
            transmission.invoice_id, _ACTIVE_STATUSES
        )
        if other_active is not None and other_active.id != transmission.id:
            raise InvalidInvoiceError(
                f"Faktura {transmission.invoice_id} ma już aktywną transmisję "
                f"{other_active.id} (status: {other_active.status}). "
                "Retry zablokowany."
            )

        now = datetime.now(UTC)
        transmission.attempt_no += 1
        transmission.status = TransmissionStatus.QUEUED
        transmission.error_code = None
        transmission.error_message = None

        self._job_repo.add(
            BackgroundJob(
                id=uuid4(),
                job_type="submit_invoice",
                status="pending",
                payload_json={
                    "transmission_id": str(transmission_id),
                    "invoice_id": str(transmission.invoice_id),
                },
                created_at=now,
            )
        )

        self.session.flush()

        self._audit_service.record(
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            event_type="transmission.retry",
            entity_type="transmission",
            entity_id=str(transmission_id),
            after={"attempt_no": transmission.attempt_no},
        )

        return transmission

    def get_transmission(self, transmission_id: UUID) -> TransmissionORM:
        transmission = self._transmission_repo.get_by_id(transmission_id)
        if transmission is None:
            raise NotFoundError(f"Nie znaleziono transmisji {transmission_id}.")
        return transmission

    def list_for_invoice(self, invoice_id: UUID) -> list[TransmissionORM]:
        return self._transmission_repo.list_for_invoice(invoice_id)

    def list_all(self, page: int, size: int) -> tuple[list[TransmissionORM], int]:
        return self._transmission_repo.list_all_paginated(page, size)
