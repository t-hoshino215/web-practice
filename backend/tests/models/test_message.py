"""Integration tests for Message persistence and ownership constraints."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import create_message, create_user
from web_practice.models import Message


@pytest.mark.integration
def test_message_defaults_are_persisted(db_session: Session) -> None:
    """New messages should be active and receive a creation timestamp."""
    user = create_user(db_session)
    message = Message(text="hello", user_id=user.id)
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    assert (message.is_archived, message.created_at is not None) == (False, True)


@pytest.mark.integration
def test_message_requires_owner(db_session: Session) -> None:
    """Messages cannot be persisted without a user ID."""
    db_session.add(Message(text="orphan"))

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.integration
def test_message_requires_existing_owner(db_session: Session) -> None:
    """Message ownership should be protected by a foreign key."""
    db_session.add(Message(text="orphan", user_id=999))

    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.integration
def test_deleting_user_cascades_to_messages(db_session: Session) -> None:
    """Deleting a user should remove all messages owned by that user."""
    user = create_user(db_session)
    create_message(db_session, user=user)

    db_session.delete(user)
    db_session.commit()
    remaining = db_session.scalar(select(func.count()).select_from(Message))

    assert remaining == 0
