"""
FastAPIの作成、ルーターの登録、ライフサイクル管理を行う
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import engine
from routers import auth_router, health_router, messages_router, users_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPIアプリケーションのライフサイクルを管理するコンテキストマネージャー。
    アプリ終了時にSQLAlchemy Engineの接続プールを破棄する。
    """
    # アプリケーションの起動時に必要な初期化処理 (yieldの前に記載する)
    yield
    # アプリケーションの終了時に必要なクリーンアップ処理 (yieldの後に記載する)
    engine.dispose()


def create_app() -> FastAPI:
    """FastAPIアプリケーションを生成し、各ルーターを登録する。"""
    app = FastAPI(
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(messages_router)
    app.include_router(users_router)
    app.include_router(auth_router)

    return app


app = create_app()
