"""Shared fixtures for unit and integration tests."""

# ruff: noqa: E402

# Application imports must follow the test-only environment and path safeguards.

import os
import sys
from collections.abc import Iterator
from pathlib import Path

AMBIENT_DATABASE_URL_ENV = "PYTEST_AMBIENT_DATABASE_URL"
ambient_database_url = os.environ.get("DATABASE_URL")
if ambient_database_url is None:
    os.environ.pop(AMBIENT_DATABASE_URL_ENV, None)
else:
    os.environ[AMBIENT_DATABASE_URL_ENV] = ambient_database_url

# Application modules create their global engine at import time, so force an
# isolated URL before importing any application code.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["COOKIE_SECURE"] = "false"
APP_DIR = Path(__file__).parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import web_practice.models  # noqa: F401
from web_practice.database import Base, get_db
from web_practice.main import create_app


@pytest.fixture
def db_engine() -> Iterator[Engine]:
    """Provide an isolated SQLite database with foreign keys enabled."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, _record: object) -> None:
        """Enable SQLite foreign keys to match PostgreSQL ownership constraints."""
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(test_engine)
        test_engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Provide a database session that is closed after each test."""
    with Session(db_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def test_app(db_session: Session) -> Iterator[FastAPI]:
    """Create an application whose DB dependency uses the test session."""
    application = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
def client(test_app: FastAPI) -> Iterator[TestClient]:
    """Provide an HTTP client and run the application lifespan."""
    with TestClient(test_app) as test_client:
        yield test_client
