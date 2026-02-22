from pydantic import BaseModel


class OpenPositionRequest(BaseModel):
    pair: str
    side: str
    leverage: int
    quantity: float


class PositionResponse(BaseModel):
    id: str
    pair: str
    side: str
    leverage: int
    entry_price: str
    quantity: str
    margin: str
    liquidation_price: str
    unrealized_pnl: str
    status: str
