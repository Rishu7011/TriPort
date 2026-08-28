"""
DB Session — async SQLAlchemy session factory.

CONCEPT: A "session" is a unit of work with the database.
Think of it like a shopping cart:
  - You add items (add/update/delete rows) to the session
  - Nothing hits Postgres until you call session.commit()
  - If something goes wrong, session.rollback() undoes everything

WHY ASYNC?
FastAPI uses Python's asyncio event loop. If a DB call is synchronous
(blocking), it freezes the entire event loop while waiting for Postgres.
Async sessions return control to the event loop during the wait, so other
requests can be handled in parallel. asyncpg is the async Postgres driver
that makes this possible.

HOW TO USE (in a FastAPI route):
    async def my_route(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Document).where(...))
        return result.scalars().all()
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

# create_async_engine: the connection pool to Postgres
# pool_pre_ping=True: test connections before use (avoids "connection lost" errors
# after the DB restarts or an idle connection times out)
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,  # set True to log every SQL statement (useful for debugging)
)

# async_sessionmaker: a factory that creates new AsyncSession objects
# expire_on_commit=False: after commit(), keep ORM objects usable in the
# same request — otherwise accessing .id after commit() would trigger another DB query
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a DB session for the duration of a request.

    The `async with` block guarantees the session is closed (and connection
    returned to the pool) even if the route raises an exception.

    Usage in a router:
        from backend.orchestrator.db.session import get_db
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        yield session
