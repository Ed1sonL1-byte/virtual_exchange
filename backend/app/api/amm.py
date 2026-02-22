from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.pool import LiquidityPool
from app.schemas.amm import MintRequest, AddLiquidityRequest, SwapRequest, PoolResponse
from app.services.amm_engine import mint_tokens, add_liquidity, swap

router = APIRouter(prefix="/api/amm", tags=["amm"])


@router.post("/mint")
async def mint(data: MintRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await mint_tokens(db, user, data.currency, Decimal(str(data.amount)))
    return {"status": "minted", "currency": data.currency, "amount": data.amount}


@router.post("/add-liquidity")
async def add_liq(data: AddLiquidityRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pool = await add_liquidity(db, user, data.pair, Decimal(str(data.base_amount)), Decimal(str(data.quote_amount)))
    return {"status": "added", "pair": data.pair, "reserve_base": str(pool.reserve_base), "reserve_quote": str(pool.reserve_quote)}


@router.post("/swap")
async def do_swap(data: SwapRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await swap(db, user.id, data.pair, data.side, Decimal(str(data.amount)))
    return result


@router.get("/pools")
async def list_pools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LiquidityPool))
    pools = result.scalars().all()
    return [PoolResponse(
        pair=p.pair, reserve_base=str(p.reserve_base), reserve_quote=str(p.reserve_quote),
        k_value=str(p.k_value), fee_rate=str(p.fee_rate),
    ) for p in pools]
