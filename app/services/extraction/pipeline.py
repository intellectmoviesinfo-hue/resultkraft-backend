"""
Core extraction orchestrator.
Coordinates: file validation -> text extraction -> university detection ->
student parsing -> analytics calculation -> result storage.
"""

import time
import io
from typing import Optional

import pandas as pd
import chardet

from app.schemas.extraction import StudentRecord, AnalyticsSummary, ExtractionResponse
from app.services.extraction.pdf_parser import extract_pdf_text_from_bytes
from app.services.extraction.validators import validate_upload
from app.services.university_parsers.detector import detect_university
from app.services.university_parsers.base import ParsedStudent
from app.services.analytics.engine import calculate_analytics


def process_file(
    filename: str,
    content: bytes,
    subject_filter: Optional[str] = None,
) -> ExtractionResponse:
    start = time.time()

    ext = validate_upload(filename, content)

    if ext == ".pdf":
        students, subjects, university = _process_pdf(content, subject_filter)
    elif ext in (".xlsx", ".xls"):
        students, subjects, university = _process_excel(content, ext, subject_filter)
    elif ext == ".csv":
        students, subjects, university = _process_csv(content, subject_filter)
    elif ext == ".docx":
        students, subjects, university = _process_docx(content, subject_filter)
    elif ext == ".ods":
        students, subjects, university = _process_ods(content, subject_filter)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Convert to StudentRecord and rank
    records = _rank_students(students, subject_filter)

    # Calculate analytics
    analytics = None
    if records:
        analytics = calculate_analytics(records)

    elapsed_ms = int((time.time() - start) * 1000)

    return ExtractionResponse(
        extraction_id="",  # Set by router after DB insert
        status="completed",
        original_filename=filename,
        file_type=ext.lstrip("."),
        university_detected=university,
        subjects_found=subjects,
        subject_selected=subject_filter,
        students=records,
        analytics=analytics,
        processing_time_ms=elapsed_ms,
    )


def _process_pdf(
    content: bytes, subject_filter: Optional[str]
) -> tuple[list[ParsedStudent], list[str], str]:
    text = extract_pdf_text_from_bytes(content)
    parser = detect_university(text)
    students, subjects = parser.parse(text, subject_filter)
    return students, subjects, parser.name


def _process_excel(
    content: bytes, ext: str, subject_filter: Optional[str]
) -> tuple[list[ParsedStudent], list[str], str]:
    engine = "openpyxl" if ext == ".xlsx" else "xlrd"
    df = pd.read_excel(io.BytesIO(content), engine=engine)
    return _process_dataframe(df, subject_filter)


def _process_csv(
    content: bytes, subject_filter: Optional[str]
) -> tuple[list[ParsedStudent], list[str], str]:
    detected = chardet.detect(content)
    encoding = detected.get("encoding", "utf-8") or "utf-8"

    # Try common delimiters
    text = content.decode(encoding, errors="replace")
    for delimiter in [",", "\t", ";", "|"]:
        try:
            df = pd.read_csv(
                io.StringIO(text),
                delimiter=delimiter,
                encoding=encoding,
            )
            if len(df.columns) >= 3:
                return _process_dataframe(df, subject_filter)
        except Exception:
            continue

    raise ValueError("Could not parse CSV file. Please check the format.")


def _process_docx(
    content: bytes, subject_filter: Optional[str]
) -> tuple[list[ParsedStudent], list[str], str]:
    from docx import Document

    doc = Document(io.BytesIO(content))
    all_data = []
    for table in doc.tables:
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        for row in table.rows[1:]:
            row_data = {
                headers[i]: cell.text.strip()
                for i, cell in enumerate(row.cells)
                if i < len(headers)
            }
            all_data.append(row_data)

    if not all_data:
        raise ValueError("No tables found in DOCX file.")

    df = pd.DataFrame(all_data)
    return _process_dataframe(df, subject_filter)


def _process_ods(
    content: bytes, subject_filter: Optional[str]
) -> tuple[list[ParsedStudent], list[str], str]:
    df = pd.read_excel(io.BytesIO(content), engine="odf")
    return _process_dataframe(df, subject_filter)


