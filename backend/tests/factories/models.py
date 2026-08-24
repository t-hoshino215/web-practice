"""Small factory functions for database-backed tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from web_practice.models import AuthSession, Message, User
from web_practice.services import hash_csrf_token, hash_session_token


def create_user(
    db: Session,
    *,
    username: str = "test-user",
    password_hash: str = "test-password-hash",
    role: str = "user",
) -> User:
    """Create and persist a user with deterministic defaults."""
    user = User(username=username, password_hash=password_hash, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_auth_session(
    db: Session,
    *,
    user: User,
    token: str = "test-session-token",
    csrf_token: str = "test-csrf-token",
    expires_at: datetime | None = None,
) -> AuthSession:
    """Create and persist an authentication session for a user."""
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        csrf_token_hash=hash_csrf_token(csrf_token),
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(auth_session)
    db.commit()
    db.refresh(auth_session)
    return auth_session


def create_message(
    db: Session,
    *,
    user: User,
    text: str = "test message",
    is_archived: bool = False,
) -> Message:
    """Create and persist a message owned by a user."""
    message = Message(text=text, user_id=user.id, is_archived=is_archived)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
