from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User, UserRole
from app.models.balance import Balance, Currency
from app.schemas.auth import AgentRegister, AgentRegisterResponse
from app.middleware.auth import generate_api_key

router = APIRouter(prefix="/api/sdk", tags=["sdk"])


@router.post("/agents/register", response_model=AgentRegisterResponse)
async def register_agent(data: AgentRegister, db: AsyncSession = Depends(get_db)):
    api_key = generate_api_key()
    user = User(
        username=data.name,
        api_key=api_key,
        role=UserRole.user,
        description=data.description,
    )
    db.add(user)
    await db.flush()

    for currency in Currency:
        balance = Balance(
            user_id=user.id,
            currency=currency,
            available=Decimal(str(settings.initial_balance)) if currency == Currency.USDT else Decimal("0"),
            locked=Decimal("0"),
        )
        db.add(balance)

    return AgentRegisterResponse(
        api_key=api_key,
        agent_id=str(user.id),
        initial_balance=settings.initial_balance,
    )
