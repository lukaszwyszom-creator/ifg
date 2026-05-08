"""Endpointy zarządzania sesją KSeF."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db_session, get_ksef_session_service, get_settings_service
from app.core.security import AuthenticatedUser
from app.schemas.ksef_session import (
    CloseSessionResponse,
    KSeFConnectionStatusResponse,
    KSeFSessionResponse,
    OpenSessionRequest,
)
from app.services.ksef_session_service import KSeFSessionService
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/ksef/session", tags=["ksef-session"])
router_status = APIRouter(prefix="/ksef", tags=["ksef-session"])

# Alias REST-owy: /ksef-sessions/  (bardziej idiomatyczny URL)
router_sessions = APIRouter(prefix="/ksef-sessions", tags=["ksef-session"])


class CloseSessionRequest(BaseModel):
    nip: str


@router_status.get("/status", response_model=KSeFConnectionStatusResponse)
def get_ksef_connection_status(
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    settings_service: Annotated[SettingsService, Depends(get_settings_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> KSeFConnectionStatusResponse:
    settings_data = settings_service.get_settings()
    payload = ksef_session_service.get_connection_status(settings_data.get("seller_nip"))
    return KSeFConnectionStatusResponse.model_validate(payload)


@router.post("/open", response_model=KSeFSessionResponse, status_code=201)
def open_session(
    body: OpenSessionRequest,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> KSeFSessionResponse:
    """Otwiera nową sesję KSeF (challenge → init token)."""
    orm = ksef_session_service.open_session(
        nip=body.nip,
        actor_user_id=current_user.user_id,
    )
    return KSeFSessionResponse.model_validate(orm)


@router_sessions.post(
    "/",
    response_model=KSeFSessionResponse,
    status_code=201,
    summary="Utwórz sesję KSeF",
    description="Inicjalizuje sesję KSeF dla podanego NIP sprzedawcy "
                "(challenge → init token). Wymaga KSEF_AUTH_TOKEN w .env.",
)
def create_session(
    body: OpenSessionRequest,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> KSeFSessionResponse:
    """POST /api/v1/ksef-sessions/ — alias dla /ksef/session/open."""
    orm = ksef_session_service.open_session(
        nip=body.nip,
        actor_user_id=current_user.user_id,
    )
    return KSeFSessionResponse.model_validate(orm)


@router_sessions.get(
    "/active",
    response_model=KSeFSessionResponse,
    summary="Aktywna sesja KSeF",
)
def get_active_session_v2(
    nip: str,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> KSeFSessionResponse:
    """GET /api/v1/ksef-sessions/active?nip=... — aktywna sesja dla NIP."""
    orm = ksef_session_service.get_active_session(nip)
    return KSeFSessionResponse.model_validate(orm)


@router_sessions.delete(
    "/",
    response_model=CloseSessionResponse,
    summary="Zamknij sesję KSeF",
)
def close_session_v2(
    nip: str,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CloseSessionResponse:
    """DELETE /api/v1/ksef-sessions/?nip=... — zamknij aktywną sesję."""
    orm = ksef_session_service.close_session(nip=nip, actor_user_id=current_user.user_id)
    return CloseSessionResponse.model_validate(orm)


@router_sessions.post(
    "/close",
    response_model=CloseSessionResponse,
    summary="Zamknij sesję KSeF (compat)",
)
def close_session_v2_post(
    body: CloseSessionRequest,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CloseSessionResponse:
    """POST /api/v1/ksef-sessions/close — alias kompatybilny dla środowisk z ograniczonym DELETE."""
    orm = ksef_session_service.close_session(nip=body.nip, actor_user_id=current_user.user_id)
    return CloseSessionResponse.model_validate(orm)


@router.delete("/close", response_model=CloseSessionResponse)
def close_session(
    nip: str,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> CloseSessionResponse:
    """Zamyka aktywną sesję KSeF dla danego NIP."""
    orm = ksef_session_service.close_session(nip=nip, actor_user_id=current_user.user_id)
    return CloseSessionResponse.model_validate(orm)


@router.get("/active", response_model=KSeFSessionResponse)
def get_active_session(
    nip: str,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> KSeFSessionResponse:
    """Zwraca aktywną sesję KSeF dla danego NIP."""
    orm = ksef_session_service.get_active_session(nip)
    return KSeFSessionResponse.model_validate(orm)


@router.get("/{session_id}", response_model=KSeFSessionResponse)
def get_session_by_id(
    session_id: UUID,
    ksef_session_service: Annotated[KSeFSessionService, Depends(get_ksef_session_service)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> KSeFSessionResponse:
    """Pobiera sesję KSeF po ID."""
    orm = ksef_session_service.get_session_by_id(session_id)
    return KSeFSessionResponse.model_validate(orm)


# ---------------------------------------------------------------------------
# SYNC PURCHASE INVOICES
# ---------------------------------------------------------------------------

class SyncPurchaseRequest(BaseModel):
    nip: str
    date_from: date
    date_to: date


class SyncPurchaseResponse(BaseModel):
    saved: int
    received: int
    skipped_existing: int
    skipped_parse: int


class SyncPurchaseJobResponse(BaseModel):
    job_id: str
    status: str  # pending | processing | done | failed


class SyncPurchaseJobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: SyncPurchaseResponse | None = None
    error: str | None = None


@router_sessions.post(
    "/sync-purchase",
    response_model=SyncPurchaseJobResponse,
    status_code=202,
    summary="Pobierz faktury zakupowe z KSeF",
    description=(
        "Pobiera faktury zakupowe (odebrane) z KSeF za podany zakres dat "
        "i zapisuje nowe do bazy. Wymaga aktywnej sesji KSeF dla podanego NIP. "
        "Operacja jest asynchroniczna — zwraca job_id do odpytywania statusu."
    ),
)
def sync_purchase_invoices(
    body: SyncPurchaseRequest,
    session: Annotated[object, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SyncPurchaseJobResponse:
    """POST /api/v1/ksef-sessions/sync-purchase — enqueue job synchronizacji faktur zakupowych."""
    from uuid import uuid4
    from datetime import UTC, datetime
    from app.persistence.models.background_job import BackgroundJob

    job = BackgroundJob(
        id=uuid4(),
        job_type="sync_purchase_invoices",
        payload_json={
            "nip": body.nip,
            "date_from": body.date_from.isoformat(),
            "date_to": body.date_to.isoformat(),
            "actor_user_id": str(current_user.user_id) if current_user.user_id else None,
        },
        status="pending",
        max_attempts=1,
    )
    session.add(job)
    session.commit()
    return SyncPurchaseJobResponse(job_id=str(job.id), status="pending")


@router_sessions.get(
    "/sync-purchase/jobs/{job_id}",
    response_model=SyncPurchaseJobStatusResponse,
    summary="Status joba synchronizacji faktur zakupowych",
)
def get_sync_purchase_job_status(
    job_id: UUID,
    session: Annotated[object, Depends(get_db_session)],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> SyncPurchaseJobStatusResponse:
    """GET /api/v1/ksef-sessions/sync-purchase/jobs/{job_id} — sprawdź status joba."""
    from app.persistence.models.background_job import BackgroundJob
    from app.core.exceptions import NotFoundError

    job = session.get(BackgroundJob, job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} nie istnieje.")

    result = None
    error = None
    if job.status == "done":
        raw = job.payload_json.get("result")
        if raw:
            result = SyncPurchaseResponse(**raw)
    elif job.status == "failed":
        error = job.last_error

    return SyncPurchaseJobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        result=result,
        error=error,
    )
