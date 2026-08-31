"""Orchestrator Service — Coordinates document ingestion, AI pipelines, auth, and risk scoring."""

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
    logger.info("service_started", port=8007)
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
