"""
Validation & Tampering Combined Service Gateway.

Contains ONLY:
  1. Validation Service: /api/v1/validation/*
  2. Tampering & Stamp Forensics Service: /api/v1/tampering/*
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger

# Import validation and tampering routers
try:
    from backend.validation_and_tampering.validation_service.routers.validation import (
        router as validation_router,
    )
except ImportError:
    from backend.validation_service.routers.validation import (
        router as validation_router,
    )

try:
    from backend.validation_and_tampering.tampering_service.routers.tampering import (
        router as tampering_router,
    )
except ImportError:
    from backend.tampering_service.routers.tampering import (
        router as tampering_router,
    )

configure_logging()
logger = get_logger("validation_tampering_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Validation & Tampering combined service started successfully")
    yield


app = FastAPI(
    title="TriPort — Validation & Tampering Service Suite",
    description="Combined deployment unit serving ONLY Document Validation and Tampering Forensics services.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount ONLY Validation and Tampering microservice routers
app.include_router(validation_router)
app.include_router(tampering_router)


@app.get("/health", tags=["health"])
async def health():
    return {
        "status": "ok",
        "service": "validation-tampering-service",
        "deployed_modules": [
            "validation_service",
            "tampering_service",
        ],
    }
