from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.domain.enums import InvoiceStatus, TransmissionStatus
from app.domain.exceptions import KSeFNotConnectedError
from app.integrations.ksef.client import KSeFClient, KSeFClientError, KSeFSessionExpiredError
from app.integrations.ksef.exceptions import KSeFMappingError
from app.integrations.ksef.mapper import KSeFMapper
from app.persistence.models.background_job import BackgroundJob
from app.persistence.repositories.invoice_repository import InvoiceRepository
from app.persistence.repositories.job_repository import JobRepository
from app.persistence.repositories.transmission_repository import TransmissionRepository
from app.services.ksef_session_service import KSeFSessionService

logger = logging.getLogger(__name__)

_MAX_AUTO_RETRY_ATTEMPTS = 5


def _backoff_minutes(attempt_no: int) -> int:
    """Wykładniczy backoff: 1, 2, 4, 8, 16 minut dla prób 1–5."""
    return 2 ** min(attempt_no - 1, 4)


class SubmitInvoiceJobHandler:
    def __init__(
        self,
        session: Session,
        transmission_repository: TransmissionRepository,
        invoice_repository: InvoiceRepository,
        job_repository: JobRepository,
        ksef_client: KSeFClient,
        ksef_session_service: KSeFSessionService,
    ) -> None:
        self.session = session
        self._transmission_repo = transmission_repository
        self._invoice_repo = invoice_repository
        self._job_repo = job_repository
        self._ksef_client = ksef_client
        self._ksef_session_service = ksef_session_service

    def _return_invoice_to_ready_for_submission(self, invoice) -> None:
        if invoice is None or invoice.status != InvoiceStatus.SENDING:
            return

        invoice.status = InvoiceStatus.READY_FOR_SUBMISSION
        logger.warning(
            "Invoice returned to READY_FOR_SUBMISSION due to KSeF unavailability"
        )

    def _mark_processing(self, transmission, now: datetime) -> None:
        transmission.status = TransmissionStatus.PROCESSING
        transmission.started_at = now

    def _load_invoice_or_mark_permanent_failure(
        self,
        invoice_id: UUID,
        transmission_id: UUID,
        transmission,
    ):
        invoice = self._invoice_repo.get_by_id(invoice_id)
        if invoice is not None:
            return invoice

        logger.error(
            "submit_invoice: nie znaleziono faktury %s dla transmisji %s.",
            invoice_id,
            transmission_id,
        )
        transmission.status = TransmissionStatus.FAILED_PERMANENT
        transmission.error_code = "INVOICE_NOT_FOUND"
        transmission.finished_at = datetime.now(UTC)
        self.session.flush()
        return None

    def _resolve_seller_nip(self, invoice) -> str:
        seller_nip = (invoice.seller_snapshot or {}).get("nip", "")
        if not seller_nip:
            raise KSeFMappingError(
                "Brak NIP sprzedawcy w seller_snapshot — nie można wybrać sesji KSeF."
            )
        return seller_nip

    def _ensure_ksef_connected(self, seller_nip: str) -> None:
        connection_status = self._ksef_session_service.get_connection_status(seller_nip)
        if connection_status["ui_status"] == "ERROR":
            raise KSeFNotConnectedError("KSeF not connected")

    def _submit_invoice_to_ksef(self, invoice):
        seller_nip = self._resolve_seller_nip(invoice)
        self._ensure_ksef_connected(seller_nip)
        ctx = self._ksef_session_service.get_session_context(seller_nip)
        xml_bytes = KSeFMapper.invoice_to_xml(invoice)
        idempotency_key = KSeFMapper.xml_content_hash(xml_bytes)
        send_result = self._ksef_client.send_invoice(
            ctx.access_token,
            ctx.session_reference,
            ctx.symmetric_key,
            ctx.initialization_vector,
            xml_bytes,
        )
        return send_result, idempotency_key

    def _enqueue_poll_job(
        self,
        transmission_id: UUID,
        reference_number: str,
        idempotency_key: str,
        now: datetime,
    ) -> None:
        self._job_repo.add(
            BackgroundJob(
                id=uuid4(),
                job_type="poll_ksef_status",
                status="pending",
                payload_json={
                    "transmission_id": str(transmission_id),
                    "reference_number": reference_number,
                    "idempotency_key": idempotency_key,
                },
                created_at=now,
            )
        )

    def _mark_submitted(
        self,
        transmission,
        transmission_id: UUID,
        send_result,
        idempotency_key: str,
        now: datetime,
    ) -> None:
        transmission.status = TransmissionStatus.SUBMITTED
        transmission.external_reference = send_result.reference_number
        transmission.finished_at = datetime.now(UTC)
        self._enqueue_poll_job(
            transmission_id=transmission_id,
            reference_number=send_result.reference_number,
            idempotency_key=idempotency_key,
            now=now,
        )
        self.session.flush()

    def _mark_retryable_failure(
        self,
        transmission,
        error_code: str,
        error_message: str,
    ) -> None:
        now = datetime.now(UTC)
        transmission.status = TransmissionStatus.FAILED_RETRYABLE
        transmission.error_code = error_code
        transmission.error_message = error_message[:512]
        transmission.finished_at = now
        self.session.flush()

    def _mark_permanent_failure(
        self,
        transmission,
        error_code: str,
        error_message: str,
    ) -> None:
        now = datetime.now(UTC)
        transmission.status = TransmissionStatus.FAILED_PERMANENT
        transmission.error_code = error_code
        transmission.error_message = error_message[:512]
        transmission.finished_at = now
        self.session.flush()

    def _enqueue_submit_retry_job(self, transmission, retry_at: datetime, now: datetime) -> None:
        self._job_repo.add(
            BackgroundJob(
                id=uuid4(),
                job_type="submit_invoice",
                status="pending",
                available_at=retry_at,
                payload_json={
                    "transmission_id": str(transmission.id),
                    "invoice_id": str(transmission.invoice_id),
                },
                created_at=now,
            )
        )

    def _mark_temporary_failure_and_retry(self, transmission, error_code: str, error_message: str) -> None:
        now = datetime.now(UTC)
        backoff = timedelta(minutes=_backoff_minutes(transmission.attempt_no))
        retry_at = now + backoff
        transmission.attempt_no += 1
        transmission.status = TransmissionStatus.FAILED_TEMPORARY
        transmission.next_retry_at = retry_at
        transmission.error_code = error_code
        transmission.error_message = error_message
        transmission.finished_at = now
        self._enqueue_submit_retry_job(transmission=transmission, retry_at=retry_at, now=now)
        self.session.flush()

    def _handle_mapping_error(self, invoice_id: UUID, transmission, exc: KSeFMappingError) -> None:
        logger.error(
            "submit_invoice: blad mapowania faktury %s: %s",
            invoice_id,
            exc,
        )
        self._mark_permanent_failure(transmission, "MAPPING_ERROR", str(exc))

    def _handle_missing_session_error(
        self,
        transmission_id: UUID,
        invoice,
        transmission,
        exc: NotFoundError,
    ) -> None:
        logger.warning(
            "submit_invoice: brak sesji KSeF dla transmisji %s (NIP=%s): %s",
            transmission_id,
            (invoice.seller_snapshot or {}).get("nip", "?") if invoice else "?",
            exc,
        )
        self._return_invoice_to_ready_for_submission(invoice)
        self._mark_retryable_failure(transmission, "NO_KSEF_SESSION", str(exc))

    def _handle_not_connected_error(
        self,
        transmission_id: UUID,
        invoice,
        transmission,
        exc: KSeFNotConnectedError,
    ) -> None:
        logger.warning(
            "submit_invoice: KSeF not connected dla transmisji %s: %s",
            transmission_id,
            exc,
        )
        self._return_invoice_to_ready_for_submission(invoice)
        self._mark_retryable_failure(transmission, "KSEF_NOT_CONNECTED", str(exc))

    def _handle_session_expired_error(
        self,
        transmission_id: UUID,
        invoice,
        transmission,
        exc: KSeFSessionExpiredError,
    ) -> None:
        seller_nip = (invoice.seller_snapshot or {}).get("nip", "") if invoice else ""
        logger.warning(
            "submit_invoice: wygasła sesja KSeF dla transmisji %s (NIP=%s): %s",
            transmission_id,
            seller_nip,
            exc,
        )
        self._return_invoice_to_ready_for_submission(invoice)
        if seller_nip:
            try:
                self._ksef_session_service.mark_session_expired(seller_nip)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "submit_invoice: nie udało się unieważnić sesji dla NIP %s.",
                    seller_nip,
                )
        self._mark_retryable_failure(transmission, "SESSION_EXPIRED", str(exc))

    def _handle_ksef_client_error(self, invoice, transmission, exc: KSeFClientError) -> None:
        error_code = str(exc.status_code) if exc.status_code else "UNKNOWN"
        if exc.transient and transmission.attempt_no < _MAX_AUTO_RETRY_ATTEMPTS:
            self._return_invoice_to_ready_for_submission(invoice)
            self._mark_temporary_failure_and_retry(transmission, error_code, str(exc))
            return

        now = datetime.now(UTC)
        transmission.status = TransmissionStatus.FAILED_PERMANENT
        transmission.error_code = error_code
        transmission.error_message = str(exc)
        transmission.finished_at = now
        self.session.flush()

    def _handle_unexpected_error(self, transmission_id: UUID, transmission, exc: Exception) -> None:
        logger.exception(
            "submit_invoice: nieoczekiwany blad dla transmisji %s.",
            transmission_id,
        )
        if transmission.attempt_no < _MAX_AUTO_RETRY_ATTEMPTS:
            self._mark_temporary_failure_and_retry(transmission, "INTERNAL_ERROR", str(exc)[:512])
            return

        now = datetime.now(UTC)
        transmission.status = TransmissionStatus.FAILED_PERMANENT
        transmission.error_code = "INTERNAL_ERROR"
        transmission.error_message = str(exc)[:512]
        transmission.finished_at = now
        self.session.flush()

    def handle(self, payload: dict) -> None:
        transmission_id = UUID(payload["transmission_id"])
        invoice_id = UUID(payload["invoice_id"])

        transmission = self._transmission_repo.lock_for_update(transmission_id)
        if transmission is None:
            logger.warning(
                "submit_invoice: nie znaleziono transmisji %s — pomijam.",
                transmission_id,
            )
            return

        now = datetime.now(UTC)
        self._mark_processing(transmission, now)

        invoice = self._load_invoice_or_mark_permanent_failure(
            invoice_id=invoice_id,
            transmission_id=transmission_id,
            transmission=transmission,
        )
        if invoice is None:
            return

        try:
            send_result, idempotency_key = self._submit_invoice_to_ksef(invoice)
            self._mark_submitted(
                transmission=transmission,
                transmission_id=transmission_id,
                send_result=send_result,
                idempotency_key=idempotency_key,
                now=now,
            )

        except KSeFMappingError as exc:
            self._handle_mapping_error(invoice_id, transmission, exc)

        except NotFoundError as exc:
            self._handle_missing_session_error(transmission_id, invoice, transmission, exc)

        except KSeFNotConnectedError as exc:
            self._handle_not_connected_error(transmission_id, invoice, transmission, exc)

        except KSeFSessionExpiredError as exc:
            self._handle_session_expired_error(transmission_id, invoice, transmission, exc)

        except KSeFClientError as exc:
            self._handle_ksef_client_error(invoice, transmission, exc)

        except Exception as exc:
            self._handle_unexpected_error(transmission_id, transmission, exc)