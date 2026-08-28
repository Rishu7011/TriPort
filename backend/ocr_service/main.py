"""OCR Service — extracts structured fields from identity documents."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.ocr_service.routers import extraction

configure_logging()
logger = get_logger("ocr-service")

app = FastAPI(
    title="BorderGuard-AI — OCR Service",
    description="Extracts structured fields via OCR and MRZ parsing.",
    version="0.1.0",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(extraction.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "ocr-service"}


@app.on_event("startup")
async def on_startup():
    logger.info("service_started", port=8001)
