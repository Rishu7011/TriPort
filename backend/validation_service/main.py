"""Validation Service — evaluates extracted fields against document rules."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.validation_service.routers import validation

configure_logging()
logger = get_logger("validation-service")

app = FastAPI(title="BorderGuard-AI — Validation Service", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(validation.router)

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "validation-service"}

@app.on_event("startup")
async def on_startup():
    logger.info("service_started", port=8002)
