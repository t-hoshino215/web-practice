"""Tests for authentication request and response schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schemas import LoginRequest, LoginResponse, UserResponse


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"), [("username", "a"), ("username", "a" * 50), ("password", "p"), ("password", "p" * 128)]
)
def test_login_request_accepts_boundaries(field: str, value: str) -> None:
    """Login fields should accept their inclusive length boundaries."""
    payload = {"username": "alice", "password": "password", field: value}

    request = LoginRequest.model_validate(payload)

    assert getattr(request, field) == value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value"), [("username", ""), ("username", "a" * 51), ("password", ""), ("password", "p" * 129)]
)
def test_login_request_rejects_values_outside_boundaries(field: str, value: str) -> None:
    """Login fields outside their supported lengths should fail validation."""
    payload = {"username": "alice", "password": "password", field: value}

    with pytest.raises(ValidationError):
        LoginRequest.model_validate(payload)


@pytest.mark.unit
def test_login_response_contains_user_and_csrf_token() -> None:
    """Login responses should expose the safe user shape and raw CSRF token."""
    user = UserResponse(id=1, username="alice", role="user", created_at=datetime(2026, 8, 20, tzinfo=UTC))

    response = LoginResponse(user=user, csrf_token="csrf-token")

    assert response.model_dump() == {"user": user.model_dump(), "csrf_token": "csrf-token"}
