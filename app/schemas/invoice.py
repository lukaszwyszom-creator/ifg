from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import InvoiceType
from app.domain.models.invoice import Invoice, InvoiceItem, calculate_overdue_days


class InvoiceItemInput(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    unit_price_net: Decimal
    vat_rate: Decimal


class InvoiceCreateRequest(BaseModel):
    buyer_id: UUID | None = None
    issue_date: date
    sale_date: date
    delivery_date: date | None = None
    due_date: date | None = None
    currency: str = "PLN"
    exchange_rate: Decimal | None = None
    exchange_rate_date: date | None = None
    direction: str = "sale"
    items: list[InvoiceItemInput]
    invoice_type: InvoiceType = InvoiceType.VAT
    correction_of_invoice_id: UUID | None = None
    correction_of_ksef_number: str | None = None
    correction_reason: str | None = None


class InvoiceUpdateRequest(BaseModel):
    buyer_id: UUID
    issue_date: date
    sale_date: date
    delivery_date: date | None = None
    due_date: date | None = None
    currency: str = "PLN"
    items: list[InvoiceItemInput]


class InvoiceItemResponse(BaseModel):
    id: UUID | None = None
    name: str
    quantity: Decimal
    unit: str
    unit_price_net: Decimal
    vat_rate: Decimal
    net_total: Decimal
    vat_total: Decimal
    gross_total: Decimal
    sort_order: int

    @classmethod
    def from_domain(cls, item: InvoiceItem) -> "InvoiceItemResponse":
        return cls(
            id=item.id,
            name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            unit_price_net=item.unit_price_net,
            vat_rate=item.vat_rate,
            net_total=item.net_total,
            vat_total=item.vat_total,
            gross_total=item.gross_total,
            sort_order=item.sort_order,
        )


class InvoiceResponse(BaseModel):
    id: UUID
    status: str
    number_local: str | None = None
    issue_date: date
    sale_date: date
    delivery_date: date | None = None
    due_date: date | None = None
    overdue_days: int | None = None
    ksef_reference_number: str | None = None
    currency: str
    seller_snapshot: dict
    buyer_snapshot: dict
    items: list[InvoiceItemResponse]
    total_net: Decimal
    total_vat: Decimal
    total_gross: Decimal
    exchange_rate: Decimal | None = None
    exchange_rate_date: date | None = None
    payment_status: str = "unpaid"
    invoice_type: str = "VAT"
    direction: str = "sale"
    correction_of_invoice_id: UUID | None = None
    correction_of_ksef_number: str | None = None
    correction_reason: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Pole obliczane (poza modelem domenowym, nie zapisywane w DB):
    # remaining_amount = total_gross - sum(active payment_allocations).
    # None oznacza brak danych (np. gdy endpoint nie liczy salda).
    remaining_amount: Decimal | None = None

    @classmethod
    def from_domain(
        cls,
        invoice: Invoice,
        remaining_amount: Decimal | None = None,
    ) -> "InvoiceResponse":
        return cls(
            id=invoice.id,
            status=invoice.status.value,
            number_local=invoice.number_local,
            issue_date=invoice.issue_date,
            sale_date=invoice.sale_date,
            delivery_date=invoice.delivery_date,
            due_date=invoice.due_date,
            overdue_days=calculate_overdue_days(invoice.due_date),
            ksef_reference_number=invoice.ksef_reference_number,
            currency=invoice.currency,
            seller_snapshot=invoice.seller_snapshot,
            buyer_snapshot=invoice.buyer_snapshot,
            items=[InvoiceItemResponse.from_domain(i) for i in invoice.items],
            total_net=invoice.total_net,
            total_vat=invoice.total_vat,
            total_gross=invoice.total_gross,
            exchange_rate=invoice.exchange_rate,
            exchange_rate_date=invoice.exchange_rate_date,
            payment_status=invoice.payment_status,
            invoice_type=invoice.invoice_type.value,
            direction=invoice.direction,
            correction_of_invoice_id=invoice.correction_of_invoice_id,
            correction_of_ksef_number=invoice.correction_of_ksef_number,
            correction_reason=invoice.correction_reason,
            created_by=invoice.created_by,
            created_at=invoice.created_at,
            updated_at=invoice.updated_at,
            remaining_amount=remaining_amount,
        )


class OpenInvoicesSummary(BaseModel):
    total_receivables: Decimal
    total_payables: Decimal


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int
    page: int
    size: int
    summary: OpenInvoicesSummary | None = None


class SubmitInvoiceResponse(BaseModel):
    invoice_id: UUID
    transmission_id: UUID
    status: str
