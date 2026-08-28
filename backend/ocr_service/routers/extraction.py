from fastapi import APIRouter

router = APIRouter(prefix="/extract", tags=["extraction"])


@router.post("/")
async def extract_fields():
    """Phase 1A stub — OCR extraction. Full implementation in Phase 1."""
    return {"status": "not_implemented", "phase": 1}
