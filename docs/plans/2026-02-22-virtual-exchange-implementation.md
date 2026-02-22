# Virtual Exchange Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a virtual trading exchange where AI agents and human users can trade ETHUSDT, SOLUSDT, BTCUSDT with spot trading, perpetual futures (1-125x leverage), and AMM liquidity pools.

**Architecture:** Single FastAPI monolith with PostgreSQL. Price Engine fetches from Binance every 2 min and broadcasts via WebSocket. Spot engine handles market/limit orders. Futures engine manages perpetual positions with liquidation. AMM engine uses Uniswap V2 (x*y=k). React frontend for human users.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / Alembic / PostgreSQL / React / TypeScript / Vite

**Design Doc:** `docs/plans/2026-02-22-virtual-exchange-design.md`

---

## Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `.gitignore`

**Step 1: Create .gitignore**

```gitignore
__pycache__/
*.py[cod]
.env
*.db
.venv/
venv/
node_modules/
dist/
.DS_Store
alembic/versions/*.pyc
```

**Step 2: Create backend/requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
pydantic==2.10.4
pydantic-settings==2.7.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.28.1
python-multipart==0.0.20
websockets==14.2
```

**Step 3: Create backend/app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_metaverse"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    binance_base_url: str = "https://api.binance.com"
    price_update_interval: int = 120  # seconds
    initial_balance: float = 10000.0  # USDT for new users
    spot_fee_rate: float = 0.001  # 0.1%
    amm_fee_rate: float = 0.003  # 0.3%
    maintenance_margin_rate: float = 0.005  # 0.5%
    funding_rate: float = 0.0001  # 0.01%

    class Config:
        env_file = ".env"


settings = Settings()
```

