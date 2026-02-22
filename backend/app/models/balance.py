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
