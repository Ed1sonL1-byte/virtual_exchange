from pydantic import BaseModel


class MintRequest(BaseModel):
    currency: str
    amount: float


class AddLiquidityRequest(BaseModel):
    pair: str
    base_amount: float
    quote_amount: float


class RemoveLiquidityRequest(BaseModel):
    pair: str


class SwapRequest(BaseModel):
    pair: str
    side: str
    amount: float


class PoolResponse(BaseModel):
    pair: str
    reserve_base: str
    reserve_quote: str
    k_value: str
    fee_rate: str
