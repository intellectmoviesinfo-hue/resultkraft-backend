"""
PDF report generator for Indian university exam results.

Produces three standalone reports plus a combined ZIP:
  1. Summary PDF   - single page with result overview, grade distribution, score ranges
  2. Roll-wise PDF - multi-page student table sorted by roll number
  3. Ranked PDF    - multi-page student table sorted by total marks descending
  4. ZIP bundle    - all three PDFs plus the Excel report
"""

import io
import zipfile
from functools import partial
from typing import Callable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable

from app.schemas.extraction import StudentRecord, AnalyticsSummary

# ---------------------------------------------------------------------------
# Color palette (matching the Excel report's visual identity)
# ---------------------------------------------------------------------------
INDIGO = colors.HexColor("#6366F1")
INDIGO_DARK = colors.HexColor("#4338CA")
INDIGO_LIGHT = colors.HexColor("#E0E7FF")
EMERALD = colors.HexColor("#10B981")
EMERALD_LIGHT = colors.HexColor("#D1FAE5")
ROSE = colors.HexColor("#F43F5E")
ROSE_LIGHT = colors.HexColor("#FFE4E6")
AMBER = colors.HexColor("#F59E0B")
GOLD_BG = colors.HexColor("#FEF3C7")
SILVER_BG = colors.HexColor("#F3F4F6")
BRONZE_BG = colors.HexColor("#FED7AA")
GRAY_50 = colors.HexColor("#F9FAFB")
GRAY_100 = colors.HexColor("#F3F4F6")
GRAY_700 = colors.HexColor("#374151")
GRAY_900 = colors.HexColor("#111827")
WHITE = colors.white

# ---------------------------------------------------------------------------
# Reusable paragraph styles
# ---------------------------------------------------------------------------
_BASE_STYLES = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    "RKTitle",
    parent=_BASE_STYLES["Title"],
    fontName="Helvetica-Bold",
    fontSize=18,
    textColor=INDIGO_DARK,
    alignment=TA_CENTER,
    spaceAfter=4,
)

STYLE_SUBTITLE = ParagraphStyle(
    "RKSubtitle",
    parent=_BASE_STYLES["Normal"],
    fontName="Helvetica",
    fontSize=11,
    textColor=GRAY_700,
    alignment=TA_CENTER,
    spaceAfter=2,
)

STYLE_SECTION = ParagraphStyle(
    "RKSection",
    parent=_BASE_STYLES["Heading2"],
    fontName="Helvetica-Bold",
    fontSize=13,
    textColor=INDIGO_DARK,
    spaceBefore=14,
    spaceAfter=6,
)

STYLE_BODY = ParagraphStyle(
    "RKBody",
    parent=_BASE_STYLES["Normal"],
    fontName="Helvetica",
    fontSize=9,
    textColor=GRAY_900,
)

STYLE_CELL = ParagraphStyle(
    "RKCell",
    parent=_BASE_STYLES["Normal"],
    fontName="Helvetica",
    fontSize=8,
    textColor=GRAY_900,
    leading=10,
)

STYLE_CELL_CENTER = ParagraphStyle(
    "RKCellCenter",
    parent=STYLE_CELL,
    alignment=TA_CENTER,
)

STYLE_HEADER_CELL = ParagraphStyle(
    "RKHeaderCell",
    parent=_BASE_STYLES["Normal"],
    fontName="Helvetica-Bold",
    fontSize=8,
    textColor=WHITE,
    alignment=TA_CENTER,
    leading=10,
)

STYLE_FOOTER = ParagraphStyle(
    "RKFooter",
    parent=_BASE_STYLES["Normal"],
    fontName="Helvetica",
    fontSize=7,
    textColor=GRAY_700,
    alignment=TA_CENTER,
)

# ---------------------------------------------------------------------------
# Page number callback
# ---------------------------------------------------------------------------

