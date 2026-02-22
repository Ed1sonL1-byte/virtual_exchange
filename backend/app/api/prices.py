from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.price import PriceHistory
from app.services.price_engine import current_prices

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("")
async def get_prices():
    return {pair: str(price) for pair, price in current_prices.items()}


@router.get("/{pair}/history")
async def get_price_history(pair: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.pair == pair.upper())
        .order_by(PriceHistory.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [{"price": str(r.price), "timestamp": r.timestamp.isoformat()} for r in rows]
