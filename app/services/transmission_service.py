from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import AuthenticatedUser
from app.domain.enums import InvoiceStatus, InvoiceType, TransmissionStatus
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
from app.services.invoice_service import InvoiceService
from app.services.settings_service import SettingsService

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
        settings_service: SettingsService | None = None,
        invoice_service: InvoiceService | None = None,
    ) -> None:
        self.session = session
        self._transmission_repo = transmission_repository
        self._invoice_repo = invoice_repository
        self._job_repo = job_repository
        self._audit_service = audit_service
        self._ksef_session_service = ksef_session_service
        self._settings_service = settings_service
        self._invoice_service = invoice_service

    @staticmethod
    def sync_invoice_from_terminal_transmission(
        invoice_repository: InvoiceRepository,
        *,
        invoice_id: UUID,
        transmission_status: TransmissionStatus,
        ksef_reference_number: str | None = None,
    ) -> None:
        """Utrzymuje spójność statusu faktury po terminalnym statusie transmisji."""
        if transmission_status == TransmissionStatus.SUCCESS:
            target = InvoiceStatus.ACCEPTED
        elif transmission_status == TransmissionStatus.FAILED_PERMANENT:
            target = InvoiceStatus.REJECTED
        elif transmission_status == TransmissionStatus.FAILED_RETRYABLE:
            target = InvoiceStatus.READY_FOR_SUBMISSION
        else:
            return

        invoice = invoice_repository.lock_for_update(invoice_id)
        if invoice is None:
            return

        if transmission_status == TransmissionStatus.FAILED_RETRYABLE:
            if invoice.status != InvoiceStatus.SENDING:
                return
            invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
            invoice_repository.update(invoice.id, invoice)
            return

        if invoice.status == target:
            if (
                target == InvoiceStatus.ACCEPTED
                and ksef_reference_number
                and invoice.ksef_reference_number != ksef_reference_number
            ):
                invoice.ksef_reference_number = ksef_reference_number
                invoice_repository.update(invoice.id, invoice)
            return

        if invoice.status != InvoiceStatus.SENDING:
            return

        if target == InvoiceStatus.REJECTED:
            invoice.status = InvoiceStatus.REJECTED
        else:
            try:
                invoice.transition_to(InvoiceStatus.ACCEPTED)
            except (InvalidStatusTransitionError, InvalidInvoiceError):
                invoice.status = InvoiceStatus.ACCEPTED
            if ksef_reference_number:
                invoice.ksef_reference_number = ksef_reference_number

        invoice_repository.update(invoice.id, invoice)

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
        direction = str(getattr(invoice, "direction", "") or "").strip().lower()
        if invoice.status == InvoiceStatus.REJECTED:
            if direction != "sale":
                raise InvalidStatusTransitionError(
                    f"Faktura musi mieć status 'ready_for_submission' "
                    f"(aktualnie: '{invoice.status.value}')."
                )
            return
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

    def _refresh_sale_seller_snapshot(self, invoice) -> Invoice:
        direction = str(getattr(invoice, "direction", "") or "").strip().lower()
        if direction != "sale" or self._settings_service is None:
            return invoice

        snapshot = self._settings_service.build_company_snapshot()
        try:
            self._settings_service.validate_company_snapshot(snapshot)
        except ValidationError as exc:
            raise InvalidInvoiceError(str(exc)) from exc

        invoice.seller_snapshot = snapshot
        return self._invoice_repo.update(invoice.id, invoice)

    def _prepare_sale_invoice_for_submit(
        self, invoice_id: UUID, invoice, actor: AuthenticatedUser
    ) -> Invoice:
        invoice = self._refresh_sale_seller_snapshot(invoice)

        direction = str(getattr(invoice, "direction", "") or "").strip().lower()
        if direction != "sale":
            return invoice

        if (invoice.number_local or "").strip():
            return invoice

        if self._invoice_service is None:
            raise InvalidInvoiceError(
                "Nie udało się nadać numeru faktury. Spróbuj ponownie."
            )

        try:
            return self._invoice_service.ensure_number_local(invoice_id, invoice, actor)
        except InvalidInvoiceError as exc:
            raise InvalidInvoiceError(self._friendly_submit_error(exc.message)) from exc

    @staticmethod
    def _friendly_submit_error(message: str) -> str:
        if (
            "Niekompletny snapshot sprzedawcy" in message
            or message == SettingsService.COMPANY_SETTINGS_MSG
        ):
            return SettingsService.COMPANY_SETTINGS_MSG
        if "Niekompletny snapshot nabywcy" in message:
            return "Uzupełnij dane nabywcy na fakturze przed wysyłką do KSeF."
        if "numeru lokalnego" in message or "number_local" in message:
            return (
                "Faktura sprzedaży nie ma numeru lokalnego. "
                "Zapisz fakturę ponownie przed wysyłką do KSeF."
            )
        return message

    @staticmethod
    def _validate_rejected_sale_resubmit(invoice) -> None:
        direction = str(getattr(invoice, "direction", "") or "").strip().lower()
        if direction != "sale":
            raise InvalidInvoiceError(
                f"Faktura musi mieć status '{InvoiceStatus.READY_FOR_SUBMISSION.value}' "
                f"przed wysyłką do KSeF (aktualnie: '{invoice.status.value}')."
            )
        invoice.validate_sale_formal_requirements(require_number_local=True)
        invoice.validate_vat()
        if invoice.invoice_type in {InvoiceType.KOR, InvoiceType.KOR_ZAL, InvoiceType.KOR_ROZ}:
            invoice.validate_kor()
        if invoice.invoice_type in (InvoiceType.ZAL, InvoiceType.ROZ):
            invoice.validate_zal()

    def _validate_invoice_before_enqueue(self, invoice) -> None:
        try:
            direction = str(getattr(invoice, "direction", "") or "").strip().lower()
            if direction == "sale" and not (invoice.number_local or "").strip():
                raise InvalidInvoiceError(
                    "Faktura sprzedaży nie ma numeru lokalnego. "
                    "Zapisz fakturę ponownie przed wysyłką do KSeF."
                )
            if invoice.status == InvoiceStatus.REJECTED:
                self._validate_rejected_sale_resubmit(invoice)
            else:
                invoice.validate_for_ksef()
                if invoice.direction == "sale":
                    invoice.validate_sale_formal_requirements(require_number_local=True)
        except InvalidInvoiceError as exc:
            raise InvalidInvoiceError(self._friendly_submit_error(exc.message)) from exc
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
        if invoice.status == InvoiceStatus.REJECTED:
            invoice.status = InvoiceStatus.SENDING
        else:
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
        invoice = self._prepare_sale_invoice_for_submit(invoice_id, invoice, actor)
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

        invoice = self._invoice_repo.lock_for_update(transmission.invoice_id)
        if invoice is None:
            raise NotFoundError(f"Nie znaleziono faktury {transmission.invoice_id}.")

        direction = str(getattr(invoice, "direction", "") or "").strip().lower()
        if direction == "sale":
            invoice = self._prepare_sale_invoice_for_submit(transmission.invoice_id, invoice, actor)
            self._validate_invoice_before_enqueue(invoice)

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
