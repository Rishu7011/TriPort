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
