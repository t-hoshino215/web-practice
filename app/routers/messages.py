"""
メッセージに関するAPIエンドポイントを提供するルーター
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from database import DbSession
from models import Message
from schemas import MessageCreate, MessageRead

# ルーター設定
router = APIRouter(
    prefix="/messages",
    tags=["messages"],
)

@router.get(
    "",
    response_model=list[MessageRead],
)
def list_messages(db: DbSession):
    """メッセージの一覧を取得する。"""
    statement = select(Message).order_by(Message.id)

    return list(db.scalars(statement))


@router.post(
    "",
    response_model=MessageRead,
    status_code=201,
)
def create_message(
    payload: MessageCreate,
    db: DbSession,
):
    """新しいメッセージを作成する。"""
    message = Message(text=payload.text)

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


@router.patch(
    "/{message_id}/archive",
    response_model=MessageRead,
)
def archive_message(
    message_id: int,
    db: DbSession,
):
    """指定されたIDのメッセージをアーカイブする。"""
    message = db.get(Message, message_id)

    if message is None:
        raise HTTPException(
            status_code=404,
            detail="Message not found",
        )

    message.is_archived = True

    db.commit()
    db.refresh(message)

    return message
