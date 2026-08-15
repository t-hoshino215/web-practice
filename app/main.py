import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, String, create_engine, func, select, text
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

# ----------------------------------------------
# データベース接続の設定
# ----------------------------------------------

# 環境変数からデータベースのURLを取得
DATABASE_URL = os.environ["DATABASE_URL"]

# SQLAlchemyのエンジンを作成
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# SQLAlchemyのセッションを作成するためのセッションメーカーを定義
SessionLocal = sessionmaker(bind=engine)

# ----------------------------------------------
# SQLAlchemyのモデル定義
# ----------------------------------------------

# SQLAlchemyのベースクラスを定義
class Base(DeclarativeBase):
    pass

# messageテーブルのモデルを定義
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=255)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    created_at: datetime

# ----------------------------------------------
# FastAPIアプリケーションの設定
# ----------------------------------------------

# データベースセッションを取得するための依存関係を定義
def get_db():
    with SessionLocal() as session:
        yield session

# データベースセッションの型を定義
DbSession = Annotated[Session, Depends(get_db)]

# FastAPIアプリケーションのライフサイクルイベントを定義
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    engine.dispose()

# FastAPIアプリケーションを作成
app = FastAPI(lifespan=lifespan)

# ----------------------------------------------
# FastAPIのルートエンドポイントを定義
# ----------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Hello, Web Server!",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
    }


@app.get("/db-health")
def db_health(db: DbSession):
    db.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected",
    }


@app.post(
    "/messages",
    response_model=MessageRead,
    status_code=201,
)
def create_message(
    payload: MessageCreate,
    db: DbSession,
):
    message = Message(text=payload.text)

    db.add(message)
    db.commit()
    db.refresh(message)

    return message


@app.get(
    "/messages",
    response_model=list[MessageRead],
)
def list_messages(db: DbSession):
    statement = select(Message).order_by(Message.id)

    return list(db.scalars(statement))