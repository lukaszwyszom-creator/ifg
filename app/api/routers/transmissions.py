from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from app.api.deps import get_current_user, get_transmission_service
from app.core.exceptions import NotFoundError
from app.core.security import AuthenticatedUser
from app.domain.enums import TransmissionStatus
from app.schemas.transmission import (
    KSeFStatusResponse,
    RetryTransmissionResponse,
    SubmitInvoiceResponse,
    TransmissionInvoiceSnapshot,
    TransmissionListResponse,
    TransmissionPageResponse,
    TransmissionResponse,
)
from app.services.transmission_service import TransmissionService

router = APIRouter(prefix="/transmissions", tags=["transmissions"])

_TERMINAL_STATUSES = {TransmissionStatus.SUCCESS, TransmissionStatus.FAILED_PERMANENT}


_TRANSMISSION_RESPONSE_FIELDS = (
    "id",
    "invoice_id",
    "channel",
    "operation_type",
    "severity",
    "correlation_id",
    "job_id",
    "status",
    "attempt_no",
    "idempotency_key",
    "external_reference",
    "ksef_reference_number",
    "upo_status",
    "error_code",
    "error_message",
    "metadata_json",
    "started_at",
    "finished_at",
    "created_at",
)


def _build_invoice_snapshot(transmission) -> TransmissionInvoiceSnapshot | None:
    invoice = getattr(transmission, "invoice", None)
    if invoice is None:
        return None

    direction = (getattr(invoice, "direction", None) or "sale").strip().lower()
    seller = getattr(invoice, "seller_snapshot_json", None) or {}
    buyer = getattr(invoice, "buyer_snapshot_json", None) or {}
    totals = getattr(invoice, "totals_json", None) or {}
    if not isinstance(seller, dict):
        seller = {}
    if not isinstance(buyer, dict):
        buyer = {}
    if not isinstance(totals, dict):
        totals = {}

    party = seller if direction == "purchase" else buyer
    gross = totals.get("total_gross")
    issue_date = getattr(invoice, "issue_date", None)
    ksef_ref = getattr(invoice, "ksef_reference_number", None) or getattr(
        transmission, "ksef_reference_number", None
    )

    return TransmissionInvoiceSnapshot(
        number=getattr(invoice, "number_local", None),
        counterparty_name=party.get("name"),
        counterparty_nip=party.get("nip"),
        gross_total=str(gross) if gross is not None else None,
        currency=getattr(invoice, "currency", None) or "PLN",
        issue_date=issue_date,
        ksef_reference_number=ksef_ref,
        status=getattr(invoice, "status", None),
        direction=direction,
    )


def _transmission_to_response(transmission) -> TransmissionResponse:
    invoice = getattr(transmission, "invoice", None)
    raw_number = getattr(invoice, "number_local", None) if invoice is not None else None
    if not isinstance(raw_number, str) or not raw_number.strip():
        raw_number = _extract_invoice_number_from_xml(getattr(transmission, "xml_content", None))
    invoice_number_local = raw_number.strip() if isinstance(raw_number, str) and raw_number.strip() else None
    return TransmissionResponse(
        **{field: getattr(transmission, field) for field in _TRANSMISSION_RESPONSE_FIELDS},
        invoice_number_local=invoice_number_local,
        invoice_snapshot=_build_invoice_snapshot(transmission),
    )


def _extract_invoice_number_from_xml(xml_content: bytes | None) -> str | None:
    """Fallback: numer faktury (P_2) z zapisanego XML transmisji."""
    if not xml_content:
        return None
    try:
        from lxml import etree

        root = etree.fromstring(xml_content)
    except Exception:
        return None

    for element in root.iter():
        if etree.QName(element).localname == "P_2":
            text = (element.text or "").strip()
            if text:
                return text
    return None


