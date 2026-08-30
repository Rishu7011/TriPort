"""Tampering Service — ELA, metadata forensics, boundary analysis, stamp matching."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.tampering_service.routers import tampering

configure_logging()
logger = get_logger("tampering-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8003)
    yield


app = FastAPI(title="TriPort — Tampering Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(tampering.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "tampering-service"}
