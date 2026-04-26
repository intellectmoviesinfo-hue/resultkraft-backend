import uuid
import re
from collections import OrderedDict
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, List
import io
import copy

from app.schemas.extraction import ExtractionResponse, FilterRequest, SortRequest
from app.services.extraction.pipeline import process_file
from app.services.extraction.validators import sanitize_filename
from app.services.analytics.engine import apply_filter, apply_sort, calculate_analytics
from app.services.reports.excel_report import generate_excel_report
from app.services.reports.pdf_report import (
    generate_summary_pdf,
    generate_rollwise_pdf,
    generate_ranked_pdf,
    generate_all_reports_zip,
)
from app.services.supabase_client import get_supabase
from app.utils.auth import get_user_id

import logging

logger = logging.getLogger("resultkraft.extraction")

router = APIRouter()


def _persist_extraction(user_id: str, extraction_id: str, filename: str, result: ExtractionResponse) -> None:
    """
    Insert extraction + student_results rows into Supabase.
    Service-role client bypasses RLS. Failures are logged but never break the user request.
    """
    sb = get_supabase()
    if sb is None:
        return  # DB unavailable — already persisted in cache, user still gets results
    try:
        sb.table("extractions").insert({
            "id": extraction_id,
            "user_id": user_id,
            "filename": filename,
            "file_type": result.file_type or "pdf",
            "university_detected": result.university_detected,
            "subject_selected": result.subject_selected,
            "subjects_found": list(result.subjects_found or []),
            "student_count": len(result.students or []),
            "pass_count": (result.analytics.pass_count if result.analytics else 0) or 0,
            "fail_count": (result.analytics.fail_count if result.analytics else 0) or 0,
            "pass_percentage": float(result.analytics.pass_percentage) if (result.analytics and result.analytics.pass_percentage is not None) else None,
            "average_marks": float(result.analytics.average_marks) if (result.analytics and result.analytics.average_marks is not None) else None,
            "status": result.status or "completed",
        }).execute()

        if result.students:
            rows = [{
                "extraction_id": extraction_id,
                "roll_number": s.roll_no or "",
                "student_name": getattr(s, "student_name", None),
                "father_name": getattr(s, "father_name", None),
                "subject_name": getattr(s, "subject_name", None),
                "external_marks": float(s.external_marks) if getattr(s, "external_marks", None) is not None else None,
                "internal_marks": float(s.internal_marks) if getattr(s, "internal_marks", None) is not None else None,
                "total_marks": float(s.total_marks) if s.total_marks is not None else None,
                "max_marks": float(s.max_marks) if getattr(s, "max_marks", None) is not None else None,
                "grade": getattr(s, "grade", None),
                "status": getattr(s, "status", None),
                "rank_in_class": getattr(s, "rank_in_class", None),
                "percentile": float(s.percentile) if getattr(s, "percentile", None) is not None else None,
            } for s in result.students]
            # Bulk insert in chunks of 500 to stay under request size limits
            for i in range(0, len(rows), 500):
                sb.table("student_results").insert(rows[i:i+500]).execute()
    except Exception as e:
        logger.warning(f"Supabase persistence failed for extraction {extraction_id}: {e}")


# Bounded LRU cache — max 200 entries, evicts oldest on overflow
class _BoundedCache:
    def __init__(self, max_size: int = 200):
        self._data: OrderedDict[str, ExtractionResponse] = OrderedDict()
        self._max = max_size

    def get(self, key: str) -> Optional[ExtractionResponse]:
        val = self._data.get(key)
        if val is not None:
            self._data.move_to_end(key)
        return val

    def set(self, key: str, value: ExtractionResponse) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) >= self._max:
            self._data.popitem(last=False)
        self._data[key] = value


_cache = _BoundedCache()


def _cache_key(user_id: str, extraction_id: str) -> str:
    return f"{user_id}:{extraction_id}"


@router.post("/extract", response_model=ExtractionResponse)
async def extract_file(
    file: UploadFile = File(...),
    subject: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id),
):
    content = await file.read()
    filename = sanitize_filename(file.filename or "unnamed")

    try:
        result = process_file(filename, content, subject_filter=subject)
        extraction_id = str(uuid.uuid4())
        result.extraction_id = extraction_id
        _cache.set(_cache_key(user_id, extraction_id), result)
        _persist_extraction(user_id, extraction_id, filename, result)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/extract-batch", response_model=ExtractionResponse)