@router.get("/", response_model=TransmissionPageResponse)
def list_transmissions(
    page: int = 1,
    size: int = 20,
    warnings_or_errors_only: bool = False,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> TransmissionPageResponse:
    items, total = transmission_service.list_all(page=page, size=size)
    if warnings_or_errors_only:
        filtered = [
            t
            for t in items
            if str(getattr(t, "severity", "")).upper() in {"WARNING", "ERROR"}
            or str(getattr(t, "status", "")).lower() in {"failed_permanent", "failed_retryable", "failed_temporary"}
        ]
        items = filtered
        total = len(filtered)
    return TransmissionPageResponse(
        items=[_transmission_to_response(t) for t in items],
        total=total,
        page=page,
        size=size,
    )


@router.post("/submit/{invoice_id}", response_model=SubmitInvoiceResponse, status_code=202)
def submit_invoice(
    invoice_id: UUID,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> SubmitInvoiceResponse:
    transmission = transmission_service.submit_invoice(invoice_id, actor)
    return SubmitInvoiceResponse(
        transmission_id=transmission.id,
        invoice_id=invoice_id,
        status=transmission.status,
    )


@router.post("/{transmission_id}/retry", response_model=RetryTransmissionResponse)
def retry_transmission(
    transmission_id: UUID,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> RetryTransmissionResponse:
    transmission = transmission_service.retry_transmission(transmission_id, actor)
    return RetryTransmissionResponse(
        transmission_id=transmission.id,
        attempt_no=transmission.attempt_no,
        status=transmission.status,
    )


@router.get("/{transmission_id}/upo")
def download_upo(
    transmission_id: UUID,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> Response:
    """Pobierz zapisane UPO (Urzędowe Poświadczenie Odbioru) jako plik XML.

    Zwraca 404 gdy:
    - transmisja nie istnieje,
    - UPO nie zostało jeszcze pobrane (upo_status != 'fetched'),
    - plik XML jest pusty.
    """
    transmission = transmission_service.get_transmission(transmission_id)
    if transmission.upo_status != "fetched" or not transmission.upo_xml:
        ksef_ref = transmission.ksef_reference_number or str(transmission_id)
        if transmission.upo_status == "failed":
            detail = f"Pobranie UPO nie powiodło się dla transmisji {transmission_id}."
        elif transmission.upo_status is None:
            detail = f"UPO nie jest jeszcze dostępne dla transmisji {transmission_id}."
        else:
            detail = f"UPO niedostępne dla transmisji {transmission_id}."
        raise NotFoundError(detail)

    ksef_ref = transmission.ksef_reference_number or str(transmission_id)
    safe_ref = "".join(c if c.isalnum() or c in "-_." else "_" for c in ksef_ref)
    filename = f"UPO_{safe_ref}.xml"

    return Response(
        content=transmission.upo_xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{transmission_id}/ksef-status", response_model=KSeFStatusResponse)
def get_ksef_status(
    transmission_id: UUID,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> KSeFStatusResponse:
    """Zwięzły widok wyniku integracji KSeF.

    Numer KSeF jest finalny wyłącznie gdy ``is_final=True`` i ``status='success'``.
    Gdy ``upo_status`` jest ``null``, UPO nie zostało jeszcze pobrane lub transmisja
    nie osiągnęła statusu success.
    """
    transmission = transmission_service.get_transmission(transmission_id)
    status_value = transmission.status.value if hasattr(transmission.status, "value") else transmission.status
    return KSeFStatusResponse(
        transmission_id=transmission.id,
        invoice_id=transmission.invoice_id,
        status=status_value,
        ksef_reference_number=transmission.ksef_reference_number,
        upo_status=transmission.upo_status,
        is_final=status_value in {s.value for s in _TERMINAL_STATUSES},
    )


@router.get("/{transmission_id}", response_model=TransmissionResponse)
def get_transmission(
    transmission_id: UUID,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> TransmissionResponse:
    transmission = transmission_service.get_transmission(transmission_id)
    return _transmission_to_response(transmission)


@router.get("/invoice/{invoice_id}", response_model=TransmissionListResponse)
def list_transmissions_for_invoice(
    invoice_id: UUID,
    transmission_service: Annotated[TransmissionService, Depends(get_transmission_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> TransmissionListResponse:
    transmissions = transmission_service.list_for_invoice(invoice_id)
    return TransmissionListResponse(
        items=[_transmission_to_response(t) for t in transmissions],
        invoice_id=invoice_id,
    )

