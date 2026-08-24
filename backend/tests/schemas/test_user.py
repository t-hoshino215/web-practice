"""Tests for user request and response schemas."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from web_practice.schemas import UserCreate, UserResponse


@pytest.mark.unit
@pytest.mark.parametrize("length", [3, 50])
def test_user_create_accepts_username_boundaries(length: int) -> None:
    """Username minimum and maximum lengths should be accepted."""
    schema = UserCreate(username="a" * length, password="password")

    assert len(schema.username) == length


@pytest.mark.unit
@pytest.mark.parametrize("username", ["ab", "a" * 51, "has space", "user!", "日本語"])
def test_user_create_rejects_invalid_username(username: str) -> None:
    """Out-of-range or unsupported usernames should fail validation."""
    with pytest.raises(ValidationError):
        UserCreate(username=username, password="password")


@pytest.mark.unit
@pytest.mark.parametrize("length", [8, 128])
def test_user_create_accepts_password_boundaries(length: int) -> None:
    """Password minimum and maximum lengths should be accepted."""
    schema = UserCreate(username="alice", password="p" * length)

    assert len(schema.password) == length


@pytest.mark.unit
@pytest.mark.parametrize("length", [7, 129])
def test_user_create_rejects_password_outside_boundaries(length: int) -> None:
    """Passwords just outside supported lengths should fail validation."""
    with pytest.raises(ValidationError):
        UserCreate(username="alice", password="p" * length)


@pytest.mark.unit
def test_user_response_reads_orm_attributes() -> None:
    """Response schemas should validate ORM-style attribute objects."""
    created_at = datetime(2026, 8, 20, tzinfo=UTC)
    user = SimpleNamespace(id=1, username="alice", role="user", created_at=created_at, password_hash="secret")

    response = UserResponse.model_validate(user)

    assert response.model_dump() == {"id": 1, "username": "alice", "role": "user", "created_at": created_at}


@pytest.mark.unit
def test_user_response_omits_password_hash() -> None:
    """Public user responses must not expose password hashes."""
    user = SimpleNamespace(
        id=1,
        username="alice",
        role="user",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        password_hash="secret",
    )

    response = UserResponse.model_validate(user)

    assert "password_hash" not in response.model_dump()
