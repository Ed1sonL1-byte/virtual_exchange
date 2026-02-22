from decimal import Decimal
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.balance import Balance, Currency
from app.models.position import Position, PositionSide, PositionStatus
from app.services.price_engine import current_prices

MMR = Decimal(str(settings.maintenance_margin_rate))


def calc_liquidation_price(entry_price: Decimal, leverage: int, side: str) -> Decimal:
    lev = Decimal(str(leverage))
    if side == "long":
        return entry_price * (1 - 1 / lev + MMR)
    else:
        return entry_price * (1 + 1 / lev - MMR)


def calc_unrealized_pnl(entry_price: Decimal, current_price: Decimal, quantity: Decimal, side: str) -> Decimal:
    if side == "long":
        return (current_price - entry_price) * quantity
    else:
        return (entry_price - current_price) * quantity


async def open_position(db: AsyncSession, user_id: UUID, pair: str, side: str, leverage: int, quantity: Decimal) -> Position:
    pair = pair.upper()
    if pair not in current_prices:
        raise HTTPException(status_code=400, detail="Price not available")
    if leverage < 1 or leverage > 125:
        raise HTTPException(status_code=400, detail="Leverage must be 1-125")

    entry_price = current_prices[pair]
    position_value = entry_price * quantity
    margin = position_value / Decimal(str(leverage))

    result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == Currency.USDT)
    )
    usdt_balance = result.scalar_one_or_none()
    if not usdt_balance or usdt_balance.available < margin:
        raise HTTPException(status_code=400, detail=f"Insufficient margin. Need {margin} USDT")

    usdt_balance.available -= margin
    usdt_balance.locked += margin

    liq_price = calc_liquidation_price(entry_price, leverage, side)

    position = Position(
        user_id=user_id,
        pair=pair,
        side=PositionSide(side),
        leverage=leverage,
        entry_price=entry_price,
        quantity=quantity,
        margin=margin,
        liquidation_price=liq_price,
        unrealized_pnl=Decimal("0"),
        status=PositionStatus.open,
    )
    db.add(position)
    return position


async def close_position(db: AsyncSession, user_id: UUID, position_id: UUID) -> Position:
    result = await db.execute(
        select(Position).where(Position.id == position_id, Position.user_id == user_id)
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.status != PositionStatus.open:
        raise HTTPException(status_code=400, detail="Position is not open")

    current_price = current_prices.get(position.pair)
    if not current_price:
        raise HTTPException(status_code=400, detail="Price not available")

    pnl = calc_unrealized_pnl(position.entry_price, current_price, position.quantity, position.side.value)

    balance_result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == Currency.USDT)
    )
    usdt_balance = balance_result.scalar_one()
    usdt_balance.locked -= position.margin
    usdt_balance.available += position.margin + pnl

    position.unrealized_pnl = pnl
    position.status = PositionStatus.closed
    position.closed_at = datetime.utcnow()

    return position
