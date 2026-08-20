"""
ユーザー情報に関するAPIエンドポイントを提供するルーター
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import DbSession
from dependencies import CurrentUser
from models import User
from schemas import UserCreate, UserResponse
from services import hash_password, normalize_username

# ルーター設定
router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    db: DbSession,
) -> User:
    """
    新しいユーザーを登録する。
    ユーザー名の重複は既存ユーザーの確認とUNIQUE制約の2段階で確認する。
    """
    # ユーザー名を正規化する（小文字に統一、前後の空白を除去）
    username = normalize_username(user_data.username)

    # DBから既存のユーザーを検索して、usernameの重複を簡易確認する。
    existing_user = db.scalar(select(User).where(User.username == username))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # ユーザーを作成し、パスワードをハッシュ化してDBに保存する。
    user = User(
        username=username,
        password_hash=hash_password(user_data.password),
    )

    db.add(user)

    # UNIQUE制約違反対応
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from e

    db.refresh(user)

    return user


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: CurrentUser,
) -> User:
    """現在のユーザー情報を取得する。"""
    return current_user
