"""Tests for FastAPI application assembly and lifespan cleanup."""

import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from pytest import MonkeyPatch

import main


@pytest.mark.unit
def test_create_app_registers_expected_routes() -> None:
    """The application factory should expose every business route."""
    application = main.create_app()

    routes = {
        (method.upper(), path) for path, operations in application.openapi()["paths"].items() for method in operations
    }

    assert {
        ("GET", "/"),
        ("GET", "/health"),
        ("GET", "/db-health"),
        ("GET", "/messages"),
        ("POST", "/messages"),
        ("PATCH", "/messages/{message_id}/archive"),
        ("POST", "/users"),
        ("GET", "/users/me"),
        ("GET", "/admin/users"),
        ("GET", "/admin/messages"),
        ("POST", "/login"),
        ("POST", "/logout"),
    } <= routes


@pytest.mark.unit
def test_lifespan_disposes_engine_on_shutdown(monkeypatch: MonkeyPatch) -> None:
    """Leaving the lifespan context should dispose the shared engine."""
    dispose = MagicMock()
    monkeypatch.setattr(main.engine, "dispose", dispose)

    async def exercise_lifespan() -> None:
        async with main.lifespan(FastAPI()):
            pass

    asyncio.run(exercise_lifespan())

    dispose.assert_called_once_with()
