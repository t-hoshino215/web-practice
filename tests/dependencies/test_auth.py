"""Tests for authentication and authorization dependencies."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from dependencies.auth import get_current_auth_session, get_current_user, require_admin
from models import AuthSession, User
from services import hash_session_token


def assert_http_error(error: pytest.ExceptionInfo[HTTPException], status_code: int, detail: str) -> None:
    """Assert the public status and detail of an authentication failure."""
    assert (error.value.status_code, error.value.detail) == (status_code, detail)


def make_auth_session(*, expired: bool = False, user_id: int = 1) -> AuthSession:
    """Build an unpersisted session with an aware expiration timestamp."""
    offset = timedelta(minutes=-1 if expired else 1)
    return AuthSession(
        user_id=user_id,
        token_hash="a" * 64,
        csrf_token_hash="b" * 64,
        expires_at=datetime.now(UTC) + offset,
    )


@pytest.mark.unit
@pytest.mark.parametrize("dependency", [get_current_auth_session, get_current_user])
def test_auth_dependencies_reject_missing_cookie(dependency: object) -> None:
    """Authentication dependencies should reject requests without a session cookie."""
    db = MagicMock(spec=Session)

    with pytest.raises(HTTPException) as error:
        dependency(db, None)  # type: ignore[operator]

    assert_http_error(error, 401, "Authentication required")


@pytest.mark.unit
@pytest.mark.parametrize("dependency", [get_current_auth_session, get_current_user])
def test_auth_dependencies_reject_unknown_session(dependency: object) -> None:
    """Authentication dependencies should reject unknown token hashes."""
    db = MagicMock(spec=Session)
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as error:
        dependency(db, "unknown-token")  # type: ignore[operator]

    assert_http_error(error, 401, "Invalid session")


@pytest.mark.unit
@pytest.mark.parametrize("dependency", [get_current_auth_session, get_current_user])
def test_auth_dependencies_query_hashed_cookie_on_token_column(dependency: object) -> None:
    """Session lookup must filter the token column by the cookie's hash."""
    db = MagicMock(spec=Session)
    db.scalar.return_value = None

    with pytest.raises(HTTPException):
        dependency(db, "raw-session-token")  # type: ignore[operator]

    statement = db.scalar.call_args.args[0]
    predicate = statement.whereclause
    assert (
        predicate.left.compare(AuthSession.__table__.c.token_hash),
        predicate.right.value,
    ) == (True, hash_session_token("raw-session-token"))


@pytest.mark.unit
@pytest.mark.parametrize("dependency", [get_current_auth_session, get_current_user])
def test_auth_dependencies_delete_expired_session(dependency: object) -> None:
    """Expired sessions should be cleaned up before returning 401."""
    db = MagicMock(spec=Session)
    auth_session = make_auth_session(expired=True)
    db.scalar.return_value = auth_session

    with pytest.raises(HTTPException) as error:
        dependency(db, "expired-token")  # type: ignore[operator]

    assert (error.value.detail, db.delete.call_args.args, db.commit.call_count) == (
        "Session expired",
        (auth_session,),
        1,
    )


@pytest.mark.unit
def test_get_current_auth_session_returns_valid_session() -> None:
    """A valid token should return its exact authentication session."""
    db = MagicMock(spec=Session)
    auth_session = make_auth_session()
    db.scalar.return_value = auth_session

    result = get_current_auth_session(db, "valid-token")

    assert result is auth_session


@pytest.mark.unit
def test_get_current_user_deletes_orphan_session() -> None:
    """Sessions whose users were removed should be cleaned up and rejected."""
    db = MagicMock(spec=Session)
    auth_session = make_auth_session(user_id=99)
    db.scalar.return_value = auth_session
    db.get.return_value = None

    with pytest.raises(HTTPException) as error:
        get_current_user(db, "orphan-token")

    assert (error.value.detail, db.delete.call_args.args, db.commit.call_count) == (
        "Invalid session",
        (auth_session,),
        1,
    )


@pytest.mark.unit
def test_get_current_user_returns_session_user() -> None:
    """A valid session should resolve and return its user."""
    db = MagicMock(spec=Session)
    auth_session = make_auth_session(user_id=7)
    user = User(id=7, username="alice", password_hash="hash", role="user")
    db.scalar.return_value = auth_session
    db.get.return_value = user

    result = get_current_user(db, "valid-token")

    assert result is user


@pytest.mark.unit
def test_require_admin_returns_admin_user() -> None:
    """The admin dependency should preserve an authorized user."""
    user = User(username="admin", password_hash="hash", role="admin")

    result = require_admin(user)

    assert result is user


@pytest.mark.unit
def test_require_admin_rejects_regular_user() -> None:
    """A regular authenticated user should receive a forbidden response."""
    user = User(username="alice", password_hash="hash", role="user")

    with pytest.raises(HTTPException) as error:
        require_admin(user)

    assert_http_error(error, 403, "Administrator privileges required")
