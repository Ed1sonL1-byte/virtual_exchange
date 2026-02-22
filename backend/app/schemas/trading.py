from pydantic import BaseModel


class SpotOrderRequest(BaseModel):
    pair: str
    side: str
    order_type: str
    quantity: float
    price: float | None = None


class SpotOrderResponse(BaseModel):
    id: str
    pair: str
    side: str
    order_type: str
    price: str | None
    quantity: str
    filled_quantity: str
    status: str
