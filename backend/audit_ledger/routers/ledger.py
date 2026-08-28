from fastapi import APIRouter

router = APIRouter(prefix="/events", tags=["ledger"])

@router.post("/")
async def append_event():
    """Phase 4A stub — ledger event append. Full implementation in Phase 4."""
    return {"status": "not_implemented", "phase": 4}

@router.get("/verify")
async def verify_chain():
    """Phase 4A stub — chain integrity verification. Full implementation in Phase 4."""
    return {"status": "not_implemented", "phase": 4}
