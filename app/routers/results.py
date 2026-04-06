from fastapi import APIRouter, HTTPException
from app.schemas.extraction import ExtractionResponse

router = APIRouter()


@router.get("/results/{extraction_id}", response_model=ExtractionResponse)
async def get_results(extraction_id: str):
    from app.routers.extraction import _extraction_cache
    result = _extraction_cache.get(extraction_id)
    if not result:
        raise HTTPException(404, "Results not found. The session may have expired.")
    return result
