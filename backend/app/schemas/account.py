from pydantic import BaseModel


class BalanceResponse(BaseModel):
    currency: str
    available: str
    locked: str
