"""Work orders router -- parity with .NET `WorkOrdersController`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from fleetwise.api.deps import SessionDep
from fleetwise.data.repositories import work_order as work_order_repo
from fleetwise.domain.dto import WorkOrderResponse
from fleetwise.domain.enums import WorkOrderStatus

router = APIRouter(prefix="/work-orders", tags=["work-orders"])


@router.get("", response_model=list[WorkOrderResponse])
async def list_work_orders(
    session: SessionDep,
    status: WorkOrderStatus | None = None,
) -> list[WorkOrderResponse]:
    work_orders = await work_order_repo.get_all(session, status=status)
    return [WorkOrderResponse.model_validate(wo) for wo in work_orders]


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(work_order_id: int, session: SessionDep) -> WorkOrderResponse:
    work_order = await work_order_repo.get_by_id(session, work_order_id)
    if work_order is None:
        raise HTTPException(status_code=404)
    return WorkOrderResponse.model_validate(work_order)
