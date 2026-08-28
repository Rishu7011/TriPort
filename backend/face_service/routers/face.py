from fastapi import APIRouter

router = APIRouter(prefix="/verify", tags=["face"])

@router.post("/")
async def verify():
    """Phase 2B stub — face verification. Full implementation in Phase 2."""
    return {"status": "not_implemented", "phase": 2}
