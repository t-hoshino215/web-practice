"""
管理者専用のAPIを提供するルーター
"""

from fastapi import APIRouter
from sqlalchemy import select

from database import DbSession
from dependencies.auth import CurrentAdmin
from models import User
from schemas.user import UserResponse

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
    _admin: CurrentAdmin,   # ここでCurrentAdminを依存関係として指定することで、管理者権限を持つユーザーのみがアクセス可能になる。
    db: DbSession,
) -> list[User]:
    """
    全ユーザーの一覧を取得できるAPI。
    管理者権限を持つユーザーのみがアクセス可能。
    """
    users = db.scalars(
        select(User).order_by(User.id)
    ).all()

    return list(users)
