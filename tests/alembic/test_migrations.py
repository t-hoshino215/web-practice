"""Safe structural and PostgreSQL integration tests for Alembic migrations."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pytest import MonkeyPatch
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url

APP_DIR = Path(__file__).parents[2] / "app"
ALEMBIC_INI = APP_DIR / "alembic.ini"
AMBIENT_DATABASE_URL_ENV = "PYTEST_AMBIENT_DATABASE_URL"
EXPECTED_CHAIN = [
    ("081ce138bdf1", "91c6f022b77c"),
    ("91c6f022b77c", "639486243669"),
    ("639486243669", "0b8ce0e2b3ed"),
    ("0b8ce0e2b3ed", "5f2d2558b4f3"),
    ("5f2d2558b4f3", "f0d9ba3f7511"),
    ("f0d9ba3f7511", "962b3addac54"),
    ("962b3addac54", None),
]


def run_alembic(database_url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run Alembic in an isolated process with an explicit database URL."""
    environment = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *arguments],
        cwd=APP_DIR,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def require_safe_postgresql_url() -> str:
    """Return a dedicated PostgreSQL URL or safely skip/fail before mutation."""
    value = os.getenv("TEST_DATABASE_URL")
    if value is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    url = make_url(value)
    database = url.database or ""
    ambient_url = os.getenv(AMBIENT_DATABASE_URL_ENV)
    if url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if not (database.startswith("test_") or database.endswith("_test")):
        pytest.fail(
            "TEST_DATABASE_URL database name must start with test_ or end with _test"
        )
    if ambient_url is not None and make_url(ambient_url) == url:
        pytest.fail("TEST_DATABASE_URL must not equal the ambient DATABASE_URL")

    local_hosts = {None, "localhost", "127.0.0.1", "::1", "postgres", "db"}
    remote_allowed = os.getenv("ALLOW_REMOTE_TEST_DATABASE") == "1"
    if url.host not in local_hosts and not remote_allowed:
        pytest.fail("Remote test databases require ALLOW_REMOTE_TEST_DATABASE=1")
    return value


def schema_objects(engine: Engine) -> set[str]:
    """Return user table and view names using a fresh inspector."""
    inspector = inspect(engine)
    return set(inspector.get_table_names()) | set(inspector.get_view_names())


@pytest.mark.unit
def test_revision_graph_has_one_linear_head() -> None:
    """Migration history should remain a single complete linear chain."""
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    revisions = [
        (revision.revision, revision.down_revision)
        for revision in script.walk_revisions()
    ]

    assert (script.get_heads(), revisions) == (["081ce138bdf1"], EXPECTED_CHAIN)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("direction", "revision_range"),
    [("upgrade", "base:head"), ("downgrade", "head:base")],
)
def test_postgresql_migrations_generate_offline_sql(
    direction: str, revision_range: str
) -> None:
    """Every migration direction should compile without connecting to a database."""
    result = run_alembic(
        "postgresql+psycopg://migration:test@localhost/test_migration",
        direction,
        revision_range,
        "--sql",
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_live_migration_without_test_url_skips(monkeypatch: MonkeyPatch) -> None:
    """Missing live DB configuration should safely skip destructive DDL."""
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    with pytest.raises(pytest.skip.Exception):
        require_safe_postgresql_url()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("test_url", "ambient_url"),
    [
        ("sqlite+pysqlite:///test_migration.db", None),
        ("postgresql+psycopg://tester@localhost/production", None),
        (
            "postgresql+psycopg://tester@localhost/test_migration",
            "postgresql+psycopg://tester@localhost/test_migration",
        ),
        ("postgresql+psycopg://tester@production.example.com/test_migration", None),
    ],
)
def test_live_migration_rejects_unsafe_url(
    monkeypatch: MonkeyPatch,
    test_url: str,
    ambient_url: str | None,
) -> None:
    """Unsafe dialect, name, ambient reuse, and remote host settings should fail."""
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.delenv("ALLOW_REMOTE_TEST_DATABASE", raising=False)
    if ambient_url is None:
        monkeypatch.delenv(AMBIENT_DATABASE_URL_ENV, raising=False)
    else:
        monkeypatch.setenv(AMBIENT_DATABASE_URL_ENV, ambient_url)

    with pytest.raises(pytest.fail.Exception):
        require_safe_postgresql_url()


@pytest.mark.integration
def test_upgrade_and_downgrade_on_dedicated_postgresql() -> None:
    """A clean, explicitly dedicated PostgreSQL DB should migrate both directions."""
    database_url = require_safe_postgresql_url()
    engine = create_engine(database_url)
    if schema_objects(engine):
        engine.dispose()
        pytest.fail("Dedicated migration database must be empty before the test")

    upgraded = False
    downgrade: subprocess.CompletedProcess[str] | None = None
    remaining_objects: set[str] = set()
    try:
        upgrade = run_alembic(database_url, "upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr
        upgraded = True

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        auth_columns = {
            column["name"] for column in inspector.get_columns("auth_sessions")
        }
        message_columns = {
            column["name"] for column in inspector.get_columns("messages")
        }
        unique_indexes = {
            index["name"]
            for table in ("users", "auth_sessions")
            for index in inspector.get_indexes(table)
            if index["unique"]
        }
        foreign_keys = {
            foreign_key["name"]
            for table in ("auth_sessions", "messages")
            for foreign_key in inspector.get_foreign_keys(table)
        }
        check_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("users")
        }
        assert (
            tables,
            user_columns,
            auth_columns,
            message_columns,
            unique_indexes,
            foreign_keys,
            check_constraints,
        ) == (
            {"alembic_version", "users", "auth_sessions", "messages"},
            {"id", "username", "password_hash", "role", "created_at"},
            {
                "id",
                "user_id",
                "token_hash",
                "csrf_token_hash",
                "expires_at",
                "created_at",
            },
            {"id", "text", "is_archived", "created_at", "user_id"},
            {"ix_users_username", "ix_auth_sessions_token_hash"},
            {"auth_sessions_user_id_fkey", "messages_user_id_fkey"},
            {"ck_users_role"},
        )
    finally:
        try:
            if upgraded:
                downgrade = run_alembic(database_url, "downgrade", "base")
                if downgrade.returncode == 0:
                    # Alembic intentionally retains its empty version table at base.
                    with engine.begin() as connection:
                        connection.execute(text("DROP TABLE alembic_version"))
                remaining_objects = schema_objects(engine)
        finally:
            engine.dispose()

    assert downgrade is not None and downgrade.returncode == 0, (
        downgrade.stderr if downgrade else ""
    )
    assert remaining_objects == set()
