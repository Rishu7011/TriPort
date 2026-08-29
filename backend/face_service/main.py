"""Face Service — 1:1 verification and 1:N deduplication using face embeddings."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.face_service.routers import face

configure_logging()
logger = get_logger("face-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8004)
    yield


app = FastAPI(title="BorderGuard-AI — Face Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(face.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "face-service"}
