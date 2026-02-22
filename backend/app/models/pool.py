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
