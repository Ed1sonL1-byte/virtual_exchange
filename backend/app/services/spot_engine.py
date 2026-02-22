from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.balance import Balance, Currency
from app.models.order import SpotOrder, OrderSide, OrderType, OrderStatus
from app.models.trade import Trade, TradeType
from app.services.price_engine import current_prices

PAIR_BASE = {"ETHUSDT": Currency.ETH, "SOLUSDT": Currency.SOL, "BTCUSDT": Currency.BTC}


async def get_balance(db: AsyncSession, user_id: UUID, currency: Currency) -> Balance:
    result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == currency)
    )
    balance = result.scalar_one_or_none()
    if not balance:
        raise HTTPException(status_code=400, detail=f"No {currency.value} balance found")
    return balance


async def place_spot_order(db: AsyncSession, user_id: UUID, pair: str, side: str, order_type: str, quantity: Decimal, price: Decimal | None) -> SpotOrder:
    pair = pair.upper()
    if pair not in PAIR_BASE:
        raise HTTPException(status_code=400, detail=f"Invalid pair: {pair}")

    base_currency = PAIR_BASE[pair]
    quote_currency = Currency.USDT

    if order_type == "market":
        if pair not in current_prices:
            raise HTTPException(status_code=400, detail="Price not available yet")
        exec_price = current_prices[pair]
    else:
        if price is None:
            raise HTTPException(status_code=400, detail="Price required for limit orders")
        exec_price = price

    total_cost = exec_price * quantity
    fee = total_cost * Decimal(str(settings.spot_fee_rate))

    if side == "buy":
        usdt_balance = await get_balance(db, user_id, quote_currency)
        required = total_cost + fee
        if usdt_balance.available < required:
            raise HTTPException(status_code=400, detail=f"Insufficient USDT. Need {required}, have {usdt_balance.available}")

        if order_type == "market":
            usdt_balance.available -= required
            base_balance = await get_balance(db, user_id, base_currency)
            base_balance.available += quantity
    else:
        base_balance = await get_balance(db, user_id, base_currency)
        if base_balance.available < quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient {base_currency.value}")

        if order_type == "market":
            base_balance.available -= quantity
            usdt_balance = await get_balance(db, user_id, quote_currency)
            usdt_balance.available += total_cost - fee

    order = SpotOrder(
        user_id=user_id,
        pair=pair,
        side=OrderSide(side),
        order_type=OrderType(order_type),
        price=exec_price,
        quantity=quantity,
        filled_quantity=quantity if order_type == "market" else Decimal("0"),
        status=OrderStatus.filled if order_type == "market" else OrderStatus.pending,
    )
    db.add(order)

    if order_type == "market":
        trade = Trade(
            order_id=order.id,
            buyer_id=user_id,
            seller_id=None,
            pair=pair,
            price=exec_price,
            quantity=quantity,
            trade_type=TradeType.spot,
        )
        db.add(trade)

    return order