def _process_dataframe(
    df: pd.DataFrame, subject_filter: Optional[str]
) -> tuple[list[ParsedStudent], list[str], str]:
    """Convert a DataFrame with marks data into ParsedStudent list."""
    # Normalize column names
    col_map = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if any(k in col_lower for k in ["roll", "reg"]):
            col_map["roll_no"] = col
        elif "name" in col_lower and "father" not in col_lower and "parent" not in col_lower:
            col_map["student_name"] = col
        elif any(k in col_lower for k in ["father", "parent"]):
            col_map["father_name"] = col
        elif any(k in col_lower for k in ["enroll", "enrol"]):
            col_map["enrollment_no"] = col
        elif any(k in col_lower for k in ["ext", "external", "theory"]):
            col_map["ext_marks"] = col
        elif any(k in col_lower for k in ["int", "internal", "practical"]):
            col_map["int_marks"] = col
        elif any(k in col_lower for k in ["total", "marks", "score"]):
            col_map["total_marks"] = col
        elif "grade" in col_lower:
            col_map["grade"] = col
        elif "subject" in col_lower:
            col_map["subject"] = col

    if "roll_no" not in col_map or "student_name" not in col_map:
        raise ValueError(
            "Could not find required columns (Roll No, Name). "
            "Please ensure your file has these columns."
        )

    students = []
    subjects_found = set()

    for _, row in df.iterrows():
        roll = str(row.get(col_map.get("roll_no", ""), "")).strip()
        name = str(row.get(col_map.get("student_name", ""), "")).strip()
        if not roll or not name or roll == "nan" or name == "nan":
            continue

        father = str(row.get(col_map.get("father_name", ""), "")).strip()
        enroll = str(row.get(col_map.get("enrollment_no", ""), "")).strip()

        ext = _safe_float(row.get(col_map.get("ext_marks", ""), 0))
        internal = _safe_float(row.get(col_map.get("int_marks", ""), 0))
        total = _safe_float(row.get(col_map.get("total_marks", ""), 0))

        if total == 0 and ext > 0:
            total = ext + internal

        grade = str(row.get(col_map.get("grade", ""), "")).strip()
        subject = str(row.get(col_map.get("subject", ""), "")).strip()

        if subject and subject != "nan":
            subjects_found.add(subject)
            if subject_filter and subject != subject_filter:
                continue

        from app.services.university_parsers.base import SubjectMarks
        student = ParsedStudent(
            roll_no=roll,
            student_name=name,
            father_name=father if father != "nan" else "",
            enrollment_no=enroll if enroll != "nan" else "",
            subjects={
                subject or "Default": SubjectMarks(
                    ext_marks=ext,
                    int_marks=internal,
                    total_marks=total,
                    grade=grade if grade != "nan" else "",
                    pass_fail="PASS" if total >= 33 else "FAIL",
                )
            },
        )
        students.append(student)

    return students, sorted(subjects_found), "Spreadsheet Import"


def _safe_float(val) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _rank_students(
    parsed_students: list[ParsedStudent],
    subject_filter: Optional[str] = None,
) -> list[StudentRecord]:
    """Convert ParsedStudent to StudentRecord with ranking."""
    records = []

    for student in parsed_students:
        for subject_name, marks in student.subjects.items():
            records.append(
                StudentRecord(
                    roll_no=student.roll_no,
                    enrollment_no=student.enrollment_no,
                    student_name=student.student_name,
                    father_name=student.father_name,
                    ext_marks=marks.ext_marks,
                    int_marks=marks.int_marks,
                    total_marks=marks.total_marks,
                    grade=marks.grade,
                    pass_fail=marks.pass_fail,
                    subject_name=subject_name,
                )
            )

    # Sort by total marks descending and assign ranks
    records.sort(key=lambda r: r.total_marks, reverse=True)
    n = len(records)
    for i, record in enumerate(records):
        record.rank_in_class = i + 1
        record.percentile = round(((n - i - 1) / n) * 100, 1) if n > 0 else 0

    return records
