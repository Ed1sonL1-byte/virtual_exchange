from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.order import SpotOrder, OrderStatus
from app.schemas.trading import SpotOrderRequest, SpotOrderResponse
from app.services.spot_engine import place_spot_order

router = APIRouter(prefix="/api/spot", tags=["spot"])


@router.post("/order", response_model=SpotOrderResponse)
async def create_order(data: SpotOrderRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await place_spot_order(
        db, user.id, data.pair, data.side, data.order_type,
        Decimal(str(data.quantity)), Decimal(str(data.price)) if data.price else None,
    )
    return SpotOrderResponse(
        id=str(order.id), pair=order.pair, side=order.side.value,
        order_type=order.order_type.value, price=str(order.price) if order.price else None,
        quantity=str(order.quantity), filled_quantity=str(order.filled_quantity), status=order.status.value,
    )


@router.get("/orders")
async def list_orders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SpotOrder).where(SpotOrder.user_id == user.id).order_by(SpotOrder.created_at.desc()))
    orders = result.scalars().all()
    return [{
        "id": str(o.id), "pair": o.pair, "side": o.side.value, "order_type": o.order_type.value,
        "price": str(o.price) if o.price else None, "quantity": str(o.quantity),
        "filled_quantity": str(o.filled_quantity), "status": o.status.value,
    } for o in orders]


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SpotOrder).where(SpotOrder.id == UUID(order_id), SpotOrder.user_id == user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.pending:
        raise HTTPException(status_code=400, detail="Cannot cancel non-pending order")
    order.status = OrderStatus.cancelled
    return {"status": "cancelled"}
