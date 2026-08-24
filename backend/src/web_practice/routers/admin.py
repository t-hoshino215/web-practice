"""
管理者専用のAPIを提供するルーター
"""

from fastapi import APIRouter
from sqlalchemy import select

from web_practice.database import DbSession
from web_practice.dependencies import CurrentAdmin
from web_practice.models import Message, User
from web_practice.schemas import MessageRead, UserResponse

# ルーター設定
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)


@router.get(
    "/users",
    response_model=list[UserResponse],
)
def get_all_users(
    _admin: CurrentAdmin,  # ここでCurrentAdminを依存関係として指定することで、管理者権限を持つユーザーのみがアクセス可能になる。
    db: DbSession,
) -> list[User]:
    """
    全ユーザーの一覧を取得できるAPI。
    管理者権限を持つユーザーのみがアクセス可能。
    """
    users = db.scalars(select(User).order_by(User.id)).all()

    return list(users)


@router.get(
    "/messages",
    response_model=list[MessageRead],
)
def get_all_messages(
    _admin: CurrentAdmin,
    db: DbSession,
) -> list[Message]:
    """
    全メッセージの一覧を取得できるAPI。
    管理者権限を持つユーザーのみがアクセス可能。
    """
    messages = db.scalars(select(Message).order_by(Message.id)).all()

    return list(messages)
