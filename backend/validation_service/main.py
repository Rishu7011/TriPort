"""Validation Service — evaluates extracted fields against document rules.

Services:
  - YAML-driven rules engine (hot-reload, no restart needed)
  - Database cross-check: SLTD, national blacklist, visa validity
  - Regional format rules: Nepal, Bhutan, Bangladesh, Myanmar
  - Offline-first SQLite cache with background Postgres sync
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.validation_service.routers import validation

configure_logging()
logger = get_logger("validation-service")


async def _background_offline_sync():
    """
    Periodically push offline decisions to Postgres when connectivity restores.
    Runs every 60 seconds as specified in Phase 3D.
    """
    from backend.validation_service.core.offline_cache import sync_pending_decisions_to_postgres

    while True:
        await asyncio.sleep(60)
        try:
            synced = await sync_pending_decisions_to_postgres()
            if synced > 0:
                logger.info("Background offline sync complete", synced_count=synced)
        except Exception as e:
            logger.debug("Background offline sync skipped", reason=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8002)

    # Start background offline sync task (Phase 3D)
    sync_task = asyncio.create_task(_background_offline_sync())
    logger.info("Background offline sync task started", interval_seconds=60)

    yield

    # Graceful shutdown
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    logger.info("service_stopped")


app = FastAPI(
    title="TriPort — Validation Service",
    version="0.3.0",
    lifespan=lifespan,
    description=(
        "Document Validation Engine: YAML rules, SLTD/blacklist database cross-checks, "
        "regional format rules for land-border nationals, offline-first SQLite cache."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(validation.router)


@app.get("/health", tags=["health"])
async def health():
    from backend.validation_service.core.offline_cache import get_offline_cache
    cache_stats = get_offline_cache().stats()
    return {
        "status": "ok",
        "service": "validation-service",
        "version": "0.3.0",
        "cache": cache_stats,
    }
