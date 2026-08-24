"""Tests for request-scoped database session management."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

from web_practice import database

APP_DIR = Path(__file__).parents[1]


@pytest.mark.unit
def test_get_db_yields_session(monkeypatch: MonkeyPatch) -> None:
    """get_db should yield the session created by SessionLocal."""
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", MagicMock(return_value=session))

    generator = database.get_db()
    yielded = next(generator)
    generator.close()

    assert yielded is session


@pytest.mark.unit
def test_get_db_closes_session_after_success(monkeypatch: MonkeyPatch) -> None:
    """Completing dependency iteration should close its session."""
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", MagicMock(return_value=session))
    generator = database.get_db()
    next(generator)

    with pytest.raises(StopIteration):
        next(generator)

    session.close.assert_called_once_with()


@pytest.mark.unit
def test_get_db_closes_session_after_error(monkeypatch: MonkeyPatch) -> None:
    """Throwing an error into the dependency should still close its session."""
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", MagicMock(return_value=session))
    generator = database.get_db()
    next(generator)

    with pytest.raises(RuntimeError, match="request failed"):
        generator.throw(RuntimeError("request failed"))

    session.close.assert_called_once_with()


@pytest.mark.unit
def test_conftest_forces_global_engine_to_sqlite() -> None:
    """The ambient URL should be captured before imports are forced to SQLite."""
    ambient_url = "postgresql+psycopg://prod-user@prod.example/production"
    environment = {
        **os.environ,
        "DATABASE_URL": ambient_url,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys; sys.path.insert(0, '.'); import tests.conftest; from web_practice import database; "
            "print(database.engine.url); print(os.environ['PYTEST_AMBIENT_DATABASE_URL'])",
        ],
        cwd=APP_DIR,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert (result.returncode, result.stdout.splitlines()) == (
        0,
        ["sqlite+pysqlite:///:memory:", ambient_url],
    )
