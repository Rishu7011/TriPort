from fastapi import APIRouter

router = APIRouter(prefix="/detect", tags=["tampering"])

@router.post("/")
async def detect():
    """Phase 2A stub — tampering detection. Full implementation in Phase 2."""
    return {"status": "not_implemented", "phase": 2}
