"""Risk Engine — combines all module signals into a weighted risk score."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.risk_engine.routers import risk

configure_logging()
logger = get_logger("risk-engine")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8005)
    yield


app = FastAPI(title="BorderGuard-AI — Risk Engine", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(risk.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "risk-engine"}
