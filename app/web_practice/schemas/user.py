"""
ユーザー関連のスキーマを定義する
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    """
    ユーザー登録APIが受け取る入力データを定義する。
    roleはユーザー登録時に指定させないため、UserCreateスキーマには含めない。
    """

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserResponse(BaseModel):
    """
    APIから公開可能なユーザー情報を定義する。
    password_hashはレスポンスへ含めない。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: datetime
