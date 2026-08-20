"""HTTP and transaction tests for user routes."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import create_user
from web_practice.dependencies.auth import get_current_user
from web_practice.models import User
from web_practice.routers import users as users_router
from web_practice.schemas import UserCreate
from web_practice.services import verify_password


@pytest.mark.integration
def test_create_user_normalizes_username(client: TestClient) -> None:
    """Registration should persist a canonical lowercase username."""
    response = client.post("/users", json={"username": "Alice", "password": "password123"})

    assert (response.status_code, response.json()["username"]) == (201, "alice")


@pytest.mark.integration
def test_create_user_response_hides_password(client: TestClient) -> None:
    """Registration responses must never expose passwords or their hashes."""
    response = client.post("/users", json={"username": "alice", "password": "password123"})

    assert set(response.json()) == {"id", "username", "role", "created_at"}


@pytest.mark.integration
def test_create_user_hashes_password_before_persisting(client: TestClient, db_session: Session) -> None:
    """Registration should store a verifiable hash and never the plaintext password."""
    plaintext = "password123"

    response = client.post("/users", json={"username": "alice", "password": plaintext})
    user = db_session.scalar(select(User).where(User.username == "alice"))

    assert (
        response.status_code == 201
        and user is not None
        and (
            user.password_hash != plaintext,
            verify_password(plaintext, user.password_hash),
        )
        == (True, True)
    )


@pytest.mark.integration
def test_create_user_rejects_duplicate_username(client: TestClient, db_session: Session) -> None:
    """Registration should reject an existing canonical username."""
    create_user(db_session, username="alice")

    response = client.post("/users", json={"username": "ALICE", "password": "password123"})

    assert (response.status_code, response.json()) == (409, {"detail": "Username already exists"})


@pytest.mark.unit
def test_create_user_rolls_back_unique_race(monkeypatch: MonkeyPatch) -> None:
    """A commit-time uniqueness race should rollback before returning conflict."""
    db = MagicMock(spec=Session)
    db.scalar.return_value = None
    db.commit.side_effect = IntegrityError("statement", {}, Exception("duplicate"))
    monkeypatch.setattr(users_router, "hash_password", MagicMock(return_value="hash"))

    with pytest.raises(HTTPException) as error:
        users_router.create_user(UserCreate(username="alice", password="password123"), db)

    assert (error.value.status_code, db.rollback.call_count) == (409, 1)


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "password123"},
        {"username": "alice", "password": "short"},
    ],
)
def test_create_user_rejects_invalid_payload(client: TestClient, payload: dict[str, str]) -> None:
    """Registration input outside schema boundaries should return 422."""
    response = client.post("/users", json=payload)

    assert response.status_code == 422


@pytest.mark.integration
def test_get_me_returns_current_user(client: TestClient, test_app: FastAPI, db_session: Session) -> None:
    """Authenticated users should receive their own public profile."""
    user = create_user(db_session, username="alice")
    test_app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/users/me")

    assert (response.status_code, response.json()["id"]) == (200, user.id)


@pytest.mark.integration
def test_get_me_requires_authentication(client: TestClient) -> None:
    """Requests without a session cookie should not expose a profile."""
    response = client.get("/users/me")

    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
