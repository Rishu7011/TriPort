"""
Alembic env.py — the bridge between Alembic and your SQLAlchemy models.

CONCEPT: Alembic is "git for your database schema."
  - Each migration file = one commit
  - `alembic upgrade head` = apply all pending migrations
  - `alembic downgrade -1` = roll back the last migration
  - `alembic revision --autogenerate -m "add index"` = Alembic compares
    your models.py against the current DB state and generates the diff

WHY autogenerate?
Without it, you'd write raw SQL for every schema change. With it, you
change models.py and Alembic writes the migration for you. You review it,
then apply it. Much safer.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base so Alembic can see all models via Base.metadata
# This is why every model must inherit from the same Base
from backend.orchestrator.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata: tells Alembic what the "desired" schema looks like
# (i.e. what's in your Python models)
target_metadata = Base.metadata


def get_url() -> str:
    """Read DATABASE_URL from environment — never hardcode credentials."""
    url = os.environ.get("DATABASE_URL", "")
    # asyncpg uses postgresql+asyncpg:// scheme
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def run_migrations_offline() -> None:
    """
    Offline mode: generate SQL scripts without connecting to DB.
    Useful when you want to review the SQL before running it.
    Run with: alembic upgrade head --sql
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Online mode: connect to DB and apply migrations directly.
    This is the normal mode used by `alembic upgrade head`.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pooling during migrations
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
