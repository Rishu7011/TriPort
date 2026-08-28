"""Risk Engine — combines all module signals into a weighted risk score."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.risk_engine.routers import risk

configure_logging()
logger = get_logger("risk-engine")

app = FastAPI(title="BorderGuard-AI — Risk Engine", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(risk.router)

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "risk-engine"}

@app.on_event("startup")
async def on_startup():
    logger.info("service_started", port=8005)