def _page_footer(canvas, doc, title: str = "ResultKraft Report"):
    """Draw footer with page number on every page."""
    canvas.saveState()
    page_w, page_h = doc.pagesize
    footer_y = 15 * mm
    # Left: branding
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAY_700)
    canvas.drawString(doc.leftMargin, footer_y, "ResultKraft - Exam Result Analysis")
    # Right: page number
    canvas.drawRightString(
        page_w - doc.rightMargin, footer_y, f"Page {doc.page}"
    )
    # Thin line above footer
    canvas.setStrokeColor(colors.HexColor("#D1D5DB"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, footer_y + 8, page_w - doc.rightMargin, footer_y + 8)
    canvas.restoreState()


def _make_footer_cb(title: str = "ResultKraft Report") -> Callable:
    return partial(_page_footer, title=title)


# ---------------------------------------------------------------------------
# Header flowables shared across reports
# ---------------------------------------------------------------------------

def _build_header_flowables(
    university_name: str,
    subject_name: str,
    report_type: str,
) -> list:
    """Return a list of Platypus flowables for the report header."""
    elements: list = []
    elements.append(Paragraph("ResultKraft", STYLE_TITLE))

    parts = []
    if university_name:
        parts.append(university_name)
    if subject_name:
        parts.append(subject_name)
    if parts:
        elements.append(Paragraph(" | ".join(parts), STYLE_SUBTITLE))

    elements.append(
        Paragraph(report_type, ParagraphStyle(
            "ReportType",
            parent=STYLE_SUBTITLE,
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=INDIGO,
            spaceAfter=4,
        ))
    )
    elements.append(
        HRFlowable(
            width="100%", thickness=1, color=INDIGO, spaceAfter=10, spaceBefore=2,
        )
    )
    return elements


# ---------------------------------------------------------------------------
# Common table style builder
# ---------------------------------------------------------------------------

def _base_table_style() -> list:
    """Return a list of TableStyle commands common to all data tables."""
    return [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TOPPADDING", (0, 1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
        # Alternating row shading
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GRAY_50]),
    ]


# ===================================================================
# 1. Summary PDF
# ===================================================================

