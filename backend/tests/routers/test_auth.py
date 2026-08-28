"""HTTP contract tests for login and logout."""

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx2 import Response
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.factories import create_auth_session, create_user
from web_practice.dependencies.auth import get_current_auth_session
from web_practice.models import AuthSession
from web_practice.routers import auth as auth_router
from web_practice.services import hash_csrf_token, hash_password, hash_session_token


def login_successfully(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> Response:
    """Create credentials and perform a deterministic successful login."""
    create_user(db_session, username="alice", password_hash=hash_password("password123"))
    monkeypatch.setattr(auth_router, "generate_session_token", lambda: "raw-session-token")
    monkeypatch.setattr(auth_router, "generate_csrf_token", lambda: "raw-csrf-token")
    return cast(
        Response,
        client.post("/api/login", json={"username": " ALICE ", "password": "password123"}),
    )


@pytest.mark.integration
def test_login_returns_user_and_csrf_token(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """Valid credentials should return safe user data and the raw CSRF token."""
    response = login_successfully(client, db_session, monkeypatch)

    assert (
        response.status_code,
        response.json()["user"]["username"],
        response.json()["csrf_token"],
    ) == (
        200,
        "alice",
        "raw-csrf-token",
    )


@pytest.mark.integration
def test_login_persists_only_hashed_tokens(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """The database should store token digests rather than raw credentials."""
    login_successfully(client, db_session, monkeypatch)

    auth_session = db_session.scalar(select(AuthSession))

    assert auth_session is not None and (
        auth_session.token_hash,
        auth_session.csrf_token_hash,
    ) == (
        hash_session_token("raw-session-token"),
        auth_router.hash_csrf_token("raw-csrf-token"),
    )


@pytest.mark.integration
def test_login_sets_hardened_session_cookie(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """Login should set the session cookie with its security attributes."""
    response = login_successfully(client, db_session, monkeypatch)

    set_cookie = response.headers["set-cookie"]

    assert all(
        attribute in set_cookie
        for attribute in [
            "session=raw-session-token",
            "HttpOnly",
            "Max-Age=604800",
            "Path=/",
            "SameSite=lax",
        ]
    )


@pytest.mark.integration
def test_login_sets_readable_csrf_cookie(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """Login should expose the CSRF token in a non-HttpOnly cookie."""
    response = login_successfully(client, db_session, monkeypatch)

    csrf_cookie = next(value for value in response.headers.get_list("set-cookie") if value.startswith("csrf_token="))

    assert (
        all(
            attribute in csrf_cookie
            for attribute in ["csrf_token=raw-csrf-token", "Max-Age=604800", "Path=/", "SameSite=lax"]
        )
        and "HttpOnly" not in csrf_cookie
    )


@pytest.mark.integration
def test_login_sets_secure_cookie_when_enabled(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """HTTPS deployments should add Secure to the session cookie."""
    monkeypatch.setattr(auth_router, "COOKIE_SECURE", True)

    response = login_successfully(client, db_session, monkeypatch)

    assert all("Secure" in cookie for cookie in response.headers.get_list("set-cookie"))


@pytest.mark.integration
def test_refresh_csrf_requires_authentication(client: TestClient) -> None:
    """An unauthenticated caller must not rotate a CSRF token."""
    response = client.post("/api/auth/csrf")

    assert (response.status_code, response.json()) == (
        401,
        {"detail": "Authentication required"},
    )


@pytest.mark.integration
def test_refresh_csrf_rotates_session_digest_and_cookie(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    """An authenticated refresh should replace both CSRF representations."""
    auth_session = configure_logout(client, test_app, db_session)
    monkeypatch.setattr(auth_router, "generate_csrf_token", lambda: "rotated-csrf-token")

    response = client.post("/api/auth/csrf")
    csrf_cookie = next(value for value in response.headers.get_list("set-cookie") if value.startswith("csrf_token="))

    assert (
        response.status_code,
        auth_session.csrf_token_hash,
        "csrf_token=rotated-csrf-token" in csrf_cookie,
    ) == (
        204,
        hash_csrf_token("rotated-csrf-token"),
        True,
    )


@pytest.mark.integration
def test_login_rejects_unknown_user(client: TestClient) -> None:
    """Unknown usernames should receive the generic credential failure."""
    response = client.post("/api/login", json={"username": "missing", "password": "password123"})

    assert (response.status_code, response.json()) == (
        401,
        {"detail": "Invalid username or password"},
    )


@pytest.mark.integration
def test_login_rejects_wrong_password(client: TestClient, db_session: Session) -> None:
    """Wrong passwords should receive the same generic credential failure."""
    create_user(db_session, username="alice", password_hash=hash_password("correct-password"))

    response = client.post("/api/login", json={"username": "alice", "password": "wrong-password"})

    assert (response.status_code, response.json()) == (
        401,
        {"detail": "Invalid username or password"},
    )


def configure_logout(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
    *,
    session_cookie: str | None = "raw-session-token",
) -> AuthSession:
    """Create and override an authenticated session for logout requests."""
    user = create_user(db_session)
    auth_session = create_auth_session(
        db_session,
        user=user,
        token="raw-session-token",
        csrf_token="raw-csrf-token",
    )
    test_app.dependency_overrides[get_current_auth_session] = lambda: auth_session
    if session_cookie is not None:
        client.cookies.set("session", session_cookie)
    client.cookies.set("csrf_token", "raw-csrf-token")
    return auth_session


@pytest.mark.integration
def test_logout_deletes_session(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """A valid logout should remove the persisted session."""
    auth_session = configure_logout(client, test_app, db_session)

    response = client.post("/api/logout", headers={"X-CSRF-Token": "raw-csrf-token"})

    assert (response.status_code, db_session.get(AuthSession, auth_session.id)) == (
        204,
        None,
    )


@pytest.mark.integration
def test_logout_expires_cookie(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Logout should instruct the browser to delete its session cookie."""
    configure_logout(client, test_app, db_session)

    response = client.post("/api/logout", headers={"X-CSRF-Token": "raw-csrf-token"})

    expired_cookies = response.headers.get_list("set-cookie")

    assert all(
        any(name in cookie and "Max-Age=0" in cookie for cookie in expired_cookies)
        for name in ["session=", "csrf_token="]
    )


@pytest.mark.integration
def test_logout_requires_csrf(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """An authenticated logout without a CSRF header should be forbidden."""
    configure_logout(client, test_app, db_session)

    response = client.post("/api/logout")

    assert (response.status_code, response.json()) == (
        403,
        {"detail": "CSRF token required"},
    )


@pytest.mark.integration
@pytest.mark.parametrize("session_cookie", [None, "unknown-session-token"])
def test_logout_is_idempotent_without_matching_cookie_session(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
    session_cookie: str | None,
) -> None:
    """The handler should safely clear cookies even when no DB session matches."""
    configure_logout(client, test_app, db_session, session_cookie=session_cookie)

    response = client.post("/api/logout", headers={"X-CSRF-Token": "raw-csrf-token"})

    assert response.status_code == 204
