"""Audit Ledger — hash-chained append-only event log."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.logging_config import configure_logging, get_logger
from backend.audit_ledger.routers import ledger

configure_logging()
logger = get_logger("audit-ledger")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("service_started", port=8006)
    yield


app = FastAPI(title="TriPort — Audit Ledger", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(ledger.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "audit-ledger"}
