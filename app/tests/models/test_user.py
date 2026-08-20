"""Integration tests for the User model and database constraints."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import create_user
from web_practice.models import User


@pytest.mark.integration
def test_user_defaults_are_persisted(db_session: Session) -> None:
    """New users should receive the regular role and creation timestamp."""
    user = User(username="alice", password_hash="hash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert (user.role, user.created_at is not None) == ("user", True)


@pytest.mark.integration
def test_username_must_be_unique(db_session: Session) -> None:
    """The database should reject duplicate normalized usernames."""
    create_user(db_session, username="alice")
    db_session.add(User(username="alice", password_hash="another-hash"))

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.integration
def test_user_role_check_rejects_unknown_role(db_session: Session) -> None:
    """Only user and admin roles should satisfy the DB check constraint."""
    db_session.add(User(username="alice", password_hash="hash", role="owner"))

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.integration
def test_user_password_hash_is_required(db_session: Session) -> None:
    """Users cannot be persisted without password credentials."""
    db_session.add(User(username="alice"))

    with pytest.raises(IntegrityError):
        db_session.commit()
