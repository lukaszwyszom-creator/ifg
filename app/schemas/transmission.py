from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TransmissionInvoiceSnapshot(BaseModel):
    """Zwięzły snapshot faktury do tooltipu Monitora KSeF (bez dodatkowych zapytań)."""

    number: str | None = None
    counterparty_name: str | None = None
    counterparty_nip: str | None = None
    gross_total: str | None = None
    currency: str | None = None
    issue_date: date | None = None
    ksef_reference_number: str | None = None
    status: str | None = None
    direction: str | None = None


class TransmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_id: UUID | None = None
    channel: str
    operation_type: str
    severity: str | None = None
    correlation_id: UUID | None = None
    job_id: UUID | None = None
    status: str
    attempt_no: int
    idempotency_key: str | None = None
    external_reference: str | None = None
    ksef_reference_number: str | None = None
    upo_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    metadata_json: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    invoice_number_local: str | None = None
    invoice_snapshot: TransmissionInvoiceSnapshot | None = None


class KSeFStatusResponse(BaseModel):
    """Zwięzły widok wyniku integracji KSeF dla danej transmisji.

    Semantyka pól:
    - ksef_reference_number: finalny numer KSeF (non-null tylko gdy status='success')
    - upo_status:  'fetched' | 'failed' | None
    - is_final:    True gdy status jest terminalny (success / failed_permanent)
    """
    transmission_id: UUID
    invoice_id: UUID
    status: str
    ksef_reference_number: str | None
    upo_status: str | None
    is_final: bool


class TransmissionListResponse(BaseModel):
    items: list[TransmissionResponse]
    invoice_id: UUID


class TransmissionPageResponse(BaseModel):
    items: list[TransmissionResponse]
    total: int
    page: int
    size: int


class RetryTransmissionResponse(BaseModel):
    transmission_id: UUID
    attempt_no: int
    status: str


class SubmitInvoiceResponse(BaseModel):
    transmission_id: UUID
    invoice_id: UUID
    status: str
