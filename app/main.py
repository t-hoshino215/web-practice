import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone, UTC
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
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
# Session/Cookieの設定
# ----------------------------------------------

SESSION_COOKIE_NAME = "session"
SESSION_LIFETIME = timedelta(days=7)

# CookieのSecure属性を有効にするかどうかを環境変数から取得する。(localhost環境ではfalse、本番(公開HTTPS)環境ではtrueにする想定)
COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE",
    "false",
).lower() in {"1", "true", "yes", "on"}


# ----------------------------------------------
# パスワードハッシュの設定
# ----------------------------------------------

password_hasher = PasswordHash.recommended()

def hash_password(password: str) -> str:
    """
    平文パスワードから、DBへ保存するための安全なパスワードハッシュを生成する。
    """
    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    入力された平文パスワードがDBへ保存されているパスワードハッシュと一致するか検証する。
    """
    return password_hasher.verify(
        password,
        password_hash,
    )


# ----------------------------------------------
# Session Tokenの生成
# ----------------------------------------------

def generate_session_token() -> str:
    """
    推測困難なランダムなセッショントークンを生成する。
    この値そのものはCookieへ保存するが、DBには保存しない。
    """
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """
    生のセッショントークンから、DB検索・保存用のSHA-256ハッシュを生成する。
    """
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_session_expiration() -> datetime:
    """
    新しいログインセッションの有効期限をUTCで生成する。
    """
    return datetime.now(UTC) + SESSION_LIFETIME


# ----------------------------------------------
# ユーザー名の設定
# ----------------------------------------------

def normalize_username(username: str) -> str:
    """
    ユーザー名の表記揺れを防ぐため、前後の空白を除去して小文字へ統一する。
    """
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

# --- Base ---

class Base(DeclarativeBase):
    """
    SQLAlchemyのベースクラス。
    このクラスを継承してDBモデルを定義する。
    """
    pass


# --- messagesテーブル ---

class Message(Base):
    """
    ユーザーが投稿したメッセージを表すDBモデル (messagesテーブル)。
    メッセージの内容、アーカイブ状態、作成日時を保持する。
    """
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

# --- usersテーブル ---

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


class UserCreate(BaseModel):
    """
    ユーザー登録APIがクライアントから受け取るデータを定義する。
    """
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class UserResponse(BaseModel):
    """
    ユーザー登録後などにクライアントへ返す公開可能なユーザー情報を定義する。
    password_hashはレスポンスへ含めない。
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    created_at: datetime


# --- auth_sessionsテーブル ---

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

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class LoginRequest(BaseModel):
    """
    ログインAPIがクライアントから受け取るデータを定義する。
    """
    username: str = Field(
        min_length=1,
        max_length=50,
    )

    password: str = Field(
        min_length=1,
        max_length=128,
    )


# ----------------------------------------------
# FastAPIアプリケーションの設定
# ----------------------------------------------

def get_db():
    """データベースセッションを取得するための依存関係"""
    with SessionLocal() as session:
        yield session

# データベースセッションの型を定義
DbSession = Annotated[Session, Depends(get_db)]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPIアプリケーションのライフサイクルイベントを管理するコンテキストマネージャー。"""
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


# --- メッセージ関連のAPIエンドポイント ---

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


# --- ユーザー登録関連のAPIエンドポイント ---

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


# --- ログイン関連のAPIエンドポイント ---

# usernameとpasswordを検証し、正しければ新しいセッションを作成する。
# 生のセッショントークンはHttpOnly Cookieとしてクライアントへ返す。
@app.post(
    "/login",
    response_model=UserResponse,
)
def login(
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    username = normalize_username(login_data.username)

    user = db.scalar(
        select(User).where(
            User.username == username
        )
    )

    # ユーザーが存在しない場合でもパスワード違いの場合でも401 Unauthorizedを返す。
    if (
        user is None
        or not verify_password(
            login_data.password,
            user.password_hash,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    session_token = generate_session_token()

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(session_token),
        expires_at=create_session_expiration(),
    )

    db.add(auth_session)
    db.commit()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,  # CookieをJavaScriptからアクセスできないようにする
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    return user


def get_current_user(
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
    db: Session = Depends(get_db),
) -> User:
    """
    Cookie内のセッショントークンを検証し、有効なログインユーザーを取得するFastAPI Dependency。
    未ログイン・無効・期限切れの場合は401を返す。
    """
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token_hash = hash_session_token(session_token)

    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash
        )
    )

    if auth_session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    now = datetime.now(UTC)

    if auth_session.expires_at <= now:
        db.delete(auth_session)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    user = db.get(
        User,
        auth_session.user_id,
    )

    if user is None:
        db.delete(auth_session)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    return user


# 現在ログインしているユーザー自身の公開情報を返す。
# get_current_userをDependencyとして使用するため、
# 有効なセッションを持つユーザーだけアクセスできる。
@app.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


# 現在のセッションをDBから削除し、
# クライアント側のセッションCookieも削除する。
# すでにログアウト済みの場合でも204を返す。
@app.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    session_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
    db: Session = Depends(get_db),
) -> Response:
    if session_token is not None:
        token_hash = hash_session_token(session_token)

        auth_session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash
            )
        )

        if auth_session is not None:
            db.delete(auth_session)
            db.commit()

    response = Response(
        status_code=status.HTTP_204_NO_CONTENT
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return response