def generate_summary_pdf(
    students: list[StudentRecord],
    analytics: AnalyticsSummary,
    university_name: str = "",
    subject_name: str = "",
) -> bytes:
    """Generate a single-page summary PDF with result overview."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title="ResultKraft Summary Report",
    )

    elements: list = []
    footer_cb = _make_footer_cb("Summary Report")

    # -- Header -------------------------------------------------------
    elements.extend(
        _build_header_flowables(university_name, subject_name, "Summary Report")
    )

    # -- Result Summary Table -----------------------------------------
    elements.append(Paragraph("Result Summary", STYLE_SECTION))

    summary_data = [
        ["Metric", "Value"],
        ["Total Students Appeared", str(analytics.total_students)],
        ["Passed", str(analytics.pass_count)],
        ["Failed", str(analytics.fail_count)],
        ["Pass Rate", f"{analytics.pass_percentage:.1f}%"],
        ["Class Average", f"{analytics.class_average:.2f}"],
        ["Highest Score", f"{analytics.highest_score:.1f}"],
        ["Lowest Score", f"{analytics.lowest_score:.1f}"],
        ["Median Score", f"{analytics.median_score:.1f}"],
        ["Standard Deviation", f"{analytics.std_deviation:.2f}"],
    ]

    summary_table = Table(summary_data, colWidths=[200, 160])
    summary_style = TableStyle(
        _base_table_style() + [
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ]
    )
    summary_table.setStyle(summary_style)
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # -- Grade Distribution Table -------------------------------------
    elements.append(Paragraph("Grade Distribution", STYLE_SECTION))

    total = analytics.total_students or 1
    grade_data = [["Grade", "Count", "Percentage"]]
    for grade in sorted(analytics.grade_distribution.keys()):
        count = analytics.grade_distribution[grade]
        pct = round(count / total * 100, 1)
        grade_data.append([grade, str(count), f"{pct}%"])

    grade_table = Table(grade_data, colWidths=[120, 100, 140])
    grade_style = TableStyle(
        _base_table_style() + [
            ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ]
    )
    grade_table.setStyle(grade_style)
    elements.append(grade_table)
    elements.append(Spacer(1, 14))

    # -- Score Range Breakdown ----------------------------------------
    elements.append(Paragraph("Score Range Breakdown", STYLE_SECTION))

    range_data = [["Range", "Count"]]
    for rng, count in analytics.score_ranges.items():
        range_data.append([rng, str(count)])

    range_table = Table(range_data, colWidths=[180, 180])
    range_style = TableStyle(
        _base_table_style() + [
            ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ]
    )
    range_table.setStyle(range_style)
    elements.append(range_table)

    # -- Build --------------------------------------------------------
    doc.build(elements, onFirstPage=footer_cb, onLaterPages=footer_cb)
    return buffer.getvalue()


# ===================================================================
# 2. Roll-wise PDF
# ===================================================================

def generate_rollwise_pdf(
    students: list[StudentRecord],
    analytics: AnalyticsSummary,
    university_name: str = "",
    subject_name: str = "",
) -> bytes:
    """Generate a multi-page PDF with students sorted by roll number."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        title="ResultKraft Roll-wise Report",
    )

    elements: list = []
    footer_cb = _make_footer_cb("Roll-wise Report")

    # -- Header -------------------------------------------------------
    elements.extend(
        _build_header_flowables(university_name, subject_name, "Roll-wise Result Report")
    )

    # -- Table --------------------------------------------------------
    sorted_students = sorted(students, key=lambda s: s.roll_no)

    col_widths = [30, 60, 72, 100, 100, 42, 38, 48, 40, 44, 36]
    # S.No, Roll No, Enrollment No, Name, Father's Name,
    # Ext(75), Int(25), Total(100), Grade, Status, Rank

    header_labels = [
        "S.No", "Roll No", "Enrollment No", "Name", "Father's Name",
        "Ext (75)", "Int (25)", "Total (100)", "Grade", "Status", "Rank",
    ]

    # Build header row using Paragraphs for word-wrap
    header_row = [Paragraph(h, STYLE_HEADER_CELL) for h in header_labels]
    table_data = [header_row]

    # Track rows that need PASS/FAIL coloring (1-based, row 0 is header)
    pass_rows = []
    fail_rows = []

    for idx, student in enumerate(sorted_students, start=1):
        row_num = idx  # 1-based data row index in table_data
        status = student.pass_fail or ""
        rank_str = str(student.rank_in_class) if student.rank_in_class else "-"

        row = [
            Paragraph(str(idx), STYLE_CELL_CENTER),
            Paragraph(str(student.roll_no), STYLE_CELL_CENTER),
            Paragraph(str(student.enrollment_no or "-"), STYLE_CELL_CENTER),
            Paragraph(str(student.student_name), STYLE_CELL),
            Paragraph(str(student.father_name or "-"), STYLE_CELL),
            Paragraph(f"{student.ext_marks:.1f}", STYLE_CELL_CENTER),
            Paragraph(f"{student.int_marks:.1f}", STYLE_CELL_CENTER),
            Paragraph(f"{student.total_marks:.1f}", STYLE_CELL_CENTER),
            Paragraph(str(student.grade), STYLE_CELL_CENTER),
            Paragraph(status, STYLE_CELL_CENTER),
            Paragraph(rank_str, STYLE_CELL_CENTER),
        ]
        table_data.append(row)

        if status.upper() == "PASS":
            pass_rows.append(row_num)
        else:
            fail_rows.append(row_num)

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    style_cmds = _base_table_style()
    # Remove generic alternating rows -- we use PASS/FAIL coloring instead
    style_cmds = [c for c in style_cmds if c[0] != "ROWBACKGROUNDS"]

    # PASS rows: light green status column; FAIL rows: light red status column
    for r in pass_rows:
        # Full-row very light tint
        style_cmds.append(("BACKGROUND", (0, r), (-1, r), WHITE))
        # Status cell green
        style_cmds.append(("BACKGROUND", (9, r), (9, r), EMERALD_LIGHT))
        style_cmds.append(("TEXTCOLOR", (9, r), (9, r), EMERALD))

    for r in fail_rows:
        style_cmds.append(("BACKGROUND", (0, r), (-1, r), WHITE))
        # Status cell red
        style_cmds.append(("BACKGROUND", (9, r), (9, r), ROSE_LIGHT))
        style_cmds.append(("TEXTCOLOR", (9, r), (9, r), ROSE))

    # Alternating row tint for readability (on top, but behind status override)
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            # Even rows get a very light gray, but only non-status columns
            style_cmds.append(("BACKGROUND", (0, i), (8, i), GRAY_50))
            style_cmds.append(("BACKGROUND", (10, i), (10, i), GRAY_50))

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    # -- Build --------------------------------------------------------
    doc.build(elements, onFirstPage=footer_cb, onLaterPages=footer_cb)
    return buffer.getvalue()


# ===================================================================
# 3. Ranked PDF
# ===================================================================

