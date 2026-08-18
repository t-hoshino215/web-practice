"""
ユーザーが投稿したメッセージを管理するためのDBモデルを定義する
テーブル名: messages
カラム:
    - id: メッセージID (主キー)
    - text: メッセージの内容 (最大255文字)
    - is_archived: メッセージのアーカイブ状態 (デフォルト値はFalse)
    - created_at: メッセージ作成日時 (デフォルト値は現在時刻)
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Message(Base):
    """
    ユーザーが投稿したメッセージを表すDBモデル (messagesテーブル)。
    メッセージの内容、アーカイブ状態、作成日時を保持する。
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    text: Mapped[str] = mapped_column(String(255))

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,  # SQLAlchemyのデフォルト値を設定
        server_default=false(), # PostgreSQLのデフォルト値を設定 (列追加時に既存の行に対しても適用される)
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
