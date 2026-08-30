"""OCR Service — extracts structured fields from identity documents."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.ocr_service.routers import extraction

configure_logging()
logger = get_logger("ocr-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8001)
    yield


app = FastAPI(
    title="TriPort — OCR & Document Classification Service",
    description="Multi-Modal OCR, MRZ parsing, and classification across Airport, Land Border, and Sea checkpoints.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(extraction.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "ocr-service"}