def generate_ranked_pdf(
    students: list[StudentRecord],
    analytics: AnalyticsSummary,
    university_name: str = "",
    subject_name: str = "",
) -> bytes:
    """Generate a multi-page PDF with students sorted by total marks descending."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=15 * mm,
        bottomMargin=20 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        title="ResultKraft Ranked Report",
    )

    elements: list = []
    footer_cb = _make_footer_cb("Ranked Report")

    # -- Header -------------------------------------------------------
    elements.extend(
        _build_header_flowables(university_name, subject_name, "Ranked Result Report")
    )

    # -- Table --------------------------------------------------------
    ranked_students = sorted(students, key=lambda s: s.total_marks, reverse=True)

    col_widths = [34, 60, 72, 100, 100, 42, 38, 48, 40, 44, 52]
    # Rank, Roll No, Enrollment No, Name, Father's Name,
    # Ext(75), Int(25), Total(100), Grade, Status, Percentile

    header_labels = [
        "Rank", "Roll No", "Enrollment No", "Name", "Father's Name",
        "Ext (75)", "Int (25)", "Total (100)", "Grade", "Status", "Percentile",
    ]

    header_row = [Paragraph(h, STYLE_HEADER_CELL) for h in header_labels]
    table_data = [header_row]

    gold_rows = []
    silver_rows = []
    bronze_rows = []
    pass_rows = []
    fail_rows = []

    for idx, student in enumerate(ranked_students, start=1):
        row_num = idx  # 1-based in table_data
        rank = idx
        status = student.pass_fail or ""
        percentile_str = f"{student.percentile:.1f}" if student.percentile is not None else "-"

        row = [
            Paragraph(str(rank), STYLE_CELL_CENTER),
            Paragraph(str(student.roll_no), STYLE_CELL_CENTER),
            Paragraph(str(student.enrollment_no or "-"), STYLE_CELL_CENTER),
            Paragraph(str(student.student_name), STYLE_CELL),
            Paragraph(str(student.father_name or "-"), STYLE_CELL),
            Paragraph(f"{student.ext_marks:.1f}", STYLE_CELL_CENTER),
            Paragraph(f"{student.int_marks:.1f}", STYLE_CELL_CENTER),
            Paragraph(f"{student.total_marks:.1f}", STYLE_CELL_CENTER),
            Paragraph(str(student.grade), STYLE_CELL_CENTER),
            Paragraph(status, STYLE_CELL_CENTER),
            Paragraph(percentile_str, STYLE_CELL_CENTER),
        ]
        table_data.append(row)

        # Categorize row
        if rank == 1:
            gold_rows.append(row_num)
        elif rank == 2:
            silver_rows.append(row_num)
        elif rank == 3:
            bronze_rows.append(row_num)
        elif status.upper() == "PASS":
            pass_rows.append(row_num)
        else:
            fail_rows.append(row_num)

        # FAIL rows that happen to be rank 1-3 are still medal-highlighted
        if rank > 3 and status.upper() != "PASS":
            # already in fail_rows
            pass

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    style_cmds = _base_table_style()
    style_cmds = [c for c in style_cmds if c[0] != "ROWBACKGROUNDS"]

    # Medal highlighting for top 3
    for r in gold_rows:
        style_cmds.append(("BACKGROUND", (0, r), (-1, r), GOLD_BG))
        style_cmds.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))

    for r in silver_rows:
        style_cmds.append(("BACKGROUND", (0, r), (-1, r), SILVER_BG))
        style_cmds.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))

    for r in bronze_rows:
        style_cmds.append(("BACKGROUND", (0, r), (-1, r), BRONZE_BG))
        style_cmds.append(("FONTNAME", (0, r), (-1, r), "Helvetica-Bold"))

    # PASS/FAIL coloring for status column (rows outside top 3)
    for r in pass_rows:
        style_cmds.append(("BACKGROUND", (9, r), (9, r), EMERALD_LIGHT))
        style_cmds.append(("TEXTCOLOR", (9, r), (9, r), EMERALD))

    for r in fail_rows:
        style_cmds.append(("BACKGROUND", (9, r), (9, r), ROSE_LIGHT))
        style_cmds.append(("TEXTCOLOR", (9, r), (9, r), ROSE))

    # Alternating tint for non-medal rows
    for i in range(4, len(table_data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (8, i), GRAY_50))
            style_cmds.append(("BACKGROUND", (10, i), (10, i), GRAY_50))

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)

    # -- Build --------------------------------------------------------
    doc.build(elements, onFirstPage=footer_cb, onLaterPages=footer_cb)
    return buffer.getvalue()


# ===================================================================
# 4. ZIP bundle (all reports)
# ===================================================================

def generate_all_reports_zip(
    students: list[StudentRecord],
    analytics: AnalyticsSummary,
    university_name: str = "",
    subject_name: str = "",
) -> bytes:
    """Create a ZIP archive containing all four report files."""
    from app.services.reports.excel_report import generate_excel_report

    summary_pdf = generate_summary_pdf(students, analytics, university_name, subject_name)
    rollwise_pdf = generate_rollwise_pdf(students, analytics, university_name, subject_name)
    ranked_pdf = generate_ranked_pdf(students, analytics, university_name, subject_name)
    excel_bytes = generate_excel_report(students, analytics, university_name, subject_name)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("ResultKraft_Summary.pdf", summary_pdf)
        zf.writestr("ResultKraft_Rollwise.pdf", rollwise_pdf)
        zf.writestr("ResultKraft_Ranked.pdf", ranked_pdf)
        zf.writestr("ResultKraft_Report.xlsx", excel_bytes)

    return zip_buffer.getvalue()
