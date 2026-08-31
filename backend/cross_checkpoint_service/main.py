"""
Cross-Checkpoint Service — Multi-Identity Detection and Face Graph Analytics.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.cross_checkpoint_service.routers import clusters

configure_logging()
logger = get_logger("cross-checkpoint-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8008, service="cross-checkpoint-service")
    yield
    logger.info("service_stopped", port=8008)


app = FastAPI(
    title="TriPort — Cross-Checkpoint & Multi-Identity Service",
    version="0.1.0",
    lifespan=lifespan,
    description=(
        "Multi-Identity and Cross-Checkpoint Analytics: detects name discrepancies, "
        "document number swapping, impossible travel velocity across checkpoints, "
        "and tracks repeat offenders to auto-escalate threat levels."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(clusters.router)


@app.get("/health", tags=["health"])
async def health():
    return {
        "status": "ok",
        "service": "cross-checkpoint-service",
        "version": "0.1.0",
    }
