"""Orchestrator Service — Coordinates document ingestion, AI pipelines, and risk scoring."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8007)
    yield


app = FastAPI(
    title="BorderGuard-AI — Orchestrator",
    description="Main orchestrator and API gateway for BorderGuard-AI.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "orchestrator"}
