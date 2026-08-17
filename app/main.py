import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    String,
    create_engine,
    false,
    func,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

# ----------------------------------------------
# パスワードハッシュの設定
# ----------------------------------------------

password_hasher = PasswordHash.recommended()


# 平文パスワードから、安全にDBへ保存するためのパスワードハッシュを生成する。
def hash_password(password: str) -> str:
    return password_hasher.hash(password)

# ----------------------------------------------
# ユーザー名の設定
# ----------------------------------------------

# ユーザー名の表記揺れを防ぐため、前後の空白を除去して小文字へ統一する。
def normalize_username(username: str) -> str:
    return username.strip().lower()


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

# [DBモデル] messageテーブル: ユーザーが投稿したメッセージを表す。
class Message(Base):
    __tablename__ = "messages"
    # テーブルのカラムを定義
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

# メッセージ作成時にクライアントから受け取るデータを定義する。
class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=255)


# メッセージ取得時にクライアントへ返すデータを定義する。
class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    is_archived: bool
    created_at: datetime


# [DBモデル] usersテーブル: アプリケーションへログインできるユーザー情報を表す。
class User(Base):
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


# ユーザー登録APIがクライアントから受け取るデータを定義する。
class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    password: str = Field(
        min_length=8,
        max_length=128,
    )


# ユーザー登録後などにクライアントへ返す公開可能なユーザー情報を定義する。
# password_hashはレスポンスへ含めない。
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
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


# メッセージを作成するAPIエンドポイントを追加
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


# メッセージ一覧を取得するAPIエンドポイントを追加
@app.get(
    "/messages",
    response_model=list[MessageRead],
)
def list_messages(db: DbSession):
    statement = select(Message).order_by(Message.id)

    return list(db.scalars(statement))


# アーカイブ確認用APIエンドポイントを追加
@app.patch(
    "/messages/{message_id}/archive",
    response_model=MessageRead,
)
def archive_message(
    message_id: int,
    db: DbSession,
):
    message = db.get(Message, message_id)

    if message is None:
        raise HTTPException(
            status_code=404,
            detail="Message not found",
        )

    message.is_archived = True

    db.commit()
    db.refresh(message)

    return message


# 新規ユーザー登録APIエンドポイント
# usernameの重複を確認し、パスワードをハッシュ化してからDBへ保存する。
@app.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    username = normalize_username(user_data.username)

    # ユーザー名の重複を確認するため、DBから既存のユーザーを検索する。（UNIQUE制約の前に確認する）
    existing_user = db.scalar(
        select(User).where(User.username == username)
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=username,
        password_hash=hash_password(user_data.password),
    )

    db.add(user)

    # ユーザーをDBへ保存する際に、UNIQUE制約違反が発生する可能性があるため、IntegrityErrorをキャッチして適切なHTTPレスポンスを返す。
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    db.refresh(user)

    return user
