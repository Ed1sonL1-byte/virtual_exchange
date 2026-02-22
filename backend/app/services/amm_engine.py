from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User, UserRole
from app.models.balance import Balance, Currency
from app.models.pool import LiquidityPool, LiquidityProvision
from app.models.trade import Trade, TradeType

PAIR_BASE = {"ETHUSDT": Currency.ETH, "SOLUSDT": Currency.SOL, "BTCUSDT": Currency.BTC}


async def mint_tokens(db: AsyncSession, user: User, currency_str: str, amount: Decimal):
    if user.role != UserRole.market_maker:
        raise HTTPException(status_code=403, detail="Only market makers can mint")

    currency = Currency(currency_str.upper())
    result = await db.execute(
        select(Balance).where(Balance.user_id == user.id, Balance.currency == currency)
    )
    balance = result.scalar_one_or_none()
    if balance:
        balance.available += amount
    else:
        db.add(Balance(user_id=user.id, currency=currency, available=amount, locked=Decimal("0")))


async def add_liquidity(db: AsyncSession, user: User, pair: str, base_amount: Decimal, quote_amount: Decimal):
    if user.role != UserRole.market_maker:
        raise HTTPException(status_code=403, detail="Only market makers can add liquidity")

    pair = pair.upper()
    if pair not in PAIR_BASE:
        raise HTTPException(status_code=400, detail=f"Invalid pair: {pair}")

    base_currency = PAIR_BASE[pair]

    base_bal = await _get_balance(db, user.id, base_currency)
    quote_bal = await _get_balance(db, user.id, Currency.USDT)

    if base_bal.available < base_amount:
        raise HTTPException(status_code=400, detail=f"Insufficient {base_currency.value}")
    if quote_bal.available < quote_amount:
        raise HTTPException(status_code=400, detail="Insufficient USDT")

    base_bal.available -= base_amount
    quote_bal.available -= quote_amount

    result = await db.execute(select(LiquidityPool).where(LiquidityPool.pair == pair))
    pool = result.scalar_one_or_none()

    if pool:
        pool.reserve_base += base_amount
        pool.reserve_quote += quote_amount
        pool.k_value = pool.reserve_base * pool.reserve_quote
    else:
        pool = LiquidityPool(
            pair=pair,
            reserve_base=base_amount,
            reserve_quote=quote_amount,
            k_value=base_amount * quote_amount,
            fee_rate=Decimal(str(settings.amm_fee_rate)),
        )
        db.add(pool)
        await db.flush()

    provision = LiquidityProvision(
        user_id=user.id,
        pool_pair=pair,
        base_deposited=base_amount,
        quote_deposited=quote_amount,
    )
    db.add(provision)

    return pool


async def swap(db: AsyncSession, user_id: UUID, pair: str, side: str, amount_in: Decimal) -> dict:
    pair = pair.upper()
    if pair not in PAIR_BASE:
        raise HTTPException(status_code=400, detail=f"Invalid pair: {pair}")

    result = await db.execute(select(LiquidityPool).where(LiquidityPool.pair == pair))
    pool = result.scalar_one_or_none()
    if not pool or pool.reserve_base <= 0 or pool.reserve_quote <= 0:
        raise HTTPException(status_code=400, detail="No liquidity available")

    base_currency = PAIR_BASE[pair]
    fee = amount_in * pool.fee_rate
    amount_in_after_fee = amount_in - fee

    if side == "buy":
        amount_out = (pool.reserve_base * amount_in_after_fee) / (pool.reserve_quote + amount_in_after_fee)

        usdt_bal = await _get_balance(db, user_id, Currency.USDT)
        if usdt_bal.available < amount_in:
            raise HTTPException(status_code=400, detail="Insufficient USDT")

        usdt_bal.available -= amount_in
        base_bal = await _get_balance(db, user_id, base_currency)
        base_bal.available += amount_out

        pool.reserve_quote += amount_in
        pool.reserve_base -= amount_out
    else:
        amount_out = (pool.reserve_quote * amount_in_after_fee) / (pool.reserve_base + amount_in_after_fee)

        base_bal = await _get_balance(db, user_id, base_currency)
        if base_bal.available < amount_in:
            raise HTTPException(status_code=400, detail=f"Insufficient {base_currency.value}")

        base_bal.available -= amount_in
        usdt_bal = await _get_balance(db, user_id, Currency.USDT)
        usdt_bal.available += amount_out

        pool.reserve_base += amount_in
        pool.reserve_quote -= amount_out

    pool.k_value = pool.reserve_base * pool.reserve_quote

    trade = Trade(
        buyer_id=user_id,
        pair=pair,
        price=amount_out / amount_in if amount_in > 0 else Decimal("0"),
        quantity=amount_out,
        trade_type=TradeType.amm_swap,
    )
    db.add(trade)

    return {"amount_in": str(amount_in), "amount_out": str(amount_out), "fee": str(fee), "pair": pair, "side": side}


async def _get_balance(db: AsyncSession, user_id: UUID, currency: Currency) -> Balance:
    result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == currency)
    )
    balance = result.scalar_one_or_none()
    if not balance:
        raise HTTPException(status_code=400, detail=f"No {currency.value} balance")
    return balance
