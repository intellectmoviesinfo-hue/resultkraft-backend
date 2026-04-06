from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StudentRecord(BaseModel):
    roll_no: str
    enrollment_no: Optional[str] = None
    student_name: str
    father_name: Optional[str] = None
    ext_marks: float
    int_marks: float
    total_marks: float
    grade: str
    pass_fail: str
    rank_in_class: Optional[int] = None
    percentile: Optional[float] = None
    subject_name: Optional[str] = None


class AnalyticsSummary(BaseModel):
    total_students: int
    pass_count: int
    fail_count: int
    pass_percentage: float
    class_average: float
    highest_score: float
    lowest_score: float
    median_score: float
    std_deviation: float
    grade_distribution: dict[str, int]
    score_ranges: dict[str, int]
    top_performers: list[StudentRecord]
    at_risk_students: list[StudentRecord]


class ExtractionResponse(BaseModel):
    extraction_id: str
    status: str
    original_filename: str
    file_type: str
    university_detected: Optional[str] = None
    subjects_found: list[str] = []
    subject_selected: Optional[str] = None
    students: list[StudentRecord] = []
    analytics: Optional[AnalyticsSummary] = None
    processing_time_ms: int = 0


class SubjectSelectionRequest(BaseModel):
    extraction_id: str
    subject: str


class FilterRequest(BaseModel):
    filter_type: str
    value: Optional[str] = None


class SortRequest(BaseModel):
    sort_by: str = "total_marks"
    ascending: bool = False
