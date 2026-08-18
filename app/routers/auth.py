"""
認証に関するAPIエンドポイントを提供するルーター
"""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from sqlalchemy import select

from config import COOKIE_SECURE, SESSION_COOKIE_NAME, SESSION_LIFETIME
from database import DbSession
from models import AuthSession, User
from schemas import LoginRequest, UserResponse
from services import (
    create_session_expiration,
    generate_session_token,
    hash_session_token,
    normalize_username,
    verify_password,
)

# ルーター設定
router = APIRouter(
    tags=["authentication"],
)

# --- ログイン ---

@router.post(
    "/login",
    response_model=UserResponse,
)
def login(
    login_data: LoginRequest,
    response: Response,
    db: DbSession,
) -> User:
    """
    usernameとpasswordを検証し、正しければ新しいセッションを作成する。
    生のセッショントークンはHttpOnly Cookieとしてクライアントへ返す。
    """
    username = normalize_username(login_data.username)

    user = db.scalar(
        select(User).where(
            User.username == username
        )
    )

    # ユーザーが存在しない場合でもパスワード違いの場合でも401 Unauthorizedを返す。
    if (
        user is None
        or not verify_password(
            login_data.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_token = generate_session_token()

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(session_token),
        expires_at=create_session_expiration(),
    )

    db.add(auth_session)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,  # CookieをJavaScriptからアクセスできないようにする
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    return user


# --- ログアウト ---

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    db: DbSession,
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
) -> Response:
    if session_token is not None:
        token_hash = hash_session_token(session_token)

        auth_session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash
            )
        )

        if auth_session is not None:
            db.delete(auth_session)
            db.commit()

    response = Response(
        status_code=status.HTTP_204_NO_CONTENT
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return response

