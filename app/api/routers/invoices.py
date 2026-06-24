from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db_session, get_idempotency_service, get_invoice_service, get_payment_service, get_settings_service
from app.core.exceptions import ConflictError
from app.core.security import AuthenticatedUser
from app.domain.exceptions import InvalidInvoiceError, InvalidStatusTransitionError
from app.domain.models.invoice import Invoice
from app.persistence.repositories.transmission_repository import TransmissionRepository
from app.schemas.invoice import (
    InvoiceCreateRequest,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdateRequest,
)
from app.services.idempotency_service import DuplicateRequestError, IdempotencyService
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.services.pdf_service import (
    render_invoice_html,
    render_invoice_pdf,
    resolve_seller_bank_account_for_render,
)
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _invoice_response(
    invoice: Invoice,
    invoice_service: InvoiceService,
    payment_service: PaymentService | None = None,
    *,
    ksef_last_error: str | None = None,
) -> InvoiceResponse:
    remaining_map = invoice_service.compute_remaining_amounts([invoice])
    raw_remaining = remaining_map.get(invoice.id)
    remaining = raw_remaining if isinstance(raw_remaining, Decimal) else None
    form_paid = None
    if payment_service is not None:
        try:
            raw_form_paid = payment_service.get_invoice_form_payment_amount(invoice.id)
            if isinstance(raw_form_paid, Decimal):
                form_paid = raw_form_paid
            elif isinstance(raw_form_paid, (int, float, str)):
                try:
                    form_paid = Decimal(str(raw_form_paid))
                except Exception:
                    form_paid = None
        except Exception:
            form_paid = None
    buyer_id = invoice_service.resolve_buyer_id(invoice)
    if not isinstance(buyer_id, UUID):
        buyer_id = None
    return InvoiceResponse.from_domain(
        invoice,
        remaining_amount=remaining,
        form_paid_amount=form_paid,
        buyer_id=buyer_id,
        ksef_last_error=ksef_last_error,
    )


