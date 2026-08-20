"""Tests for CSRF header validation."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from dependencies.csrf import require_csrf
from models import AuthSession
from services import hash_csrf_token


def make_auth_session() -> AuthSession:
    """Build a valid authentication session for CSRF tests."""
    return AuthSession(
        user_id=1,
        token_hash="a" * 64,
        csrf_token_hash=hash_csrf_token("valid-csrf-token"),
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )


@pytest.mark.unit
def test_require_csrf_rejects_missing_header() -> None:
    """State-changing requests must supply an explicit CSRF header."""
    with pytest.raises(HTTPException) as error:
        require_csrf(make_auth_session(), None)

    assert (error.value.status_code, error.value.detail) == (403, "CSRF token required")


@pytest.mark.unit
def test_require_csrf_rejects_invalid_token() -> None:
    """A mismatched CSRF token should be forbidden."""
    with pytest.raises(HTTPException) as error:
        require_csrf(make_auth_session(), "wrong-token")

    assert (error.value.status_code, error.value.detail) == (403, "Invalid CSRF token")


@pytest.mark.unit
def test_require_csrf_accepts_matching_token() -> None:
    """The expected raw CSRF token should pass validation."""
    require_csrf(make_auth_session(), "valid-csrf-token")
