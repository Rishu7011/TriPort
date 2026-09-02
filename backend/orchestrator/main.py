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

from backend.orchestrator.routers import documents, auth
from backend.orchestrator.routers import analytics
from backend.audit_ledger.routers import ledger

configure_logging()
logger = get_logger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("server_startup_warming_models", port=8007)
    
    # 1. Warm-up Database Connection Pool
    try:
        from backend.orchestrator.db.session import init_engine_and_tables
        await init_engine_and_tables()
        logger.info("db_engine_warmed_up")
    except Exception as e:
        logger.warning("db_warmup_failed", error=str(e))

    # 2. Warm-up EasyOCR Engine (load weights into memory once)
    try:
        import asyncio
        from backend.ocr_service.core.field_extractor import get_ocr_reader
        await asyncio.to_thread(get_ocr_reader)
        logger.info("easyocr_engine_warmed_up")
    except Exception as e:
        logger.warning("ocr_warmup_failed", error=str(e))

    # 3. Warm-up AWS Rekognition Client
    try:
        from backend.face_service.core.aws_rekognition import get_rekognition_client
        get_rekognition_client()
        logger.info("aws_rekognition_client_warmed_up")
    except Exception as e:
        logger.warning("rekognition_warmup_failed", error=str(e))

    yield


app = FastAPI(
    title="TriPort — Orchestrator Gateway",
    description="Main orchestrator, gateway, and security coordinator for TriPort AI screening system.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router)
app.include_router(ledger.router, prefix="/api/v1/audit")
app.include_router(analytics.router)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    tb = traceback.format_exc()
    logger.error("global_unhandled_exception", error=str(exc))
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "orchestrator"}
