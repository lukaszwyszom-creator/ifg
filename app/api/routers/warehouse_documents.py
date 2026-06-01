from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_warehouse_document_service
from app.core.security import AuthenticatedUser
from app.schemas.warehouse_document import (
    WarehouseDocCreateRequest,
    WarehouseDocListResponse,
    WarehouseDocResponse,
    WarehouseDocUpdateRequest,
)
from app.services.warehouse_document_service import WarehouseDocumentService

router = APIRouter(prefix="/warehouse-documents", tags=["warehouse"])


@router.get("", response_model=WarehouseDocListResponse)
def list_documents(
    doc_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    svc: Annotated[WarehouseDocumentService, Depends(get_warehouse_document_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseDocListResponse:
    docs, total = svc.list_documents(
        doc_type=doc_type, status=status, limit=limit, offset=offset
    )
    return WarehouseDocListResponse(
        items=[WarehouseDocResponse.from_orm(d) for d in docs],
        total=total,
    )


@router.get("/{doc_id}", response_model=WarehouseDocResponse)
def get_document(
    doc_id: UUID,
    svc: Annotated[WarehouseDocumentService, Depends(get_warehouse_document_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseDocResponse:
    doc = svc.get_document_response(doc_id)
    return doc


@router.post("", response_model=WarehouseDocResponse, status_code=201)
def create_document(
    body: WarehouseDocCreateRequest,
    svc: Annotated[WarehouseDocumentService, Depends(get_warehouse_document_service)] = ...,
    actor: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseDocResponse:
    doc = svc.create_document(
        body.model_dump(),
        created_by=UUID(actor.user_id),
    )
    return WarehouseDocResponse.from_orm(doc)


@router.patch("/{doc_id}", response_model=WarehouseDocResponse)
def update_document(
    doc_id: UUID,
    body: WarehouseDocUpdateRequest,
    svc: Annotated[WarehouseDocumentService, Depends(get_warehouse_document_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseDocResponse:
    """Aktualizuje dokument DRAFT. Zwraca 409 dla POSTED/CANCELLED."""
    doc = svc.update_document(doc_id, body.model_dump())
    return WarehouseDocResponse.from_orm(doc)


@router.delete("/{doc_id}", status_code=204)
def cancel_document(
    doc_id: UUID,
    svc: Annotated[WarehouseDocumentService, Depends(get_warehouse_document_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> None:
    """Anuluje dokument DRAFT (soft delete — status CANCELLED). Zwraca 409 dla POSTED."""
    svc.cancel_document(doc_id)


@router.post("/{doc_id}/post", response_model=WarehouseDocResponse)
def post_document(
    doc_id: UUID,
    svc: Annotated[WarehouseDocumentService, Depends(get_warehouse_document_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseDocResponse:
    """Księguje dokument. Idempotentny — drugi call dla POSTED dokumentu jest no-op."""
    doc = svc.post_document(doc_id)
    return svc.get_document_response(doc_id)
