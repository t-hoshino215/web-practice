"""Integration tests for AuthSession persistence and constraints."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import create_auth_session, create_user
from web_practice.models import AuthSession


@pytest.mark.integration
def test_auth_session_defaults_are_persisted(db_session: Session) -> None:
    """A persisted session should receive its ID and creation timestamp."""
    user = create_user(db_session)

    auth_session = create_auth_session(db_session, user=user)

    assert (auth_session.id is not None, auth_session.created_at is not None) == (True, True)


@pytest.mark.integration
def test_auth_session_token_hash_must_be_unique(db_session: Session) -> None:
    """Two sessions cannot share the same stored token hash."""
    user = create_user(db_session)
    create_auth_session(db_session, user=user, token="duplicate")

    with pytest.raises(IntegrityError):
        create_auth_session(db_session, user=user, token="duplicate", csrf_token="other")


@pytest.mark.integration
def test_auth_session_requires_csrf_hash(db_session: Session) -> None:
    """A session without CSRF state should violate its NOT NULL constraint."""
    user = create_user(db_session)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(auth_session)

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.integration
def test_deleting_user_cascades_to_auth_sessions(db_session: Session) -> None:
    """Deleting a user should remove sessions owned by that user."""
    user = create_user(db_session)
    create_auth_session(db_session, user=user)

    db_session.delete(user)
    db_session.commit()
    remaining = db_session.scalar(select(func.count()).select_from(AuthSession))

    assert remaining == 0


@pytest.mark.integration
def test_auth_session_requires_existing_user(db_session: Session) -> None:
    """Session ownership should be protected by a foreign key."""
    auth_session = AuthSession(
        user_id=999,
        token_hash="a" * 64,
        csrf_token_hash="b" * 64,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(auth_session)

    with pytest.raises(IntegrityError):
        db_session.commit()
