from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io

router = APIRouter()


@router.get("/reports/{extraction_id}/excel")
async def download_excel_report(extraction_id: str):
    from app.routers.extraction import _extraction_cache
    from app.services.reports.excel_report import generate_excel_report
    from app.services.analytics.engine import calculate_analytics

    result = _extraction_cache.get(extraction_id)
    if not result:
        raise HTTPException(404, "Report not found")

    analytics = result.analytics or calculate_analytics(result.students)
    excel_bytes = generate_excel_report(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )
    filename = f"ResultKraft_Report_{extraction_id[:8]}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
