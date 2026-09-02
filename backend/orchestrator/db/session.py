"""
DB Session — async SQLAlchemy engine factory for Supabase (PostgreSQL + pgvector).

Driver: psycopg3 (psycopg[binary]) — the asyncio-native PostgreSQL driver that
fully supports Supabase's Supavisor transaction-mode pooler (port 6543).

Unlike asyncpg, psycopg3 does not use server-side prepared statements by default,
making it fully compatible with transaction-mode connection poolers.

Compatibility notes:
- URL scheme: postgresql+psycopg://
- SSL: sslmode=require is passed as a URL query parameter (standard PostgreSQL DSN)
- NullPool: Supavisor manages pooling; SQLAlchemy's pool is disabled
- Schema: managed by Alembic (alembic upgrade head) — NOT create_all at startup
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger("orchestrator.db.session")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_init_lock = asyncio.Lock()


def _build_database_url() -> str:
    """
    Build a psycopg3-compatible async database URL.

    - Converts postgresql+asyncpg:// or postgres:// to postgresql+psycopg://
    - Appends ?sslmode=require if not present (required for Supabase)
    """
    import re
    url = settings.database_url.strip()

    # Normalise scheme → psycopg asyncio driver
    replacements = [
        ("postgresql+asyncpg://", "postgresql+psycopg://"),
        ("postgres+asyncpg://",   "postgresql+psycopg://"),
        ("postgresql://",          "postgresql+psycopg://"),
        ("postgres://",            "postgresql+psycopg://"),
    ]
    for old, new in replacements:
        if url.startswith(old):
            url = new + url[len(old):]
            break

    # psycopg uses standard sslmode= query parameter
    if "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"

    return url


async def init_engine_and_tables() -> AsyncEngine:
    """
    Initialize the async SQLAlchemy engine connected to Supabase.
    Thread-safe via asyncio.Lock. Called once at startup.
    """
    global _engine, _session_factory

    if _engine is not None:
        return _engine

    async with _init_lock:
        if _engine is not None:
            return _engine

        url = _build_database_url()

        _engine = create_async_engine(
            url,
            echo=False,
            poolclass=NullPool,   # Supavisor manages pooling
            connect_args={"prepare_threshold": None},  # Disable prepared statements for Supavisor transaction pooler
        )

        # ── Startup health check ──────────────────────────────────────────
        try:
            async with asyncio.timeout(25.0):
                async with _engine.connect() as conn:
                    pg_version = (await conn.execute(text("SELECT version()"))).scalar()
                    pgv = (await conn.execute(
                        text("SELECT 1 FROM pg_extension WHERE extname='vector'")
                    )).scalar()

                    if not pgv:
                        logger.warning(
                            "pgvector_not_found",
                            hint="Run in Supabase SQL Editor: CREATE EXTENSION IF NOT EXISTS vector;",
                        )
                    else:
                        logger.info("pgvector_available")

                    logger.info(
                        "db_connected_supabase",
                        version=(pg_version or "")[:50],
                        host=url.split("@")[-1][:50],
                    )

        except asyncio.TimeoutError as exc:
            await _engine.dispose()
            _engine = None
            raise RuntimeError(
                "Timed out connecting to Supabase. Check DATABASE_URL and network."
            ) from exc
        except Exception as exc:
            logger.error("supabase_connection_failed", reason=str(exc)[:300])
            await _engine.dispose()
            _engine = None
            raise RuntimeError(
                f"Cannot connect to Supabase: {exc}\n"
                "Ensure DATABASE_URL is set to the Supabase Supavisor pooler URL "
                "(port 6543, transaction mode) with postgresql+psycopg:// scheme."
            ) from exc

        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a DB session for the duration of a request.
    The session is automatically closed on exit (NullPool closes the connection).
    """
    global _session_factory
    if _engine is None or _session_factory is None:
        try:
            await init_engine_and_tables()
        except Exception as exc:
            logger.error("get_db_initialization_failed", error=str(exc))
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service initializing or temporarily unavailable. Please retry in a moment.",
            ) from exc

    if _session_factory is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session factory not initialized.",
        )

    async with _session_factory() as session:
        yield session


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global async_sessionmaker, initializing if needed."""
    global _session_factory
    if _engine is None or _session_factory is None:
        await init_engine_and_tables()
    return _session_factory

