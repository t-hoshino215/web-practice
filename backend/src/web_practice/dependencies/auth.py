"""
FastAPIのDependencyとして利用する、認証関連の依存関係を定義するモジュール。

Dependencies:
CurrentAdmin
↓
require_admin()
↓
CurrentUser
↓
get_current_user()
↓
CurrentAuthSession
↓
Session Cookie
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select

from web_practice.config import SESSION_COOKIE_NAME
from web_practice.database import DbSession
from web_practice.models import AuthSession, User
from web_practice.services import hash_session_token

# ----------------------------------------------
# 認証セッション
# ----------------------------------------------


def get_current_auth_session(
    db: DbSession,
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> AuthSession:
    """
    Cookieに保存されたセッショントークンを取得し、DB上の有効な認証セッションを返す。
    Cookieなし・Session不明・期限切れの場合は401を返す。
    """
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token_hash = hash_session_token(session_token)

    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))

    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    if auth_session.expires_at <= datetime.now(UTC):
        db.delete(auth_session)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    return auth_session


# FastAPIのDependencyとして利用する現在の有効な認証セッションの型エイリアス。
CurrentAuthSession = Annotated[AuthSession, Depends(get_current_auth_session)]


# ----------------------------------------------
# ログイン中のユーザー
# ----------------------------------------------


def get_current_user(
    db: DbSession,
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> User:
    """
    Cookie内のセッショントークンを検証し、有効なログインユーザーを取得するFastAPI Dependency。
    未ログイン・無効・期限切れの場合は401を返す。
    """
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token_hash = hash_session_token(session_token)

    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))

    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    now = datetime.now(UTC)

    if auth_session.expires_at <= now:
        db.delete(auth_session)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    user = db.get(
        User,
        auth_session.user_id,
    )

    if user is None:
        db.delete(auth_session)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    return user


# FastAPIのDependencyとして利用する現在の有効なログインユーザーの型エイリアス。
CurrentUser = Annotated[User, Depends(get_current_user)]


# ----------------------------------------------
# 管理者権限の確認
# ----------------------------------------------


def require_admin(
    current_user: CurrentUser,
) -> User:
    """
    現在のユーザーが管理者権限を持つことを確認する。
    ログイン済みでもadminでなければ403 Forbiddenを返す。
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )

    return current_user


# 管理者権限を持つログインユーザーを取得するためのFastAPI Dependency型エイリアス。
CurrentAdmin = Annotated[User, Depends(require_admin)]
