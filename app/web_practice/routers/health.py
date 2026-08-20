"""
FastAPIのルートエンドポイントを定義する
ヘルスチェック用のエンドポイントも含む
"""

from fastapi import APIRouter
from sqlalchemy import text

from web_practice.database import DbSession

# ルーター設定
router = APIRouter()


@router.get("/")
def root():
    return {
        "message": "Hello, Web Server!",
    }


@router.get("/health")
def health():
    return {
        "status": "ok",
    }


@router.get("/db-health")
def db_health(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
    }
