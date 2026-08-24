"""
ログイン中のユーザーセッションを管理するためのDBモデルを定義する
テーブル名: auth_sessions
カラム:
    - id: セッションID (主キー)
    - user_id: ユーザーID (usersテーブルの外部キー)
    - token_hash: セッショントークンのSHA-256ハッシュ値 (一意制約あり)
    - expires_at: セッションの有効期限日時
    - created_at: セッション作成日時 (デフォルト値は現在時刻)
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from web_practice.database import Base


class AuthSession(Base):
    """
    ログイン中のユーザーセッションをDB上で管理するモデル (auth_sessionsテーブル)。
    Cookieに保存する生のセッショントークンは保存せず、
    SHA-256でハッシュ化した値のみをDBへ保存する。
    """

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    # CSRF攻撃対策用トークンのハッシュ値。
    # クライアントには生のトークンを渡し、DBにはハッシュのみ保存する。
    csrf_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