**Step 4: Create backend/app/main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(title="Agent Metaverse Virtual Exchange", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 5: Create backend/.env.example**

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agent_metaverse
JWT_SECRET=change-me-in-production
```

**Step 6: Set up Python venv and install dependencies**

Run:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Step 7: Verify server starts**

Run: `cd backend && uvicorn app.main:app --reload --port 8000`
Expected: Server starts, `GET http://localhost:8000/health` returns `{"status": "ok"}`

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with FastAPI, config, and dependencies"
```

---

## Task 2: Database Setup & SQLAlchemy Models

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/balance.py`
- Create: `backend/app/models/order.py`
- Create: `backend/app/models/position.py`
- Create: `backend/app/models/pool.py`
- Create: `backend/app/models/trade.py`
- Create: `backend/app/models/price.py`

**Step 1: Create backend/app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**Step 2: Create backend/app/models/user.py**

```python
import uuid
import enum
from datetime import datetime

from sqlalchemy import String, Enum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    market_maker = "market_maker"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)  # null for agents
    api_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    balances = relationship("Balance", back_populates="user")
```

**Step 3: Create backend/app/models/balance.py**

```python
import uuid
import enum
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Currency(str, enum.Enum):
    USDT = "USDT"
    ETH = "ETH"
    SOL = "SOL"
    BTC = "BTC"


class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    currency: Mapped[Currency] = mapped_column(Enum(Currency), nullable=False)
    available: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    locked: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))

    user = relationship("User", back_populates="balances")
```

**Step 4: Create backend/app/models/order.py**

```python
import uuid
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Enum, ForeignKey, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OrderSide(str, enum.Enum):
    buy = "buy"
    sell = "sell"


class OrderType(str, enum.Enum):
    market = "market"
    limit = "limit"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    filled = "filled"
    partially_filled = "partially_filled"
    cancelled = "cancelled"


class SpotOrder(Base):
    __tablename__ = "spot_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

**Step 5: Create backend/app/models/position.py**

```python
import uuid
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Enum, Integer, ForeignKey, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PositionSide(str, enum.Enum):
    long = "long"
    short = "short"


class PositionStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    liquidated = "liquidated"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[PositionSide] = mapped_column(Enum(PositionSide), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    margin: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    liquidation_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    status: Mapped[PositionStatus] = mapped_column(Enum(PositionStatus), default=PositionStatus.open)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

**Step 6: Create backend/app/models/pool.py**

```python
import uuid
from decimal import Decimal

from sqlalchemy import String, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LiquidityPool(Base):
    __tablename__ = "liquidity_pools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pair: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    reserve_base: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    reserve_quote: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    k_value: Mapped[Decimal] = mapped_column(Numeric(40, 16), default=Decimal("0"))
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.003"))


class LiquidityProvision(Base):
    __tablename__ = "liquidity_provisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pool_pair: Mapped[str] = mapped_column(String(20), nullable=False)
    share_percentage: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0"))
    base_deposited: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    quote_deposited: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
```

**Step 7: Create backend/app/models/trade.py**

```python
import uuid
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Enum, ForeignKey, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TradeType(str, enum.Enum):
    spot = "spot"
    futures = "futures"
    amm_swap = "amm_swap"


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    buyer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    pair: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    trade_type: Mapped[TradeType] = mapped_column(Enum(TradeType), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

**Step 8: Create backend/app/models/price.py**

```python
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Integer, String, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
```

**Step 9: Create backend/app/models/__init__.py**

```python
from app.models.user import User, UserRole
from app.models.balance import Balance, Currency
from app.models.order import SpotOrder, OrderSide, OrderType, OrderStatus
from app.models.position import Position, PositionSide, PositionStatus
from app.models.pool import LiquidityPool, LiquidityProvision
from app.models.trade import Trade, TradeType
from app.models.price import PriceHistory

__all__ = [
    "User", "UserRole",
    "Balance", "Currency",
    "SpotOrder", "OrderSide", "OrderType", "OrderStatus",
    "Position", "PositionSide", "PositionStatus",
    "LiquidityPool", "LiquidityProvision",
    "Trade", "TradeType",
    "PriceHistory",
]
```

**Step 10: Set up Alembic for migrations**

Run:
```bash
cd backend
source .venv/bin/activate
alembic init alembic
```

Then edit `alembic/env.py` to import models and use async engine. Edit `alembic.ini` to use `DATABASE_URL` from env.

**Step 11: Create and run initial migration**

Run:
```bash
createdb agent_metaverse  # or ensure PostgreSQL is running with this DB
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

**Step 12: Commit**

```bash
git add -A
git commit -m "feat: database setup with SQLAlchemy models and Alembic migrations"
```

---

## Task 3: Auth System (JWT + API Key)

**Files:**
- Create: `backend/app/middleware/auth.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/app/api/sdk.py`
- Modify: `backend/app/main.py` (register routers)
- Create: `backend/tests/test_auth.py`

**Step 1: Create backend/app/schemas/auth.py**

```python
from pydantic import BaseModel


class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AgentRegister(BaseModel):
    name: str
    description: str = ""


class AgentRegisterResponse(BaseModel):
    api_key: str
    agent_id: str
    initial_balance: float
    currency: str = "USDT"
```

**Step 2: Create backend/app/middleware/auth.py**

```python
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
```

**Step 3: Create backend/app/api/auth.py**

```python
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
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
```

**Step 4: Create backend/app/api/sdk.py**

```python
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
```

**Step 5: Create backend/app/api/__init__.py and register routers in main.py**

Update `backend/app/main.py` to include:
```python
from app.api.auth import router as auth_router
from app.api.sdk import router as sdk_router

app.include_router(auth_router)
app.include_router(sdk_router)
```

**Step 6: Write test for auth**

Create `backend/tests/test_auth.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_agent_register():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/sdk/agents/register", json={"name": "TestBot", "description": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "api_key" in data
        assert data["initial_balance"] == 10000.0
```

**Step 7: Run test**

Run: `cd backend && python -m pytest tests/test_auth.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: auth system with JWT for web users and API key for agents"
```

---

## Task 4: Price Engine & WebSocket Broadcast

**Files:**
- Create: `backend/app/services/price_engine.py`
- Create: `backend/app/websocket/__init__.py`
- Create: `backend/app/websocket/broadcaster.py`
- Create: `backend/app/api/prices.py`
- Modify: `backend/app/main.py` (add startup task, register router)

**Step 1: Create backend/app/websocket/broadcaster.py**

```python
import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket):
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)

    def disconnect(self, channel: str, websocket: WebSocket):
        if channel in self.active_connections:
            self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, data: dict):
        if channel not in self.active_connections:
            return
        disconnected = []
        for ws in self.active_connections[channel]:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.active_connections[channel].remove(ws)


manager = ConnectionManager()
```

**Step 2: Create backend/app/services/price_engine.py**

```python
import asyncio
import logging
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.price import PriceHistory
from app.websocket.broadcaster import manager

logger = logging.getLogger(__name__)

TRADING_PAIRS = ["ETHUSDT", "SOLUSDT", "BTCUSDT"]

# In-memory latest prices
current_prices: dict[str, Decimal] = {}


async def fetch_binance_prices() -> dict[str, Decimal]:
    prices = {}
    async with httpx.AsyncClient() as client:
        for pair in TRADING_PAIRS:
            try:
                resp = await client.get(f"{settings.binance_base_url}/api/v3/ticker/price", params={"symbol": pair})
                resp.raise_for_status()
                data = resp.json()
                prices[pair] = Decimal(data["price"])
            except Exception as e:
                logger.error(f"Failed to fetch {pair}: {e}")
                if pair in current_prices:
                    prices[pair] = current_prices[pair]
    return prices


async def save_prices(prices: dict[str, Decimal]):
    async with async_session() as db:
        for pair, price in prices.items():
            db.add(PriceHistory(pair=pair, price=price))
        await db.commit()


async def price_update_loop():
    while True:
        try:
            prices = await fetch_binance_prices()
            if prices:
                current_prices.update(prices)
                await save_prices(prices)
                await manager.broadcast("prices", {
                    "type": "price_update",
                    "data": {pair: str(price) for pair, price in prices.items()},
                })
                logger.info(f"Price update: {prices}")
        except Exception as e:
            logger.error(f"Price update error: {e}")
        await asyncio.sleep(settings.price_update_interval)
```

**Step 3: Create backend/app/api/prices.py**

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.price import PriceHistory
from app.services.price_engine import current_prices
from app.websocket.broadcaster import manager

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("")
async def get_prices():
    return {pair: str(price) for pair, price in current_prices.items()}


@router.get("/{pair}/history")
async def get_price_history(pair: str, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.pair == pair.upper())
        .order_by(PriceHistory.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [{"price": str(r.price), "timestamp": r.timestamp.isoformat()} for r in rows]
```

**Step 4: Add WebSocket endpoint for prices**

Add to `backend/app/api/prices.py`:
```python
@router.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    await manager.connect("prices", websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect("prices", websocket)
```

Note: The WebSocket route needs to be mounted at the app level. Add in main.py:
```python
from app.api.prices import router as prices_router
app.include_router(prices_router)

# WebSocket at root level
from app.websocket.broadcaster import manager
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    await manager.connect("prices", websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("prices", websocket)
```

**Step 5: Start price engine on app startup**

Update `main.py` lifespan:
```python
import asyncio
from app.services.price_engine import price_update_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(price_update_loop())
    yield
    task.cancel()
```

**Step 6: Test price endpoint**

Run server and verify: `curl http://localhost:8000/api/prices`
Expected: Returns current prices after first fetch cycle.

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: price engine with Binance API polling and WebSocket broadcast"
```

---

## Task 5: Account & Balance API

**Files:**
- Create: `backend/app/schemas/account.py`
- Create: `backend/app/api/account.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Create backend/app/schemas/account.py**

```python
from pydantic import BaseModel


class BalanceResponse(BaseModel):
    currency: str
    available: str
    locked: str
```

**Step 2: Create backend/app/api/account.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.balance import Balance
from app.models.position import Position, PositionStatus
from app.schemas.account import BalanceResponse

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/balance", response_model=list[BalanceResponse])
async def get_balance(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Balance).where(Balance.user_id == user.id))
    balances = result.scalars().all()
    return [BalanceResponse(currency=b.currency.value, available=str(b.available), locked=str(b.locked)) for b in balances]


@router.get("/positions")
async def get_positions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.status == PositionStatus.open)
    )
    positions = result.scalars().all()
    return [{
        "id": str(p.id),
        "pair": p.pair,
        "side": p.side.value,
        "leverage": p.leverage,
        "entry_price": str(p.entry_price),
        "quantity": str(p.quantity),
        "margin": str(p.margin),
        "liquidation_price": str(p.liquidation_price),
        "unrealized_pnl": str(p.unrealized_pnl),
    } for p in positions]
```

**Step 3: Register router in main.py**

```python
from app.api.account import router as account_router
app.include_router(account_router)
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: account balance and positions API endpoints"
```

---

## Task 6: Spot Trading Engine

**Files:**
- Create: `backend/app/schemas/trading.py`
- Create: `backend/app/services/spot_engine.py`
- Create: `backend/app/api/spot.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Create backend/app/schemas/trading.py**

```python
from decimal import Decimal
from pydantic import BaseModel


class SpotOrderRequest(BaseModel):
    pair: str  # ETHUSDT, SOLUSDT, BTCUSDT
    side: str  # buy, sell
    order_type: str  # market, limit
    quantity: float
    price: float | None = None  # required for limit orders


class SpotOrderResponse(BaseModel):
    id: str
    pair: str
    side: str
    order_type: str
    price: str | None
    quantity: str
    filled_quantity: str
    status: str
```

**Step 2: Create backend/app/services/spot_engine.py**

```python
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
    else:  # sell
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
            buyer_id=user_id if side == "buy" else user_id,
            seller_id=None,
            pair=pair,
            price=exec_price,
            quantity=quantity,
            trade_type=TradeType.spot,
        )
        db.add(trade)

    return order
```

**Step 3: Create backend/app/api/spot.py**

```python
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.order import SpotOrder, OrderStatus
from app.schemas.trading import SpotOrderRequest, SpotOrderResponse
from app.services.spot_engine import place_spot_order

router = APIRouter(prefix="/api/spot", tags=["spot"])


@router.post("/order", response_model=SpotOrderResponse)
async def create_order(data: SpotOrderRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await place_spot_order(
        db, user.id, data.pair, data.side, data.order_type,
        Decimal(str(data.quantity)), Decimal(str(data.price)) if data.price else None,
    )
    return SpotOrderResponse(
        id=str(order.id), pair=order.pair, side=order.side.value,
        order_type=order.order_type.value, price=str(order.price) if order.price else None,
        quantity=str(order.quantity), filled_quantity=str(order.filled_quantity), status=order.status.value,
    )


@router.get("/orders")
async def list_orders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SpotOrder).where(SpotOrder.user_id == user.id).order_by(SpotOrder.created_at.desc()))
    orders = result.scalars().all()
    return [{
        "id": str(o.id), "pair": o.pair, "side": o.side.value, "order_type": o.order_type.value,
        "price": str(o.price) if o.price else None, "quantity": str(o.quantity),
        "filled_quantity": str(o.filled_quantity), "status": o.status.value,
    } for o in orders]


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SpotOrder).where(SpotOrder.id == UUID(order_id), SpotOrder.user_id == user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.pending:
        raise HTTPException(status_code=400, detail="Cannot cancel non-pending order")
    order.status = OrderStatus.cancelled
    return {"status": "cancelled"}
```

**Step 4: Register router in main.py**

```python
from app.api.spot import router as spot_router
app.include_router(spot_router)
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: spot trading engine with market/limit orders"
```

---

## Task 7: Perpetual Futures Engine

**Files:**
- Create: `backend/app/schemas/futures.py`
- Create: `backend/app/services/futures_engine.py`
- Create: `backend/app/services/liquidation.py`
- Create: `backend/app/api/futures.py`
- Modify: `backend/app/main.py` (register router, add liquidation to price loop)

**Step 1: Create backend/app/schemas/futures.py**

```python
from pydantic import BaseModel


class OpenPositionRequest(BaseModel):
    pair: str
    side: str  # long, short
    leverage: int  # 1-125
    quantity: float


class ClosePositionRequest(BaseModel):
    pass  # close by position ID in URL


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
```

**Step 2: Create backend/app/services/futures_engine.py**

```python
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.balance import Balance, Currency
from app.models.position import Position, PositionSide, PositionStatus
from app.services.price_engine import current_prices

MMR = Decimal(str(settings.maintenance_margin_rate))


def calc_liquidation_price(entry_price: Decimal, leverage: int, side: str) -> Decimal:
    lev = Decimal(str(leverage))
    if side == "long":
        return entry_price * (1 - 1 / lev + MMR)
    else:
        return entry_price * (1 + 1 / lev - MMR)


def calc_unrealized_pnl(entry_price: Decimal, current_price: Decimal, quantity: Decimal, side: str) -> Decimal:
    if side == "long":
        return (current_price - entry_price) * quantity
    else:
        return (entry_price - current_price) * quantity


async def open_position(db: AsyncSession, user_id: UUID, pair: str, side: str, leverage: int, quantity: Decimal) -> Position:
    pair = pair.upper()
    if pair not in current_prices:
        raise HTTPException(status_code=400, detail="Price not available")
    if leverage < 1 or leverage > 125:
        raise HTTPException(status_code=400, detail="Leverage must be 1-125")

    entry_price = current_prices[pair]
    position_value = entry_price * quantity
    margin = position_value / Decimal(str(leverage))

    # Check USDT balance
    result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == Currency.USDT)
    )
    usdt_balance = result.scalar_one_or_none()
    if not usdt_balance or usdt_balance.available < margin:
        raise HTTPException(status_code=400, detail=f"Insufficient margin. Need {margin} USDT")

    usdt_balance.available -= margin
    usdt_balance.locked += margin

    liq_price = calc_liquidation_price(entry_price, leverage, side)

    position = Position(
        user_id=user_id,
        pair=pair,
        side=PositionSide(side),
        leverage=leverage,
        entry_price=entry_price,
        quantity=quantity,
        margin=margin,
        liquidation_price=liq_price,
        unrealized_pnl=Decimal("0"),
        status=PositionStatus.open,
    )
    db.add(position)
    return position


async def close_position(db: AsyncSession, user_id: UUID, position_id: UUID) -> Position:
    result = await db.execute(
        select(Position).where(Position.id == position_id, Position.user_id == user_id)
    )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.status != PositionStatus.open:
        raise HTTPException(status_code=400, detail="Position is not open")

    current_price = current_prices.get(position.pair)
    if not current_price:
        raise HTTPException(status_code=400, detail="Price not available")

    pnl = calc_unrealized_pnl(position.entry_price, current_price, position.quantity, position.side.value)

    # Return margin + PnL to available balance
    balance_result = await db.execute(
        select(Balance).where(Balance.user_id == user_id, Balance.currency == Currency.USDT)
    )
    usdt_balance = balance_result.scalar_one()
    usdt_balance.locked -= position.margin
    usdt_balance.available += position.margin + pnl

    position.unrealized_pnl = pnl
    position.status = PositionStatus.closed
    from datetime import datetime
    position.closed_at = datetime.utcnow()

    return position
```

**Step 3: Create backend/app/services/liquidation.py**

```python
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.balance import Balance, Currency
from app.models.position import Position, PositionStatus
from app.services.price_engine import current_prices
from app.services.futures_engine import calc_unrealized_pnl
from app.database import async_session

logger = logging.getLogger(__name__)


async def check_liquidations():
    async with async_session() as db:
        result = await db.execute(
            select(Position).where(Position.status == PositionStatus.open)
        )
        positions = result.scalars().all()

        for position in positions:
            current_price = current_prices.get(position.pair)
            if not current_price:
                continue

            pnl = calc_unrealized_pnl(position.entry_price, current_price, position.quantity, position.side.value)
            position.unrealized_pnl = pnl

            # Check liquidation
            if position.margin + pnl <= position.entry_price * position.quantity * settings.maintenance_margin_rate:
                logger.warning(f"Liquidating position {position.id} for user {position.user_id}")
                position.status = PositionStatus.liquidated
                position.closed_at = datetime.utcnow()

                # Margin is lost
                balance_result = await db.execute(
                    select(Balance).where(Balance.user_id == position.user_id, Balance.currency == Currency.USDT)
                )
                balance = balance_result.scalar_one()
                balance.locked -= position.margin

        await db.commit()
```

**Step 4: Create backend/app/api/futures.py**

```python
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.position import Position, PositionStatus
from app.schemas.futures import OpenPositionRequest, PositionResponse
from app.services.futures_engine import open_position, close_position
from app.services.price_engine import current_prices
from app.services.futures_engine import calc_unrealized_pnl

router = APIRouter(prefix="/api/futures", tags=["futures"])


@router.post("/open", response_model=PositionResponse)
async def open_pos(data: OpenPositionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pos = await open_position(db, user.id, data.pair, data.side, data.leverage, Decimal(str(data.quantity)))
    return PositionResponse(
        id=str(pos.id), pair=pos.pair, side=pos.side.value, leverage=pos.leverage,
        entry_price=str(pos.entry_price), quantity=str(pos.quantity), margin=str(pos.margin),
        liquidation_price=str(pos.liquidation_price), unrealized_pnl=str(pos.unrealized_pnl), status=pos.status.value,
    )


@router.post("/close/{position_id}", response_model=PositionResponse)
async def close_pos(position_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    pos = await close_position(db, user.id, UUID(position_id))
    return PositionResponse(
        id=str(pos.id), pair=pos.pair, side=pos.side.value, leverage=pos.leverage,
        entry_price=str(pos.entry_price), quantity=str(pos.quantity), margin=str(pos.margin),
        liquidation_price=str(pos.liquidation_price), unrealized_pnl=str(pos.unrealized_pnl), status=pos.status.value,
    )


@router.get("/positions")
async def list_positions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Position).where(Position.user_id == user.id, Position.status == PositionStatus.open)
    )
    positions = result.scalars().all()
    enriched = []
    for p in positions:
        cp = current_prices.get(p.pair)
        pnl = calc_unrealized_pnl(p.entry_price, cp, p.quantity, p.side.value) if cp else p.unrealized_pnl
        enriched.append({
            "id": str(p.id), "pair": p.pair, "side": p.side.value, "leverage": p.leverage,
            "entry_price": str(p.entry_price), "quantity": str(p.quantity), "margin": str(p.margin),
            "liquidation_price": str(p.liquidation_price), "unrealized_pnl": str(pnl), "status": p.status.value,
        })
    return enriched
```

**Step 5: Integrate liquidation into price update loop**

Update `backend/app/services/price_engine.py` `price_update_loop`:
```python
from app.services.liquidation import check_liquidations

# After broadcasting prices, add:
await check_liquidations()
```

**Step 6: Register router in main.py**

```python
from app.api.futures import router as futures_router
app.include_router(futures_router)
```

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: perpetual futures engine with liquidation system"
```

---

## Task 8: AMM Engine (Uniswap V2)

**Files:**
- Create: `backend/app/schemas/amm.py`
- Create: `backend/app/services/amm_engine.py`
- Create: `backend/app/api/amm.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Create backend/app/schemas/amm.py**

```python
from pydantic import BaseModel


class MintRequest(BaseModel):
    currency: str  # ETH, SOL, BTC, USDT
    amount: float


class AddLiquidityRequest(BaseModel):
    pair: str  # ETHUSDT, SOLUSDT, BTCUSDT
    base_amount: float
    quote_amount: float


class RemoveLiquidityRequest(BaseModel):
    pair: str


class SwapRequest(BaseModel):
    pair: str
    side: str  # buy or sell (buy = USDT->base, sell = base->USDT)
    amount: float  # amount of input token


class PoolResponse(BaseModel):
    pair: str
    reserve_base: str
    reserve_quote: str
    k_value: str
    fee_rate: str
```

**Step 2: Create backend/app/services/amm_engine.py**

```python
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

    # Check balances
    base_bal = await _get_balance(db, user.id, base_currency)
    quote_bal = await _get_balance(db, user.id, Currency.USDT)

    if base_bal.available < base_amount:
        raise HTTPException(status_code=400, detail=f"Insufficient {base_currency.value}")
    if quote_bal.available < quote_amount:
        raise HTTPException(status_code=400, detail="Insufficient USDT")

    # Deduct from balances
    base_bal.available -= base_amount
    quote_bal.available -= quote_amount

    # Get or create pool
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

    # Record provision
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

    if side == "buy":  # USDT -> base token
        # x * y = k => new_quote * new_base = k
        amount_out = (pool.reserve_base * amount_in_after_fee) / (pool.reserve_quote + amount_in_after_fee)

        usdt_bal = await _get_balance(db, user_id, Currency.USDT)
        if usdt_bal.available < amount_in:
            raise HTTPException(status_code=400, detail="Insufficient USDT")

        usdt_bal.available -= amount_in
        base_bal = await _get_balance(db, user_id, base_currency)
        base_bal.available += amount_out

        pool.reserve_quote += amount_in
        pool.reserve_base -= amount_out
    else:  # base token -> USDT
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
```

**Step 3: Create backend/app/api/amm.py**

```python
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
```

**Step 4: Register router in main.py**

```python
from app.api.amm import router as amm_router
app.include_router(amm_router)
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: AMM engine with Uniswap V2 model, minting, and liquidity management"
```

---

## Task 9: Frontend Setup (React + Vite)

**Files:**
- Create: `frontend/` (scaffolded by Vite)
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/services/websocket.ts`

**Step 1: Scaffold React project**

Run:
```bash
cd /Users/edisonli/Desktop/Agent_metaverse
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install axios react-router-dom
```

**Step 2: Create frontend/src/services/api.ts**

```typescript
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authApi = {
  register: (username: string, password: string) =>
    api.post("/api/auth/register", { username, password }),
  login: (username: string, password: string) =>
    api.post("/api/auth/login", { username, password }),
};

export const accountApi = {
  getBalance: () => api.get("/api/account/balance"),
  getPositions: () => api.get("/api/account/positions"),
};

export const priceApi = {
  getPrices: () => api.get("/api/prices"),
};

export const spotApi = {
  placeOrder: (pair: string, side: string, order_type: string, quantity: number, price?: number) =>
    api.post("/api/spot/order", { pair, side, order_type, quantity, price }),
  getOrders: () => api.get("/api/spot/orders"),
  cancelOrder: (id: string) => api.delete(`/api/spot/orders/${id}`),
};

export const futuresApi = {
  openPosition: (pair: string, side: string, leverage: number, quantity: number) =>
    api.post("/api/futures/open", { pair, side, leverage, quantity }),
  closePosition: (id: string) => api.post(`/api/futures/close/${id}`),
  getPositions: () => api.get("/api/futures/positions"),
};

export const ammApi = {
  getPools: () => api.get("/api/amm/pools"),
  swap: (pair: string, side: string, amount: number) =>
    api.post("/api/amm/swap", { pair, side, amount }),
};

export default api;
```

**Step 3: Create frontend/src/services/websocket.ts**

```typescript
const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";

export function connectPriceWebSocket(onMessage: (data: any) => void): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/prices`);
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };
  ws.onclose = () => {
    setTimeout(() => connectPriceWebSocket(onMessage), 5000);
  };
  return ws;
}
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: React frontend scaffolding with API client and WebSocket service"
```

---

## Task 10: Frontend Pages (Dashboard, Trading, Account)

**Files:**
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/SpotTrading.tsx`
- Create: `frontend/src/pages/FuturesTrading.tsx`
- Create: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create Login page**

```typescript
// frontend/src/pages/Login.tsx
import { useState } from "react";
import { authApi } from "../services/api";

export default function Login({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const fn = isRegister ? authApi.register : authApi.login;
    const { data } = await fn(username, password);
    localStorage.setItem("token", data.access_token);
    onLogin();
  };

  return (
    <div style={{ maxWidth: 400, margin: "100px auto", padding: 20 }}>
      <h2>{isRegister ? "Register" : "Login"}</h2>
      <form onSubmit={handleSubmit}>
        <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit">{isRegister ? "Register" : "Login"}</button>
      </form>
      <button onClick={() => setIsRegister(!isRegister)}>
        {isRegister ? "Already have an account? Login" : "Need an account? Register"}
      </button>
    </div>
  );
}
```

**Step 2: Create Dashboard page**

```typescript
// frontend/src/pages/Dashboard.tsx
import { useEffect, useState } from "react";
import { priceApi, accountApi } from "../services/api";
import { connectPriceWebSocket } from "../services/websocket";

export default function Dashboard() {
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [balances, setBalances] = useState<any[]>([]);

  useEffect(() => {
    priceApi.getPrices().then(({ data }) => setPrices(data));
    accountApi.getBalance().then(({ data }) => setBalances(data));

    const ws = connectPriceWebSocket((msg) => {
      if (msg.type === "price_update") setPrices(msg.data);
    });
    return () => ws.close();
  }, []);

  return (
    <div style={{ padding: 20 }}>
      <h2>Market Prices</h2>
      <table>
        <thead><tr><th>Pair</th><th>Price (USDT)</th></tr></thead>
        <tbody>
          {Object.entries(prices).map(([pair, price]) => (
            <tr key={pair}><td>{pair}</td><td>{price}</td></tr>
          ))}
        </tbody>
      </table>
      <h2>Balances</h2>
      <table>
        <thead><tr><th>Currency</th><th>Available</th><th>Locked</th></tr></thead>
        <tbody>
          {balances.map((b) => (
            <tr key={b.currency}><td>{b.currency}</td><td>{b.available}</td><td>{b.locked}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Step 3: Create SpotTrading page**

```typescript
// frontend/src/pages/SpotTrading.tsx
import { useState, useEffect } from "react";
import { spotApi, priceApi } from "../services/api";

export default function SpotTrading() {
  const [pair, setPair] = useState("BTCUSDT");
  const [side, setSide] = useState("buy");
  const [quantity, setQuantity] = useState("");
  const [orders, setOrders] = useState<any[]>([]);
  const [prices, setPrices] = useState<Record<string, string>>({});

  useEffect(() => {
    spotApi.getOrders().then(({ data }) => setOrders(data));
    priceApi.getPrices().then(({ data }) => setPrices(data));
  }, []);

  const handleOrder = async () => {
    await spotApi.placeOrder(pair, side, "market", parseFloat(quantity));
    spotApi.getOrders().then(({ data }) => setOrders(data));
    setQuantity("");
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Spot Trading</h2>
      <p>Current Price: {prices[pair] || "Loading..."}</p>
      <select value={pair} onChange={(e) => setPair(e.target.value)}>
        <option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option>
      </select>
      <select value={side} onChange={(e) => setSide(e.target.value)}>
        <option value="buy">Buy</option><option value="sell">Sell</option>
      </select>
      <input placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <button onClick={handleOrder}>Place Order</button>

      <h3>Orders</h3>
      <table>
        <thead><tr><th>Pair</th><th>Side</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}><td>{o.pair}</td><td>{o.side}</td><td>{o.quantity}</td><td>{o.price}</td><td>{o.status}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Step 4: Create FuturesTrading page**

```typescript
// frontend/src/pages/FuturesTrading.tsx
import { useState, useEffect } from "react";
import { futuresApi, priceApi } from "../services/api";

export default function FuturesTrading() {
  const [pair, setPair] = useState("BTCUSDT");
  const [side, setSide] = useState("long");
  const [leverage, setLeverage] = useState(10);
  const [quantity, setQuantity] = useState("");
  const [positions, setPositions] = useState<any[]>([]);
  const [prices, setPrices] = useState<Record<string, string>>({});

  useEffect(() => {
    futuresApi.getPositions().then(({ data }) => setPositions(data));
    priceApi.getPrices().then(({ data }) => setPrices(data));
  }, []);

  const handleOpen = async () => {
    await futuresApi.openPosition(pair, side, leverage, parseFloat(quantity));
    futuresApi.getPositions().then(({ data }) => setPositions(data));
    setQuantity("");
  };

  const handleClose = async (id: string) => {
    await futuresApi.closePosition(id);
    futuresApi.getPositions().then(({ data }) => setPositions(data));
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Futures Trading</h2>
      <p>Current Price: {prices[pair] || "Loading..."}</p>
      <select value={pair} onChange={(e) => setPair(e.target.value)}>
        <option>BTCUSDT</option><option>ETHUSDT</option><option>SOLUSDT</option>
      </select>
      <select value={side} onChange={(e) => setSide(e.target.value)}>
        <option value="long">Long</option><option value="short">Short</option>
      </select>
      <input type="number" min={1} max={125} value={leverage} onChange={(e) => setLeverage(parseInt(e.target.value))} />
      <span>x Leverage</span>
      <input placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
      <button onClick={handleOpen}>Open Position</button>

      <h3>Open Positions</h3>
      <table>
        <thead><tr><th>Pair</th><th>Side</th><th>Leverage</th><th>Entry</th><th>Qty</th><th>Margin</th><th>Liq Price</th><th>PnL</th><th></th></tr></thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.id}>
              <td>{p.pair}</td><td>{p.side}</td><td>{p.leverage}x</td><td>{p.entry_price}</td>
              <td>{p.quantity}</td><td>{p.margin}</td><td>{p.liquidation_price}</td>
              <td style={{color: parseFloat(p.unrealized_pnl) >= 0 ? "green" : "red"}}>{p.unrealized_pnl}</td>
              <td><button onClick={() => handleClose(p.id)}>Close</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Step 5: Update App.tsx with routing**

```typescript
// frontend/src/App.tsx
import { useState } from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import SpotTrading from "./pages/SpotTrading";
import FuturesTrading from "./pages/FuturesTrading";
import Login from "./pages/Login";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("token"));

  if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} />;

  return (
    <BrowserRouter>
      <nav style={{ padding: 10, borderBottom: "1px solid #ccc" }}>
        <Link to="/" style={{ marginRight: 20 }}>Dashboard</Link>
        <Link to="/spot" style={{ marginRight: 20 }}>Spot</Link>
        <Link to="/futures" style={{ marginRight: 20 }}>Futures</Link>
        <button onClick={() => { localStorage.removeItem("token"); setLoggedIn(false); }}>Logout</button>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/spot" element={<SpotTrading />} />
        <Route path="/futures" element={<FuturesTrading />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: frontend pages for dashboard, spot trading, and futures trading"
```

---

## Task 11: Docker Compose & Integration

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`

**Step 1: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

**Step 3: Create docker-compose.yml**

```yaml
version: "3.8"
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agent_metaverse
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/agent_metaverse
    depends_on:
      - db

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

**Step 4: Test with docker-compose**

Run: `docker-compose up --build`
Expected: All 3 services start. Backend at :8000, Frontend at :3000, PostgreSQL at :5432.

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: Docker Compose setup for full stack deployment"
```

---

## Task 12: Python SDK for Agents

**Files:**
- Create: `sdk/agent_metaverse/__init__.py`
- Create: `sdk/agent_metaverse/client.py`
- Create: `sdk/setup.py`

**Step 1: Create sdk/agent_metaverse/client.py**

```python
import httpx


class AgentMetaverseClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(base_url=self.base_url, headers={"X-API-Key": api_key} if api_key else {})

    @classmethod
    def register(cls, base_url: str, name: str, description: str = "") -> "AgentMetaverseClient":
        resp = httpx.post(f"{base_url}/api/sdk/agents/register", json={"name": name, "description": description})
        resp.raise_for_status()
        data = resp.json()
        return cls(base_url=base_url, api_key=data["api_key"])

    def get_prices(self) -> dict:
        return self._client.get("/api/prices").json()

    def get_balance(self) -> list:
        return self._client.get("/api/account/balance").json()

    def buy_spot(self, pair: str, quantity: float) -> dict:
        return self._client.post("/api/spot/order", json={"pair": pair, "side": "buy", "order_type": "market", "quantity": quantity}).json()

    def sell_spot(self, pair: str, quantity: float) -> dict:
        return self._client.post("/api/spot/order", json={"pair": pair, "side": "sell", "order_type": "market", "quantity": quantity}).json()

    def open_position(self, pair: str, side: str, leverage: int, quantity: float) -> dict:
        return self._client.post("/api/futures/open", json={"pair": pair, "side": side, "leverage": leverage, "quantity": quantity}).json()

    def close_position(self, position_id: str) -> dict:
        return self._client.post(f"/api/futures/close/{position_id}").json()

    def get_positions(self) -> list:
        return self._client.get("/api/futures/positions").json()

    def swap(self, pair: str, side: str, amount: float) -> dict:
        return self._client.post("/api/amm/swap", json={"pair": pair, "side": side, "amount": amount}).json()
```

**Step 2: Create sdk/agent_metaverse/__init__.py**

```python
from agent_metaverse.client import AgentMetaverseClient

__all__ = ["AgentMetaverseClient"]
```

**Step 3: Create sdk/setup.py**

```python
from setuptools import setup, find_packages

setup(
    name="agent-metaverse",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["httpx>=0.28.0"],
    python_requires=">=3.10",
    description="Python SDK for Agent Metaverse Virtual Exchange",
)
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: Python SDK for agent integration"
```

---

## Task 13: Final Integration Testing

**Step 1: Start services**

```bash
docker-compose up -d
# Wait for services to be ready
sleep 10
# Run migrations
cd backend && alembic upgrade head
```

**Step 2: Test agent registration via SDK**

```python
from agent_metaverse import AgentMetaverseClient

client = AgentMetaverseClient.register("http://localhost:8000", "TestAgent", "Integration test bot")
print(client.get_balance())
print(client.get_prices())
```

**Step 3: Test spot trading flow**

```python
# Wait for prices to load
prices = client.get_prices()
print(f"Prices: {prices}")

# Buy some ETH
result = client.buy_spot("ETHUSDT", 0.1)
print(f"Buy result: {result}")

# Check balance
print(client.get_balance())
```

**Step 4: Test futures flow**

```python
# Open long BTC position with 10x leverage
pos = client.open_position("BTCUSDT", "long", 10, 0.01)
print(f"Position: {pos}")

# Check positions
print(client.get_positions())

# Close position
client.close_position(pos["id"])
```

**Step 5: Commit final state**

```bash
git add -A
git commit -m "feat: integration tests and final verification"
```

---

## Summary

| Task | Component | Key Files |
|------|-----------|-----------|
| 1 | Project scaffolding | main.py, config.py, requirements.txt |
| 2 | Database models | models/*.py, alembic/ |
| 3 | Auth (JWT + API Key) | middleware/auth.py, api/auth.py, api/sdk.py |
| 4 | Price Engine | services/price_engine.py, websocket/broadcaster.py |
| 5 | Account API | api/account.py |
| 6 | Spot Trading | services/spot_engine.py, api/spot.py |
| 7 | Futures Engine | services/futures_engine.py, services/liquidation.py |
| 8 | AMM Engine | services/amm_engine.py, api/amm.py |
| 9 | Frontend setup | frontend/src/services/ |
| 10 | Frontend pages | frontend/src/pages/ |
| 11 | Docker Compose | docker-compose.yml, Dockerfiles |
| 12 | Python SDK | sdk/agent_metaverse/ |
| 13 | Integration test | End-to-end verification |