@router.get("/", response_model=InvoiceListResponse)
def list_invoices(
    status: str | None = Query(default=None),
    issue_date_from: date | None = Query(default=None),
    issue_date_to: date | None = Query(default=None),
    issue_date_before: date | None = Query(default=None),
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    view: str | None = Query(default=None, pattern="^(open|month)$"),
    number_filter: str | None = Query(default=None),
    direction: str | None = Query(default=None, pattern="^(sale|purchase)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    session: Annotated[Session, Depends(get_db_session)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> InvoiceListResponse:
    # Parametr `month=YYYY-MM` ma pierwszeństwo gdy nie podano jawnie zakresu dat.
    # Zapewnia spójność widoku z miesiącem wyświetlanym w nagłówku UI.
    # Stosujemy konwencję półotwartego przedziału [first_day, first_day_of_next_month),
    # co eliminuje edge-case'y końca dnia i jest zgodne z praktyką SQL.
    # Dla view="open" filtry dat są ignorowane przez service.
    if (
        view != "open"
        and month
        and issue_date_from is None
        and issue_date_to is None
        and issue_date_before is None
    ):
        year, mon = (int(part) for part in month.split("-"))
        issue_date_from = date(year, mon, 1)
        if mon == 12:
            issue_date_before = date(year + 1, 1, 1)
        else:
            issue_date_before = date(year, mon + 1, 1)

    items, total = invoice_service.list_invoices(
        status=status,
        page=page,
        size=size,
        issue_date_from=issue_date_from,
        issue_date_to=issue_date_to,
        issue_date_before=issue_date_before,
        number_filter=number_filter,
        direction=direction,
        view=view,
    )
    # Saldo do zapłaty per faktura — liczone na bieżąco (poza DB).
    # Działa dla każdego widoku (open / month / domyślnego).
    remaining_map = invoice_service.compute_remaining_amounts(items)
    ksef_errors: dict = {}
    if items:
        try:
            ksef_errors = TransmissionRepository(session).get_latest_ksef_errors_for_invoices(
                [invoice.id for invoice in items]
            )
        except Exception:
            ksef_errors = {}
    # Agregacja po stronie backendu wyłącznie dla widoku 'open'
    # (frontend nie liczy sum). Wykorzystuje już policzone remaining_map.
    summary = (
        invoice_service.compute_open_summary(items, remaining_map)
        if view == "open"
        else None
    )
    return InvoiceListResponse(
        items=[
            InvoiceResponse.from_domain(
                i,
                remaining_amount=remaining_map.get(i.id),
                ksef_last_error=ksef_errors.get(i.id),
            )
            for i in items
        ],
        total=total,
        page=page,
        size=size,
        summary=summary,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: UUID,
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> InvoiceResponse:
    invoice = invoice_service.get_invoice(invoice_id)
    return _invoice_response(invoice, invoice_service, payment_service)


@router.post("/", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    body: InvoiceCreateRequest,
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)] = ...,
    idempotency_service: Annotated[IdempotencyService, Depends(get_idempotency_service)] = ...,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> InvoiceResponse:
    scope = "create_invoice"

    if idempotency_key:
        cached = idempotency_service.acquire(scope, idempotency_key, body.model_dump())
        if cached is not None:
            return cached

    try:
        created = invoice_service.create_invoice(body.model_dump(), actor)
        invoice = created
        if body.amount_paid is not None and body.amount_paid > 0:
            try:
                payment_service.record_invoice_initial_payment(
                    invoice.id,
                    body.amount_paid,
                    actor,
                    payment_date=body.issue_date,
                )
            except ValueError as exc:
                raise InvalidInvoiceError(str(exc)) from exc
            refreshed = invoice_service.get_invoice(invoice.id)
            if isinstance(refreshed, Invoice):
                invoice = refreshed
        response = _invoice_response(invoice, invoice_service, payment_service)

        if idempotency_key:
            idempotency_service.complete(
                scope,
                idempotency_key,
                entity_type="invoice",
                entity_id=str(invoice.id),
                response_snapshot=response.model_dump(mode="json"),
            )

        return response

    except (InvalidInvoiceError, DuplicateRequestError):
        if idempotency_key:
            idempotency_service.fail(scope, idempotency_key)
        raise


@router.post("/{invoice_id}/mark-ready", response_model=InvoiceResponse)
def mark_invoice_as_ready(
    invoice_id: UUID,
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> InvoiceResponse:
    try:
        invoice = invoice_service.mark_as_ready(invoice_id, actor)
        return InvoiceResponse.from_domain(invoice)
    except InvalidInvoiceError as exc:
        raise InvalidInvoiceError(f"Nie można oznaczyć faktury jako gotowej: {exc.message}") from exc
    except InvalidStatusTransitionError as exc:
        raise ConflictError(exc.message) from exc


@router.put("/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: UUID,
    body: InvoiceUpdateRequest,
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    payment_service: Annotated[PaymentService, Depends(get_payment_service)] = ...,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> InvoiceResponse:
    invoice = invoice_service.update_invoice(invoice_id, body.model_dump(), actor)
    if body.amount_paid is not None:
        try:
            payment_service.set_invoice_form_payment(
                invoice_id,
                body.amount_paid,
                actor,
                payment_date=body.issue_date,
            )
        except ValueError as exc:
            raise InvalidInvoiceError(str(exc)) from exc
    invoice = invoice_service.get_invoice(invoice_id)
    return _invoice_response(invoice, invoice_service, payment_service)


@router.get("/{invoice_id}/preview", response_class=HTMLResponse)
def get_invoice_preview(
    invoice_id: UUID,
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    settings_service: Annotated[SettingsService, Depends(get_settings_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> HTMLResponse:
    """Podgląd HTML faktury — otwierany w nowej karcie, gotowy do druku (Ctrl+P)."""
    invoice = invoice_service.get_invoice(invoice_id)
    remaining_map = invoice_service.compute_remaining_amounts([invoice])
    schema = InvoiceResponse.from_domain(invoice, remaining_amount=remaining_map.get(invoice.id))
    company_bank = settings_service.get_settings().get("seller_bank_account")
    bank_account = resolve_seller_bank_account_for_render(
        schema,
        company_bank_account=company_bank,
    )
    html = render_invoice_html(schema, seller_bank_account=bank_account)
    return HTMLResponse(content=html)


@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)] = ...,
    settings_service: Annotated[SettingsService, Depends(get_settings_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> Response:
    """Pobierz fakturę jako plik PDF (application/pdf)."""
    invoice = invoice_service.get_invoice(invoice_id)
    remaining_map = invoice_service.compute_remaining_amounts([invoice])
    schema = InvoiceResponse.from_domain(invoice, remaining_amount=remaining_map.get(invoice.id))
    company_bank = settings_service.get_settings().get("seller_bank_account")
    bank_account = resolve_seller_bank_account_for_render(
        schema,
        company_bank_account=company_bank,
    )
    pdf_bytes = render_invoice_pdf(schema, seller_bank_account=bank_account)
    filename = f"faktura-{schema.number_local or schema.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

