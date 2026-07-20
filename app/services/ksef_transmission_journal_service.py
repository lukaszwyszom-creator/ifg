from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.domain.enums import KSeFOperationType, KSeFSeverity
from app.persistence.models.transmission import TransmissionORM
from app.persistence.repositories.transmission_repository import TransmissionRepository

_ALLOWED_METADATA_KEYS = {
    "retry_after",
    "offset",
    "page",
    "pages",
    "downloaded",
    "saved",
    "duplicates",
    "skipped",
    "error_code",
    "source",
    "duration_ms",
    "email_status",
    "attempt",
    "max_attempts",
    "recipient_count",
}


class KSeFTransmissionJournalService:
    """Centralne logowanie zdarzeń KSeF do tabeli transmissions."""

    def __init__(self, session: Session, transmission_repository: TransmissionRepository) -> None:
        self.session = session
        self._repo = transmission_repository

    def log_event(
        self,
        *,
        operation_type: KSeFOperationType,
        severity: KSeFSeverity,
        status: str,
        short_description: str,
        invoice_id: UUID | None = None,
        ksef_reference_number: str | None = None,
        correlation_id: UUID | None = None,
        job_id: UUID | None = None,
        attempt_no: int | None = None,
        error_message: str | None = None,
        metadata_json: dict | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> TransmissionORM:
        now = datetime.now(UTC)
        event = TransmissionORM(
            id=uuid4(),
            invoice_id=invoice_id,
            channel="ksef",
            operation_type=operation_type.value,
            severity=severity.value,
            correlation_id=correlation_id or invoice_id or uuid4(),
            job_id=job_id,
            status=status,
            attempt_no=attempt_no if attempt_no is not None else 1,
            idempotency_key=None,
            ksef_reference_number=ksef_reference_number,
            error_message=error_message,
            metadata_json=self._normalize_metadata(metadata_json, short_description),
            started_at=started_at,
            finished_at=finished_at,
            created_at=now,
        )
        return self._repo.add(event)

    @staticmethod
    def _normalize_metadata(metadata_json: dict | None, short_description: str) -> dict:
        payload = {"description": (short_description or "").strip()[:256]}
        if not metadata_json:
            return payload
        for key in _ALLOWED_METADATA_KEYS:
            if key in metadata_json:
                payload[key] = metadata_json[key]
        return payload
