"""
ユーザー認証関連のスキーマを定義する
"""

from pydantic import BaseModel, Field

from schemas.user import UserResponse


class LoginRequest(BaseModel):
    """
    ログインAPIがクライアントから受け取る認証情報を定義する。
    """

    username: str = Field(
        min_length=1,
        max_length=50,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


class LoginResponse(BaseModel):
    """
    ログイン成功時にユーザー情報とCSRFトークンを返す。
    """

    user: UserResponse
    csrf_token: str
