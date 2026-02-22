import uuid
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def generate_api_key() -> str:
    return f"amv_{secrets.token_hex(24)}"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Depends(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Try API Key first
    if api_key:
        result = await db.execute(select(User).where(User.api_key == api_key))
        user = result.scalar_one_or_none()
        if user:
            return user

    # Try JWT
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
                user = result.scalar_one_or_none()
                if user:
                    return user
        except JWTError:
            pass

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
