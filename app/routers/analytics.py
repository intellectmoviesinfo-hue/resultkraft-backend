from fastapi import APIRouter, HTTPException
from app.schemas.extraction import AnalyticsSummary
from app.services.analytics.engine import calculate_analytics

router = APIRouter()


@router.get("/analytics/{extraction_id}", response_model=AnalyticsSummary)
async def get_analytics(extraction_id: str):
    from app.routers.extraction import _extraction_cache
    result = _extraction_cache.get(extraction_id)
    if not result:
        raise HTTPException(404, "Extraction not found")
    analytics = result.analytics or calculate_analytics(result.students)
    return analytics
