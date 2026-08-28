"""Tests for CSRF header validation."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from web_practice.dependencies.csrf import require_csrf
from web_practice.models import AuthSession
from web_practice.services import hash_csrf_token


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
        require_csrf(make_auth_session(), None, "valid-csrf-token")

    assert (error.value.status_code, error.value.detail) == (403, "CSRF token required")


@pytest.mark.unit
def test_require_csrf_rejects_missing_cookie() -> None:
    """State-changing requests must supply the CSRF cookie."""
    with pytest.raises(HTTPException) as error:
        require_csrf(make_auth_session(), "valid-csrf-token", None)

    assert (error.value.status_code, error.value.detail) == (403, "CSRF token required")


@pytest.mark.unit
def test_require_csrf_rejects_header_cookie_mismatch() -> None:
    """The submitted header and cookie must contain the same token."""
    with pytest.raises(HTTPException) as error:
        require_csrf(make_auth_session(), "header-token", "cookie-token")

    assert (error.value.status_code, error.value.detail) == (403, "Invalid CSRF token")


@pytest.mark.unit
def test_require_csrf_rejects_token_not_bound_to_session() -> None:
    """A matching header and cookie must still match the session digest."""
    with pytest.raises(HTTPException) as error:
        require_csrf(make_auth_session(), "other-token", "other-token")

    assert (error.value.status_code, error.value.detail) == (403, "Invalid CSRF token")


@pytest.mark.unit
def test_require_csrf_rejects_non_ascii_token() -> None:
    """Untrusted non-ASCII tokens should be forbidden rather than raising a server error."""
    with pytest.raises(HTTPException) as error:
        require_csrf(make_auth_session(), "不正なトークン", "不正なトークン")

    assert (error.value.status_code, error.value.detail) == (403, "Invalid CSRF token")


@pytest.mark.unit
def test_require_csrf_accepts_matching_header_cookie_and_session() -> None:
    """The header, cookie, and session digest should pass when all match."""
    require_csrf(make_auth_session(), "valid-csrf-token", "valid-csrf-token")
