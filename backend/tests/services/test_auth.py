"""Tests for authentication and token utilities."""

import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from web_practice.config import SESSION_LIFETIME
from web_practice.services import auth


@pytest.mark.unit
def test_hash_password_can_be_verified() -> None:
    """A generated password hash should verify its source password."""
    password_hash = auth.hash_password("correct horse battery staple")

    result = auth.verify_password("correct horse battery staple", password_hash)

    assert result is True


@pytest.mark.unit
def test_verify_password_rejects_different_password() -> None:
    """Password verification should reject a different plaintext."""
    password_hash = auth.hash_password("original password")

    result = auth.verify_password("different password", password_hash)

    assert result is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("generator_name", "expected"),
    [("generate_session_token", "session-token"), ("generate_csrf_token", "csrf-token")],
)
def test_token_generators_request_32_random_bytes(
    monkeypatch: MonkeyPatch,
    generator_name: str,
    expected: str,
) -> None:
    """Security token generators should request the configured entropy size."""
    token_urlsafe = MagicMock(return_value=expected)
    monkeypatch.setattr(auth.secrets, "token_urlsafe", token_urlsafe)

    result = getattr(auth, generator_name)()

    assert (result, token_urlsafe.call_args.args) == (expected, (32,))


@pytest.mark.unit
@pytest.mark.parametrize("hasher", [auth.hash_session_token, auth.hash_csrf_token])
def test_token_hashes_use_sha256(hasher: object) -> None:
    """Persisted token representations should be deterministic SHA-256 digests."""
    expected = hashlib.sha256(b"raw-token").hexdigest()

    result = hasher("raw-token")  # type: ignore[operator]

    assert result == expected


@pytest.mark.unit
def test_create_session_expiration_uses_utc_lifetime(monkeypatch: MonkeyPatch) -> None:
    """Session expiration should be based on the configured lifetime in UTC."""
    current_time = datetime(2026, 8, 20, 1, 2, 3, tzinfo=UTC)
    datetime_mock = MagicMock()
    datetime_mock.now.return_value = current_time
    monkeypatch.setattr(auth, "datetime", datetime_mock)

    result = auth.create_session_expiration()

    assert result == current_time + SESSION_LIFETIME


@pytest.mark.unit
def test_valid_csrf_token_is_accepted() -> None:
    """A raw CSRF token should match its stored hash."""
    expected_hash = auth.hash_csrf_token("csrf-token")

    result = auth.is_valid_csrf_token("csrf-token", expected_hash)

    assert result is True


@pytest.mark.unit
def test_invalid_csrf_token_is_rejected() -> None:
    """A different CSRF token should not match the stored hash."""
    expected_hash = auth.hash_csrf_token("csrf-token")

    result = auth.is_valid_csrf_token("wrong-token", expected_hash)

    assert result is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("username", "expected"),
    [(" Alice ", "alice"), ("ADMIN", "admin"), ("first LAST", "first last")],
)
def test_normalize_username_trims_and_lowercases(username: str, expected: str) -> None:
    """Username normalization should remove outer whitespace and case variance."""
    result = auth.normalize_username(username)

    assert result == expected