async def extract_batch(
    files: List[UploadFile] = File(...),
    subject: Optional[str] = Form(None),
    user_id: str = Depends(get_user_id),
):
    """Process multiple files and merge results."""
    if len(files) > 5:
        raise HTTPException(400, "Maximum 5 files per batch upload")

    all_students = []
    all_subjects = set()
    university = None
    total_time = 0

    for upload in files:
        content = await upload.read()
        filename = sanitize_filename(upload.filename or "unnamed")
        try:
            result = process_file(filename, content, subject_filter=subject)
            all_students.extend(result.students)
            all_subjects.update(result.subjects_found)
            if result.university_detected and not university:
                university = result.university_detected
            total_time += result.processing_time_ms
        except ValueError as e:
            raise HTTPException(400, f"Error in {filename}: {str(e)}")

    # Deduplicate students by roll_no (keep first occurrence)
    seen = set()
    unique_students = []
    for s in all_students:
        if s.roll_no not in seen:
            seen.add(s.roll_no)
            unique_students.append(s)

    # Re-rank after merge
    unique_students.sort(key=lambda s: s.total_marks, reverse=True)
    n = len(unique_students)
    for i, s in enumerate(unique_students):
        s.rank_in_class = i + 1
        s.percentile = round(((n - i - 1) / n) * 100, 1) if n > 0 else 0

    analytics = calculate_analytics(unique_students) if unique_students else None

    extraction_id = str(uuid.uuid4())
    response = ExtractionResponse(
        extraction_id=extraction_id,
        status="completed",
        original_filename=f"{len(files)} files merged",
        file_type="batch",
        university_detected=university,
        subjects_found=sorted(all_subjects),
        subject_selected=subject,
        students=unique_students,
        analytics=analytics,
        processing_time_ms=total_time,
    )
    _cache.set(_cache_key(user_id, extraction_id), response)
    _persist_extraction(user_id, extraction_id, response.original_filename or "batch", response)
    return response


@router.get("/extract/{extraction_id}", response_model=ExtractionResponse)
async def get_extraction(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _cache.get(_cache_key(user_id, extraction_id))
    if not result:
        raise HTTPException(404, "Extraction not found or expired")
    return result


@router.post("/extract/{extraction_id}/select-subject", response_model=ExtractionResponse)
async def select_subject(
    extraction_id: str,
    subject: str = Form(...),
    user_id: str = Depends(get_user_id),
):
    result = _cache.get(_cache_key(user_id, extraction_id))
    if not result:
        raise HTTPException(404, "Extraction not found or expired")

    filtered_students = [s for s in result.students if s.subject_name == subject]
    result.subject_selected = subject
    result.students = filtered_students
    return result


@router.post("/extract/{extraction_id}/filter", response_model=ExtractionResponse)
async def filter_results(
    extraction_id: str,
    req: FilterRequest,
    user_id: str = Depends(get_user_id),
):
    result = _cache.get(_cache_key(user_id, extraction_id))
    if not result:
        raise HTTPException(404, "Extraction not found or expired")

    filtered = apply_filter(result.students, req.filter_type, req.value or "")
    response = copy.copy(result)
    response.students = filtered
    return response


@router.post("/extract/{extraction_id}/sort", response_model=ExtractionResponse)
async def sort_results(
    extraction_id: str,
    req: SortRequest,
    user_id: str = Depends(get_user_id),
):
    result = _cache.get(_cache_key(user_id, extraction_id))
    if not result:
        raise HTTPException(404, "Extraction not found or expired")

    sorted_students = apply_sort(result.students, req.sort_by)
    response = copy.copy(result)
    response.students = sorted_students
    return response


# ── Download endpoints ──────────────────────────────────────────────


def _get_result_or_404(user_id: str, extraction_id: str) -> ExtractionResponse:
    result = _cache.get(_cache_key(user_id, extraction_id))
    if not result:
        raise HTTPException(404, "Extraction not found or expired")
    if not result.students:
        raise HTTPException(400, "No student data to export")
    return result


def _safe_filename(base: str) -> str:
    return re.sub(r'[^\w\-]', '_', base)


@router.get("/extract/{extraction_id}/download/excel")
async def download_excel(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _get_result_or_404(user_id, extraction_id)
    analytics = result.analytics or calculate_analytics(result.students)

    excel_bytes = generate_excel_report(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )

    name = _safe_filename(f"{result.subject_selected or 'Report'}_Result_Analysis")
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'},
    )


@router.get("/extract/{extraction_id}/download/pdf-summary")
async def download_pdf_summary(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _get_result_or_404(user_id, extraction_id)
    analytics = result.analytics or calculate_analytics(result.students)

    pdf_bytes = generate_summary_pdf(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )

    name = _safe_filename(f"Summary_RESULT_LIST_{result.subject_selected or 'Report'}")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


@router.get("/extract/{extraction_id}/download/pdf-rollwise")
async def download_pdf_rollwise(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _get_result_or_404(user_id, extraction_id)
    analytics = result.analytics or calculate_analytics(result.students)

    pdf_bytes = generate_rollwise_pdf(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )

    name = _safe_filename(f"Roll_No_Wise_RESULT_LIST_{result.subject_selected or 'Report'}")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


@router.get("/extract/{extraction_id}/download/pdf-ranked")
async def download_pdf_ranked(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _get_result_or_404(user_id, extraction_id)
    analytics = result.analytics or calculate_analytics(result.students)

    pdf_bytes = generate_ranked_pdf(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )

    name = _safe_filename(f"RANKED_RESULT_LIST_{result.subject_selected or 'Report'}")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
    )


@router.get("/extract/{extraction_id}/download/all")
async def download_all(extraction_id: str, user_id: str = Depends(get_user_id)):
    result = _get_result_or_404(user_id, extraction_id)
    analytics = result.analytics or calculate_analytics(result.students)

    zip_bytes = generate_all_reports_zip(
        students=result.students,
        analytics=analytics,
        university_name=result.university_detected or "",
        subject_name=result.subject_selected or "",
    )

    name = _safe_filename(f"{result.subject_selected or 'Report'}_Complete_Analysis")
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
    )
