import sys
from pathlib import Path

# Ensure repo root is on sys.path so 'import backend.xxx' works from any directory
_repo_root = str(Path(__file__).resolve().parents[2])
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger

from backend.validation_service.routers import validation

configure_logging()
logger = get_logger("validation-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8002)
    yield
    logger.info("service_stopped")


app = FastAPI(
    title="TriPort — Validation Service",
    version="0.3.0",
    lifespan=lifespan,
    description=(
        "Document Validation Engine: YAML rules, in-memory SLTD/blacklist cross-checks, "
        "and regional format rules for land-border nationals."
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
    return {
        "status": "ok",
        "service": "validation-service",
        "version": "0.3.0",
    }
