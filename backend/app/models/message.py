import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Boolean, func, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # null = broadcast to all
    recipient_name: Mapped[str | None] = mapped_column(String(50), nullable=True)  # null = "all"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_broadcast: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
