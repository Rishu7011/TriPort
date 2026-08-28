from fastapi import APIRouter

router = APIRouter(prefix="/score", tags=["risk"])

@router.post("/")
async def score():
    """Phase 3 stub — risk scoring. Full implementation in Phase 3."""
    return {"status": "not_implemented", "phase": 3}
