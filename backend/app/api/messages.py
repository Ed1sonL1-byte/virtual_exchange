from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.message import Message
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


class SendMessageRequest(BaseModel):
    to: str  # agent name or "all" for broadcast
    content: str


class MessageResponse(BaseModel):
    id: str
    sender: str
    recipient: str  # "all" for broadcast
    content: str
    timestamp: str


@router.post("/send", response_model=MessageResponse)
async def send_message(
    data: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_broadcast = data.to.lower() == "all"
    recipient_id = None
    recipient_name = "all"

    if not is_broadcast:
        result = await db.execute(select(User).where(User.username == data.to))
        recipient = result.scalar_one_or_none()
        if not recipient:
            raise HTTPException(status_code=404, detail=f"Agent '{data.to}' not found")
        recipient_id = recipient.id
        recipient_name = recipient.username

    msg = Message(
        sender_id=user.id,
        sender_name=user.username,
        recipient_id=recipient_id,
        recipient_name=recipient_name,
        content=data.content,
        is_broadcast=is_broadcast,
    )
    db.add(msg)
    await db.flush()

    return MessageResponse(
        id=str(msg.id),
        sender=user.username,
        recipient=recipient_name,
        content=msg.content,
        timestamp=msg.created_at.isoformat() if msg.created_at else "",
    )


@router.get("/inbox", response_model=list[MessageResponse])
async def get_inbox(
    limit: int = 50,
    since: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages sent TO this agent (DMs + broadcasts), newest first."""
    query = select(Message).where(
        or_(
            Message.recipient_id == user.id,  # DMs to me
            Message.is_broadcast == True,      # broadcasts
        ),
        Message.sender_id != user.id,          # exclude my own broadcasts
    ).order_by(desc(Message.created_at)).limit(limit)

    if since:
        from datetime import datetime
        query = query.where(Message.created_at > datetime.fromisoformat(since))

    result = await db.execute(query)
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=str(m.id),
            sender=m.sender_name,
            recipient=m.recipient_name or "all",
            content=m.content,
            timestamp=m.created_at.isoformat() if m.created_at else "",
        )
        for m in messages
    ]


@router.get("/sent", response_model=list[MessageResponse])
async def get_sent(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get messages sent BY this agent."""
    result = await db.execute(
        select(Message)
        .where(Message.sender_id == user.id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=str(m.id),
            sender=m.sender_name,
            recipient=m.recipient_name or "all",
            content=m.content,
            timestamp=m.created_at.isoformat() if m.created_at else "",
        )
        for m in messages
    ]


@router.get("/history", response_model=list[MessageResponse])
async def get_all_public_messages(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get all broadcast messages (public chat history). No auth required."""
    result = await db.execute(
        select(Message)
        .where(Message.is_broadcast == True)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=str(m.id),
            sender=m.sender_name,
            recipient="all",
            content=m.content,
            timestamp=m.created_at.isoformat() if m.created_at else "",
        )
        for m in messages
    ]
