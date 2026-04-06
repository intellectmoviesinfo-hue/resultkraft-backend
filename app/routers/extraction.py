import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import io

from app.schemas.extraction import ExtractionResponse, FilterRequest, SortRequest
from app.services.extraction.pipeline import process_file
from app.services.analytics.engine import apply_filter, apply_sort
from app.services.reports.excel_report import generate_excel_report
from app.utils.auth import get_user_id

router = APIRouter()

# In-memory store for MVP (replace with Supabase in Phase 2)
# Keyed by (user_id, extraction_id) to prevent cross-user access
_extraction_cache: dict[str, ExtractionResponse] = {}


@router.post("/extract", response_model=ExtractionResponse)
async def extract_file(
    file: UploadFile = File(...),
    subject: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id),
):
    content = await file.read()
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    try:
        result = process_file(file.filename, content, subject_filter=subject)
        extraction_id = str(uuid.uuid4())
        result.extraction_id = extraction_id
        # Scope cache key to user to prevent cross-user data leaks
        _extraction_cache[f"{user_id}:{extraction_id}"] = result
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {str(e)}")


@router.get("/extract/{extraction_id}", response_model=ExtractionResponse)
async def get_extraction(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _extraction_cache.get(f"{user_id}:{extraction_id}")
    if not result:
        raise HTTPException(404, "Extraction not found")
    return result


@router.post("/extract/{extraction_id}/select-subject", response_model=ExtractionResponse)
async def select_subject(extraction_id: str, subject: str = Form(...), user_id: str = Depends(get_user_id)):
    result = _extraction_cache.get(f"{user_id}:{extraction_id}")
    if not result:
        raise HTTPException(404, "Extraction not found")

    filtered_students = [s for s in result.students if s.subject_name == subject]
    result.subject_selected = subject
    result.students = filtered_students
    return result


@router.post("/extract/{extraction_id}/filter", response_model=ExtractionResponse)
async def filter_results(extraction_id: str, req: FilterRequest, user_id: str = Depends(get_user_id)):
    result = _extraction_cache.get(f"{user_id}:{extraction_id}")
    if not result:
        raise HTTPException(404, "Extraction not found")

    filtered = apply_filter(result.students, req.filter_type, req.value or "")
    import copy
    response = copy.copy(result)
    response.students = filtered
    return response


@router.post("/extract/{extraction_id}/sort", response_model=ExtractionResponse)
async def sort_results(extraction_id: str, req: SortRequest, user_id: str = Depends(get_user_id)):
    result = _extraction_cache.get(f"{user_id}:{extraction_id}")
    if not result:
        raise HTTPException(404, "Extraction not found")

    sorted_students = apply_sort(result.students, req.sort_by)
    import copy
    response = copy.copy(result)
    response.students = sorted_students
    return response


@router.get("/extract/{extraction_id}/download/excel")
async def download_excel(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _extraction_cache.get(f"{user_id}:{extraction_id}")
    if not result:
        raise HTTPException(404, "Extraction not found")
    if not result.students:
        raise HTTPException(400, "No student data to export")

    from app.services.analytics.engine import calculate_analytics
    analytics = result.analytics or calculate_analytics(result.students)

    excel_bytes = generate_excel_report(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )

    filename = f"ResultKraft_{result.university_detected or 'Report'}_{result.subject_selected or 'All'}.xlsx"
    filename = filename.replace(" ", "_")

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
