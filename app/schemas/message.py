"""
メッセージ関連のスキーマを定義する
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    """
    メッセージ作成時にクライアントから受け取るデータを定義する。
    """
    text: str = Field(min_length=1, max_length=255)


class MessageRead(BaseModel):
    """
    メッセージ取得時にクライアントへ返すデータを定義する。
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    is_archived: bool
    created_at: datetime
