"""Tests for message request and response schemas."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from web_practice.schemas import MessageCreate, MessageRead


@pytest.mark.unit
@pytest.mark.parametrize("length", [1, 255])
def test_message_create_accepts_text_boundaries(length: int) -> None:
    """Message text should accept its inclusive length boundaries."""
    message = MessageCreate(text="x" * length)

    assert len(message.text) == length


@pytest.mark.unit
@pytest.mark.parametrize("length", [0, 256])
def test_message_create_rejects_text_outside_boundaries(length: int) -> None:
    """Message text just outside allowed lengths should fail validation."""
    with pytest.raises(ValidationError):
        MessageCreate(text="x" * length)


@pytest.mark.unit
def test_message_read_uses_orm_attributes_and_hides_owner() -> None:
    """Message responses should validate ORM objects without exposing ownership IDs."""
    created_at = datetime(2026, 8, 20, tzinfo=UTC)
    message = SimpleNamespace(id=2, text="hello", is_archived=False, created_at=created_at, user_id=9)

    response = MessageRead.model_validate(message)

    assert response.model_dump() == {"id": 2, "text": "hello", "is_archived": False, "created_at": created_at}
