"""Tests for environment-derived application configuration."""

import runpy
from pathlib import Path

import pytest
from pytest import MonkeyPatch

CONFIG_PATH = Path(__file__).parents[1] / "app" / "config.py"


def load_config() -> dict[str, object]:
    """Execute config in isolation so environment cases cannot leak module state."""
    return runpy.run_path(str(CONFIG_PATH))


@pytest.mark.unit
def test_database_url_uses_environment(monkeypatch: MonkeyPatch) -> None:
    """DATABASE_URL should preserve the configured URL."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://tester@db/test_db")

    values = load_config()

    assert values["DATABASE_URL"] == "postgresql+psycopg://tester@db/test_db"


@pytest.mark.unit
def test_database_url_is_required(monkeypatch: MonkeyPatch) -> None:
    """Missing DATABASE_URL should fail fast during configuration."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(KeyError) as error:
        load_config()

    assert error.value.args == ("DATABASE_URL",)


@pytest.mark.unit
@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_cookie_secure_accepts_truthy_values(monkeypatch: MonkeyPatch, value: str) -> None:
    """Supported truthy spellings should enable Secure cookies."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("COOKIE_SECURE", value)

    values = load_config()

    assert values["COOKIE_SECURE"] is True


@pytest.mark.unit
@pytest.mark.parametrize("value", ["0", "false", "no", "off", "unexpected"])
def test_cookie_secure_rejects_other_values(monkeypatch: MonkeyPatch, value: str) -> None:
    """Unsupported values should leave Secure cookies disabled."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("COOKIE_SECURE", value)

    values = load_config()

    assert values["COOKIE_SECURE"] is False


@pytest.mark.unit
def test_cookie_secure_defaults_to_false(monkeypatch: MonkeyPatch) -> None:
    """Local development should default Secure cookies to disabled."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.delenv("COOKIE_SECURE", raising=False)

    values = load_config()

    assert values["COOKIE_SECURE"] is False
