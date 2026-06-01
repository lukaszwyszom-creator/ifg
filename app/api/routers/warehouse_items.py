from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_warehouse_item_service
from app.core.security import AuthenticatedUser

from app.schemas.warehouse_item import (
    WarehouseBalanceListResponse,
    WarehouseItemCreateRequest,
    WarehouseItemListResponse,
    WarehouseItemResponse,
    WarehouseItemUpdateRequest,
)
from app.services.warehouse_item_service import WarehouseItemService

router = APIRouter(prefix="/warehouse/items", tags=["warehouse"])


@router.post("", response_model=WarehouseItemResponse, status_code=201)
def create_item(
    body: WarehouseItemCreateRequest,
    svc: Annotated[WarehouseItemService, Depends(get_warehouse_item_service)],
    _: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> WarehouseItemResponse:
    item = svc.create(body)
    return WarehouseItemResponse.model_validate(item)


@router.get("", response_model=WarehouseItemListResponse)
def list_items(
    include_inactive: bool = Query(default=False),
    svc: Annotated[WarehouseItemService, Depends(get_warehouse_item_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseItemListResponse:
    items = svc.list_items(include_inactive=include_inactive)
    return WarehouseItemListResponse(
        items=[WarehouseItemResponse.model_validate(i) for i in items],
        total=len(items),
    )


@router.get("/balance", response_model=WarehouseBalanceListResponse)
def list_balance(
    svc: Annotated[WarehouseItemService, Depends(get_warehouse_item_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseBalanceListResponse:
    """Zwraca aktywne warstwy FIFO (remaining_quantity != 0)."""
    entries = svc.list_balance_layers()
    return WarehouseBalanceListResponse(items=entries, total=len(entries))


@router.get("/{item_id}", response_model=WarehouseItemResponse)
def get_item(
    item_id: UUID,
    svc: Annotated[WarehouseItemService, Depends(get_warehouse_item_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseItemResponse:
    return WarehouseItemResponse.model_validate(svc.get_by_id(item_id))


@router.patch("/{item_id}", response_model=WarehouseItemResponse)
def update_item(
    item_id: UUID,
    body: WarehouseItemUpdateRequest,
    svc: Annotated[WarehouseItemService, Depends(get_warehouse_item_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseItemResponse:
    item = svc.update(item_id, body)
    return WarehouseItemResponse.model_validate(item)


@router.patch("/{item_id}/deactivate", response_model=WarehouseItemResponse)
def deactivate_item(
    item_id: UUID,
    svc: Annotated[WarehouseItemService, Depends(get_warehouse_item_service)] = ...,
    _: Annotated[AuthenticatedUser, Depends(get_current_user)] = ...,
) -> WarehouseItemResponse:
    """Dezaktywuje pozycję (soft delete). Nie usuwa rekordu."""
    item = svc.deactivate(item_id)
    return WarehouseItemResponse.model_validate(item)
