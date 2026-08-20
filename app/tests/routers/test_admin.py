"""HTTP contract tests for administrator routes."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user
from tests.factories import create_message, create_user


@pytest.mark.integration
def test_admin_lists_all_users_in_id_order(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Administrators should receive all safe user records in ID order."""
    admin = create_user(db_session, username="admin", role="admin")
    regular = create_user(db_session, username="alice")
    test_app.dependency_overrides[get_current_user] = lambda: admin

    response = client.get("/admin/users")

    assert [(user["id"], set(user)) for user in response.json()] == [
        (admin.id, {"id", "username", "role", "created_at"}),
        (regular.id, {"id", "username", "role", "created_at"}),
    ]


@pytest.mark.integration
def test_admin_lists_all_messages_in_id_order(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Administrators should receive messages from every owner in ID order."""
    admin = create_user(db_session, username="admin", role="admin")
    regular = create_user(db_session, username="alice")
    first = create_message(db_session, user=regular, text="first")
    second = create_message(db_session, user=admin, text="second")
    test_app.dependency_overrides[get_current_user] = lambda: admin

    response = client.get("/admin/messages")

    assert [message["id"] for message in response.json()] == [first.id, second.id]


@pytest.mark.integration
def test_admin_route_rejects_regular_user(
    client: TestClient,
    test_app: FastAPI,
    db_session: Session,
) -> None:
    """Authenticated regular users should receive forbidden from admin routes."""
    user = create_user(db_session)
    test_app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/admin/users")

    assert (response.status_code, response.json()) == (
        403,
        {"detail": "Administrator privileges required"},
    )


@pytest.mark.integration
def test_admin_route_requires_authentication(client: TestClient) -> None:
    """Unauthenticated clients should receive 401 before authorization checks."""
    response = client.get("/admin/messages")

    assert (response.status_code, response.json()) == (401, {"detail": "Authentication required"})
