"""HTTP contract tests for user-owned message routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import get_current_auth_session, get_current_user
from models import AuthSession, Message, User
from tests.factories import create_auth_session, create_message, create_user


def authenticate(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
    *,
    username: str = "alice",
) -> tuple[User, AuthSession]:
    """Override auth dependencies with a persisted user and session."""
    user = create_user(db_session, username=username)
    auth_session = create_auth_session(db_session, user=user, csrf_token="csrf-token")
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_current_auth_session] = lambda: auth_session
    client.cookies.set("session", "test-session-token")
    return user, auth_session


@pytest.mark.integration
def test_list_messages_filters_owner_and_orders_by_id(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Users should see only their messages in creation order."""
    user, _ = authenticate(client, test_app, db_session)
    other_user = create_user(db_session, username="bob")
    first = create_message(db_session, user=user, text="first")
    second = create_message(db_session, user=user, text="second")
    create_message(db_session, user=other_user, text="hidden")

    response = client.get("/messages")

    assert [message["id"] for message in response.json()] == [first.id, second.id]


@pytest.mark.integration
def test_create_message_assigns_current_user(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Message ownership should always come from the current session user."""
    user, _ = authenticate(client, test_app, db_session)

    response = client.post("/messages", json={"text": "hello"}, headers={"X-CSRF-Token": "csrf-token"})
    message = db_session.scalar(select(Message).where(Message.text == "hello"))

    assert (response.status_code, response.json()["text"], message.user_id if message else None) == (
        200,
        "hello",
        user.id,
    )


@pytest.mark.integration
@pytest.mark.parametrize("text", ["", "x" * 256])
def test_create_message_rejects_invalid_text(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
    text: str,
) -> None:
    """Message text outside schema boundaries should return 422."""
    authenticate(client, test_app, db_session)

    response = client.post("/messages", json={"text": text}, headers={"X-CSRF-Token": "csrf-token"})

    assert response.status_code == 422


@pytest.mark.integration
def test_create_message_requires_csrf(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Authenticated message creation without CSRF proof should be forbidden."""
    authenticate(client, test_app, db_session)

    response = client.post("/messages", json={"text": "hello"})

    assert (response.status_code, response.json()) == (403, {"detail": "CSRF token required"})


@pytest.mark.integration
def test_archive_message_marks_owned_message(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Owners should be able to archive their messages."""
    user, _ = authenticate(client, test_app, db_session)
    message = create_message(db_session, user=user)

    response = client.patch(
        f"/messages/{message.id}/archive",
        headers={"X-CSRF-Token": "csrf-token"},
    )

    assert (response.status_code, response.json()["is_archived"]) == (200, True)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("headers", "detail"),
    [({}, "CSRF token required"), ({"X-CSRF-Token": "wrong-token"}, "Invalid CSRF token")],
)
def test_archive_message_rejects_invalid_csrf(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
    headers: dict[str, str],
    detail: str,
) -> None:
    """Archiving should reject both missing and mismatched CSRF tokens."""
    user, _ = authenticate(client, test_app, db_session)
    message = create_message(db_session, user=user)

    response = client.patch(f"/messages/{message.id}/archive", headers=headers)

    assert (response.status_code, response.json()) == (403, {"detail": detail})


@pytest.mark.integration
def test_archive_message_hides_other_users_message(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Archiving another user's message should reveal no ownership information."""
    authenticate(client, test_app, db_session)
    other_user = create_user(db_session, username="bob")
    message = create_message(db_session, user=other_user)

    response = client.patch(
        f"/messages/{message.id}/archive",
        headers={"X-CSRF-Token": "csrf-token"},
    )

    assert (response.status_code, response.json()) == (404, {"detail": "Message not found"})


@pytest.mark.integration
def test_list_messages_requires_authentication(client: TestClient) -> None:
    """Unauthenticated clients should not receive message data."""
    response = client.get("/messages")

    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
