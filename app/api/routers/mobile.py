from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    get_current_user,
    get_invoice_service,
    get_ksef_session_service,
    get_ksef_sync_service,
    get_payment_service,
    get_settings_service,
)
from app.core.security import AuthenticatedUser
from app.schemas.mobile import (
    CreditorDetailResponse,
    CreditorsListResponse,
    DashboardResponse,
    DebtorDetailResponse,
    DebtorsListResponse,
    NotificationsResponse,
)
from app.services.invoice_service import InvoiceService
from app.services.ksef_session_service import KSeFSessionService
from app.services.ksef_sync_service import KSeFSyncService
from app.services.mobile_service import MobileService
from app.services.payment_service import PaymentService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/mobile", tags=["mobile"])


def get_mobile_service(
    invoice_service: Annotated[InvoiceService, Depends(get_invoice_service)],
    payment_service: Annotated[PaymentService, Depends(get_payment_service)],
    ksef_sync_service: Annotated[KSeFSyncService, Depends(get_ksef_sync_service)],
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
) -> MobileService:
    return MobileService(
        invoice_service=invoice_service,
        payment_service=payment_service,
        ksef_sync_service=ksef_sync_service,
        ksef_session_service=ksef_session_service,
        settings_service=settings_service,
    )


@router.get("/dashboard", response_model=DashboardResponse)
def get_mobile_dashboard(
    mobile_service: Annotated[MobileService, Depends(get_mobile_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
    period: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
) -> DashboardResponse:
    if period:
        try:
            year, month = (int(part) for part in period.split("-"))
            if month < 1 or month > 12:
                raise ValueError
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Parametr 'period' musi mieć format YYYY-MM.") from exc

    payload = mobile_service.get_dashboard(period=period)
    return DashboardResponse.model_validate(payload)


@router.get("/notifications", response_model=NotificationsResponse)
def get_mobile_notifications(
    mobile_service: Annotated[MobileService, Depends(get_mobile_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> NotificationsResponse:
    payload = mobile_service.get_notifications()
    return NotificationsResponse.model_validate(payload)


@router.get("/debtors", response_model=DebtorsListResponse)
def get_mobile_debtors(
    mobile_service: Annotated[MobileService, Depends(get_mobile_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DebtorsListResponse:
    payload = mobile_service.get_debtors()
    return DebtorsListResponse.model_validate(payload)


@router.get("/debtors/{debtor_id}", response_model=DebtorDetailResponse)
def get_mobile_debtor(
    debtor_id: UUID,
    mobile_service: Annotated[MobileService, Depends(get_mobile_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DebtorDetailResponse:
    payload = mobile_service.get_debtor(debtor_id)
    return DebtorDetailResponse.model_validate(payload)


@router.get("/creditors", response_model=CreditorsListResponse)
def get_mobile_creditors(
    mobile_service: Annotated[MobileService, Depends(get_mobile_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CreditorsListResponse:
    payload = mobile_service.get_creditors()
    return CreditorsListResponse.model_validate(payload)


@router.get("/creditors/{creditor_id}", response_model=CreditorDetailResponse)
def get_mobile_creditor(
    creditor_id: UUID,
    mobile_service: Annotated[MobileService, Depends(get_mobile_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CreditorDetailResponse:
    payload = mobile_service.get_creditor(creditor_id)
    return CreditorDetailResponse.model_validate(payload)
