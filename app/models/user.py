"""
アプリケーションへログインできるユーザー情報を管理するためのDBモデルを定義する
テーブル名: users
カラム:
    - id: ユーザーID (主キー)
    - username: ユーザー名 (一意制約あり)
    - password_hash: パスワードのハッシュ値 (Argon2で生成したハッシュ値を保存)
    - created_at: ユーザー作成日時 (デフォルト値は現在時刻)
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class User(Base):
    """
    アプリケーションへログインできるユーザー情報を表すDBモデル (usersテーブル)。
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,    # ユーザー名は一意である必要があるため、unique=Trueを設定
        index=True,
        nullable=False,
    )

    # パスワードのハッシュ値を保存するカラム（パスワードはArgon2で生成したハッシュ値を保存する）
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
