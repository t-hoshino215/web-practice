"""
データベース接続およびセッション管理の設定
リクエスト単位のDB管理を行い、全体のライフサイクルは main.py で管理する。
"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import DATABASE_URL


class Base(DeclarativeBase):
    """
    SQLAlchemyのベースクラス。
    このクラスを継承してDBモデルを定義する。
    """
    pass


# SQLAlchemyのエンジンを作成
engine = create_engine(DATABASE_URL)

# SQLAlchemyのセッションを作成するためのセッションメーカーを定義
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session]:
    """
    データベースセッションを取得するためのジェネレーター関数。
    FastAPIのDependencyとしてDBセッションを提供し、リクエストの終了時に必ずセッションを閉じる。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# FastAPIのDependencyとして使用するための型エイリアスを定義
DbSession = Annotated[Session, Depends(get_db)]
