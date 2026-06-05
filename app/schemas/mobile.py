from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RecentPurchaseInvoice(BaseModel):
    id: UUID
    supplier_name: str
    number: str
    amount_gross: Decimal
    issue_date: date


class DashboardResponse(BaseModel):
    period: str
    sales_net: Decimal = Field(default=Decimal("0"))
    purchase_net: Decimal = Field(default=Decimal("0"))
    vat_balance: Decimal = Field(default=Decimal("0"))
    vat_label: Literal["due", "refund"] = "due"
    debtors_count: int = 0
    debtors_total_due: Decimal = Field(default=Decimal("0"))
    debtors_overdue_due: Decimal = Field(default=Decimal("0"))
    creditors_count: int = 0
    creditors_total_due: Decimal = Field(default=Decimal("0"))
    creditors_overdue_due: Decimal = Field(default=Decimal("0"))
    unassigned_payments_count: int = 0
    unassigned_payments_total: Decimal = Field(default=Decimal("0"))
    ksef_new_invoices_count: int = 0
    ksef_last_sync_at: datetime | None = None
    ksef_connection_status: Literal["connected", "disconnected", "error"] = "disconnected"
    notifications_active_count: int = 0
    recent_purchase_invoices: list[RecentPurchaseInvoice] = Field(default_factory=list)


class NotificationItem(BaseModel):
    id: UUID
    type: Literal[
        "payment_unassigned",
        "ksef_new_invoice",
        "debtor_overdue",
        "creditor_overdue",
        "ksef_sync_error",
    ]
    title: str
    subtitle: str
    count: int = Field(ge=1)
    created_at: datetime
    target_type: str
    target_id: str | None = None


class NotificationsResponse(BaseModel):
    items: list[NotificationItem] = Field(default_factory=list)


class SettlementInvoiceItem(BaseModel):
    invoice_id: UUID
    number: str
    issue_date: date
    due_date: date | None = None
    amount_due: Decimal
    overdue_days: int | None = None


class CounterpartyListItem(BaseModel):
    id: UUID
    name: str
    total_due: Decimal
    overdue_due: Decimal
    invoices_count: int
    overdue_invoices_count: int
    last_invoice_due_date: date | None = None


class CounterpartiesListResponse(BaseModel):
    items: list[CounterpartyListItem] = Field(default_factory=list)


class CounterpartyDetailResponse(BaseModel):
    id: UUID
    name: str
    total_due: Decimal
    overdue_due: Decimal
    invoices_count: int
    overdue_invoices_count: int
    invoices: list[SettlementInvoiceItem] = Field(default_factory=list)


DebtorsListResponse = CounterpartiesListResponse
DebtorDetailResponse = CounterpartyDetailResponse
CreditorsListResponse = CounterpartiesListResponse
CreditorDetailResponse = CounterpartyDetailResponse
