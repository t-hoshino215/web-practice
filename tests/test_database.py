"""Tests for request-scoped database session management."""

from unittest.mock import MagicMock

import pytest
from pytest import MonkeyPatch

import database


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
