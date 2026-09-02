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

from backend.face_service.routers import face

configure_logging()
logger = get_logger("face-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_starting", port=8004, message="Pre-warming face recognition models...")
    try:
        from backend.face_service.core.embedding import _get_insightface_app
        app_instance = _get_insightface_app()
        if app_instance is not None:
            logger.info("InsightFace ArcFace+RetinaFace model ready")
        else:
            logger.warning("InsightFace unavailable — DeepFace fallback will be used")
    except Exception as exc:
        logger.warning("Model pre-warm failed", error=str(exc))
    logger.info("service_started", port=8004)
    yield


app = FastAPI(title="TriPort — Face Service", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(face.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "face-service"}
