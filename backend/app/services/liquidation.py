import logging
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.models.balance import Balance, Currency
from app.models.position import Position, PositionStatus
from app.services.price_engine import current_prices
from app.services.futures_engine import calc_unrealized_pnl
from app.database import async_session

logger = logging.getLogger(__name__)


async def check_liquidations():
    async with async_session() as db:
        result = await db.execute(
            select(Position).where(Position.status == PositionStatus.open)
        )
        positions = result.scalars().all()

        for position in positions:
            current_price = current_prices.get(position.pair)
            if not current_price:
                continue

            pnl = calc_unrealized_pnl(position.entry_price, current_price, position.quantity, position.side.value)
            position.unrealized_pnl = pnl

            if position.margin + pnl <= position.entry_price * position.quantity * settings.maintenance_margin_rate:
                logger.warning(f"Liquidating position {position.id} for user {position.user_id}")
                position.status = PositionStatus.liquidated
                position.closed_at = datetime.utcnow()

                balance_result = await db.execute(
                    select(Balance).where(Balance.user_id == position.user_id, Balance.currency == Currency.USDT)
                )
                balance = balance_result.scalar_one()
                balance.locked -= position.margin

        await db.commit()
