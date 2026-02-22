from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.position import Position, PositionStatus
from app.schemas.futures import OpenPositionRequest, PositionResponse
from app.services.futures_engine import open_position, close_position
from app.services.price_engine import current_prices
from app.services.futures_engine import calc_unrealized_pnl

router = APIRouter(prefix="/api/futures", tags=["futures"])


@router.post("/open", response_model=PositionResponse)
async def open_pos(data: OpenPositionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pos = await open_position(db, user.id, data.pair, data.side, data.leverage, Decimal(str(data.quantity)))
    return PositionResponse(
        id=str(pos.id), pair=pos.pair, side=pos.side.value, leverage=pos.leverage,
        entry_price=str(pos.entry_price), quantity=str(pos.quantity), margin=str(pos.margin),
        liquidation_price=str(pos.liquidation_price), unrealized_pnl=str(pos.unrealized_pnl), status=pos.status.value,
    )


@router.post("/close/{position_id}", response_model=PositionResponse)
async def close_pos(position_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pos = await close_position(db, user.id, UUID(position_id))
    return PositionResponse(
        id=str(pos.id), pair=pos.pair, side=pos.side.value, leverage=pos.leverage,
        entry_price=str(pos.entry_price), quantity=str(pos.quantity), margin=str(pos.margin),
        liquidation_price=str(pos.liquidation_price), unrealized_pnl=str(pos.unrealized_pnl), status=pos.status.value,
    )


@router.get("/positions")
async def list_positions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.status == PositionStatus.open)
    )
    positions = result.scalars().all()
    enriched = []
    for p in positions:
        cp = current_prices.get(p.pair)
        pnl = calc_unrealized_pnl(p.entry_price, cp, p.quantity, p.side.value) if cp else p.unrealized_pnl
        enriched.append({
            "id": str(p.id), "pair": p.pair, "side": p.side.value, "leverage": p.leverage,
            "entry_price": str(p.entry_price), "quantity": str(p.quantity), "margin": str(p.margin),
            "liquidation_price": str(p.liquidation_price), "unrealized_pnl": str(pnl), "status": p.status.value,
        })
    return enriched
