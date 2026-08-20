"""
アプリケーションへログインできるユーザー情報を管理するためのDBモデルを定義する
テーブル名: users
カラム:
    - id: ユーザーID (主キー)
    - username: ユーザー名 (一意制約あり)
    - password_hash: パスワードのハッシュ値 (Argon2で生成したハッシュ値を保存)
    - role: ユーザーの役割 (userまたはadmin、デフォルト値はuser)
    - created_at: ユーザー作成日時 (デフォルト値は現在時刻)
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from web_practice.database import Base


class User(Base):
    """
    アプリケーションへログインできるユーザー情報を表すDBモデル (usersテーブル)。
    """

    __tablename__ = "users"

    # roleカラムの値をDBレベルでCHECK制約として定義し、userまたはadmin以外の値が設定されることを防ぐ。
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'admin')",
            name="ck_users_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,  # ユーザー名は一意である必要があるため、unique=Trueを設定
        index=True,
        nullable=False,
    )

    # パスワードのハッシュ値を保存するカラム（パスワードはArgon2で生成したハッシュ値を保存する）
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        server_default="user",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
