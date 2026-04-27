from fastapi import APIRouter, HTTPException, Depends
from app.schemas.extraction import ExtractionResponse
from app.utils.auth import get_user_id

router = APIRouter()


@router.get("/results/{extraction_id}", response_model=ExtractionResponse)
async def get_results(extraction_id: str, user_id: str = Depends(get_user_id)):
    """
    Retrieve a previously-extracted result by ID. Mirrors GET /extract/{id} —
    same cache, same auth, just a friendlier URL for the results page.
    """
    from app.routers.extraction import _cache, _cache_key
    result = _cache.get(_cache_key(user_id, extraction_id))
    if not result:
        raise HTTPException(404, "Results not found. The session may have expired.")
    return result
