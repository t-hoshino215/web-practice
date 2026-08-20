"""
メッセージに関するAPIエンドポイントを提供するルーター
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from database import DbSession
from dependencies import CurrentUser, require_csrf
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
def list_messages(
    current_user: CurrentUser,
    db: DbSession,
) -> list[Message]:
    """
    ログイン中のユーザーのメッセージの一覧を取得する。
    """
    messages = db.scalars(select(Message).where(Message.user_id == current_user.id).order_by(Message.id)).all()

    return list(messages)


@router.post(
    "",
    response_model=MessageRead,
    dependencies=[Depends(require_csrf)],
)
def create_message(
    message_data: MessageCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> Message:
    """
    ログイン中のユーザーを所有者として新しいメッセージを作成する。
    クライアントはログインセッションからユーザーIDを特定する。
    """
    message = Message(text=message_data.text, user_id=current_user.id)

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


@router.patch("/{message_id}/archive", response_model=MessageRead, dependencies=[Depends(require_csrf)])
def archive_message(
    message_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> Message:
    """
    指定されたIDのメッセージをアーカイブする。
    ログイン中のユーザーが所有者でない場合でも404 Not Foundを返し、他人のメッセージの存在を隠す。
    """
    # メッセージIDとユーザーIDでメッセージを検索する
    message = db.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id,
        )
    )

    # メッセージが存在しない場合は404 Not Foundを返す
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    message.is_archived = True

    db.commit()
    db.refresh(message)

    return message
