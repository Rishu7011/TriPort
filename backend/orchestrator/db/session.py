"""
DB Session — async SQLAlchemy session factory with automatic fallback.
"""

import asyncio
import os
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings
from backend.logging_config import get_logger
from backend.orchestrator.db.models import Base

logger = get_logger("orchestrator.db.session")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_init_lock = asyncio.Lock()


def _get_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def init_engine_and_tables() -> AsyncEngine:
    global _engine, _session_factory

    if _engine is not None:
        return _engine

    async with _init_lock:
        if _engine is not None:
            return _engine

        target_url = settings.database_url
        engine_kwargs = {"echo": False, "pool_pre_ping": True}
        is_postgres_ready = False

        if "postgresql" in target_url:
            ctx = _get_ssl_context()
            test_engine = None
            try:
                test_engine = create_async_engine(
                    target_url,
                    connect_args={"ssl": ctx},
                    **engine_kwargs,
                )
                # Quick 3-second connection attempt
                async with asyncio.timeout(3.0):
                    async with test_engine.begin() as conn:
                        await conn.run_sync(Base.metadata.create_all)
                _engine = test_engine
                is_postgres_ready = True
                logger.info("db_connected_postgresql", url=target_url.split("@")[-1])
            except BaseException as exc:
                logger.warn(
                    "postgresql_connection_failed_fallback_sqlite",
                    reason=str(exc)[:120],
                )
                if test_engine is not None:
                    try:
                        await test_engine.dispose()
                    except Exception:
                        pass

        if not is_postgres_ready:
            sqlite_url = "sqlite+aiosqlite:///./triport.db"
            _engine = create_async_engine(sqlite_url, **engine_kwargs)
            async with _engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("db_fallback_sqlite_initialized", path="./triport.db")

        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session for the duration of a request."""
    if _engine is None or _session_factory is None:
        await init_engine_and_tables()

    async with _session_factory() as session:  # type: ignore
        yield session
