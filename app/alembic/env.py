from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import web_practice.models  # noqa: F401
from web_practice.config import DATABASE_URL
from web_practice.database import Base

# this is the Alembic Config object, which provides access to the values within the .ini file in use.
alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

database_url = DATABASE_URL

# ConfigParserで%が解釈されるのを防ぐ
alembic_config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

# AlembicがDBとSQLAlchemyのモデルを比較するために必要なメタデータを指定
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = alembic_config.get_section(
        alembic_config.config_ini_section,
        {},
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
