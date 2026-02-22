from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User, UserRole
from app.models.balance import Balance, Currency
from app.schemas.auth import UserRegister, UserLogin, TokenResponse
from app.middleware.auth import hash_password, verify_password, create_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def create_initial_balances(db: AsyncSession, user_id):
    for currency in Currency:
        balance = Balance(
            user_id=user_id,
            currency=currency,
            available=Decimal(str(settings.initial_balance)) if currency == Currency.USDT else Decimal("0"),
            locked=Decimal("0"),
        )
        db.add(balance)


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=data.username, password_hash=hash_password(data.password), role=UserRole.user)
    db.add(user)
    await db.flush()
    await create_initial_balances(db, user.id)
    return TokenResponse(access_token=create_token(str(user.id)))


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(access_token=create_token(str(user.id)))
