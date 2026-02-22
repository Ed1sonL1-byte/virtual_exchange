from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.balance import Balance
from app.models.position import Position, PositionStatus
from app.schemas.account import BalanceResponse

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/balance", response_model=list[BalanceResponse])
async def get_balance(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Balance).where(Balance.user_id == user.id))
    balances = result.scalars().all()
    return [BalanceResponse(currency=b.currency.value, available=str(b.available), locked=str(b.locked)) for b in balances]


@router.get("/positions")
async def get_positions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.status == PositionStatus.open)
    )
    positions = result.scalars().all()
    return [{
        "id": str(p.id),
        "pair": p.pair,
        "side": p.side.value,
        "leverage": p.leverage,
        "entry_price": str(p.entry_price),
        "quantity": str(p.quantity),
        "margin": str(p.margin),
        "liquidation_price": str(p.liquidation_price),
        "unrealized_pnl": str(p.unrealized_pnl),
    } for p in positions]
