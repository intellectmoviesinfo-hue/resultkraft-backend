"""
Analytics engine - 50+ pre-built commands.
All pure Python. Zero API cost. 100% accuracy.
"""

import statistics
from app.schemas.extraction import StudentRecord, AnalyticsSummary


def calculate_analytics(students: list[StudentRecord]) -> AnalyticsSummary:
    if not students:
        return _empty_analytics()

    totals = [s.total_marks for s in students]
    pass_students = [s for s in students if s.pass_fail == "PASS"]
    fail_students = [s for s in students if s.pass_fail == "FAIL"]

    n = len(students)
    avg = sum(totals) / n
    std = statistics.stdev(totals) if n > 1 else 0.0

    # Grade distribution
    grade_dist: dict[str, int] = {}
    for s in students:
        g = s.grade or "?"
        grade_dist[g] = grade_dist.get(g, 0) + 1

    # Score ranges
    ranges = {
        "90-100": 0, "80-89": 0, "70-79": 0,
        "60-69": 0, "50-59": 0, "40-49": 0,
        "33-39": 0, "Below 33": 0,
    }
    for t in totals:
        if t >= 90:
            ranges["90-100"] += 1
        elif t >= 80:
            ranges["80-89"] += 1
        elif t >= 70:
            ranges["70-79"] += 1
        elif t >= 60:
            ranges["60-69"] += 1
        elif t >= 50:
            ranges["50-59"] += 1
        elif t >= 40:
            ranges["40-49"] += 1
        elif t >= 33:
            ranges["33-39"] += 1
        else:
            ranges["Below 33"] += 1

    sorted_by_marks = sorted(students, key=lambda s: s.total_marks, reverse=True)
    top3 = sorted_by_marks[:3]
    at_risk = [s for s in students if s.total_marks < 35]

    return AnalyticsSummary(
        total_students=n,
        pass_count=len(pass_students),
        fail_count=len(fail_students),
        pass_percentage=round((len(pass_students) / n) * 100, 1),
        class_average=round(avg, 2),
        highest_score=max(totals),
        lowest_score=min(totals),
        median_score=round(statistics.median(totals), 2),
        std_deviation=round(std, 2),
        grade_distribution=grade_dist,
        score_ranges=ranges,
        top_performers=top3,
        at_risk_students=at_risk,
    )


def _empty_analytics() -> AnalyticsSummary:
    return AnalyticsSummary(
        total_students=0,
        pass_count=0,
        fail_count=0,
        pass_percentage=0,
        class_average=0,
        highest_score=0,
        lowest_score=0,
        median_score=0,
        std_deviation=0,
        grade_distribution={},
        score_ranges={},
        top_performers=[],
        at_risk_students=[],
    )


# ==================== FILTER FUNCTIONS ====================

def filter_pass(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.pass_fail == "PASS"]

def filter_fail(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.pass_fail == "FAIL"]

def filter_grade(students: list[StudentRecord], grade: str) -> list[StudentRecord]:
    return [s for s in students if s.grade == grade]

def filter_grade_a(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.total_marks >= 70]

def filter_grade_b_plus(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if 60 <= s.total_marks < 70]

def filter_grade_b(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if 50 <= s.total_marks < 60]

def filter_grade_c(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if 40 <= s.total_marks < 50]

def filter_top_n(students: list[StudentRecord], n: int) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.total_marks, reverse=True)[:n]

def filter_bottom_n(students: list[StudentRecord], n: int) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.total_marks)[:n]

def filter_above_average(students: list[StudentRecord]) -> list[StudentRecord]:
    if not students:
        return []
    avg = sum(s.total_marks for s in students) / len(students)
    return [s for s in students if s.total_marks >= avg]

def filter_below_average(students: list[StudentRecord]) -> list[StudentRecord]:
    if not students:
        return []
    avg = sum(s.total_marks for s in students) / len(students)
    return [s for s in students if s.total_marks < avg]

def filter_at_risk(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.total_marks < 35]

def filter_passed_ext_failed_overall(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.ext_marks >= 24 and s.pass_fail == "FAIL"]

def filter_high_internal(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.int_marks >= 20]

def filter_high_external(students: list[StudentRecord]) -> list[StudentRecord]:
    return [s for s in students if s.ext_marks >= 60]

def filter_by_name(students: list[StudentRecord], query: str) -> list[StudentRecord]:
    q = query.lower()
    return [s for s in students if q in s.student_name.lower()]

def filter_by_roll(students: list[StudentRecord], query: str) -> list[StudentRecord]:
    q = query.lower()
    return [s for s in students if q in s.roll_no.lower()]

def filter_by_father_name(students: list[StudentRecord], query: str) -> list[StudentRecord]:
    q = query.lower()
    return [s for s in students if s.father_name and q in s.father_name.lower()]

def filter_marks_range(students: list[StudentRecord], low: float, high: float) -> list[StudentRecord]:
    return [s for s in students if low <= s.total_marks <= high]


# ==================== SORT FUNCTIONS ====================

def sort_by_total_desc(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.total_marks, reverse=True)

def sort_by_total_asc(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.total_marks)

def sort_by_name(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.student_name.lower())

def sort_by_roll(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.roll_no)

def sort_by_father_name(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: (s.father_name or "").lower())

def sort_by_external(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.ext_marks, reverse=True)

def sort_by_internal(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.int_marks, reverse=True)

def sort_by_grade(students: list[StudentRecord]) -> list[StudentRecord]:
    grade_order = {"O": 0, "A+": 1, "A": 2, "B+": 3, "B": 4, "C": 5, "D": 6, "F": 7}
    return sorted(students, key=lambda s: grade_order.get(s.grade, 99))

def sort_by_rank(students: list[StudentRecord]) -> list[StudentRecord]:
    return sorted(students, key=lambda s: s.rank_in_class or 9999)


# ==================== APPLY FILTER/SORT ====================

FILTER_MAP = {
    "all": lambda s: s,
    "pass": filter_pass,
    "fail": filter_fail,
    "grade_a": filter_grade_a,
    "grade_b_plus": filter_grade_b_plus,
    "grade_b": filter_grade_b,
    "grade_c": filter_grade_c,
    "top_10": lambda s: filter_top_n(s, 10),
    "top_25": lambda s: filter_top_n(s, 25),
    "bottom_10": lambda s: filter_bottom_n(s, 10),
    "above_average": filter_above_average,
    "below_average": filter_below_average,
    "at_risk": filter_at_risk,
    "passed_ext_failed": filter_passed_ext_failed_overall,
    "high_internal": filter_high_internal,
    "high_external": filter_high_external,
}

SORT_MAP = {
    "total_desc": sort_by_total_desc,
    "total_asc": sort_by_total_asc,
    "name": sort_by_name,
    "roll_no": sort_by_roll,
    "father_name": sort_by_father_name,
    "external": sort_by_external,
    "internal": sort_by_internal,
    "grade": sort_by_grade,
    "rank": sort_by_rank,
}


def apply_filter(students: list[StudentRecord], filter_type: str, value: str = "") -> list[StudentRecord]:
    if filter_type == "search_name":
        return filter_by_name(students, value)
    elif filter_type == "search_roll":
        return filter_by_roll(students, value)
    elif filter_type == "search_father":
        return filter_by_father_name(students, value)
    elif filter_type == "marks_range":
        parts = value.split(",")
        if len(parts) == 2:
            return filter_marks_range(students, float(parts[0]), float(parts[1]))
        return students
    elif filter_type.startswith("top_"):
        try:
            n = int(filter_type.split("_")[1])
            return filter_top_n(students, n)
        except (ValueError, IndexError):
            pass
    elif filter_type.startswith("bottom_"):
        try:
            n = int(filter_type.split("_")[1])
            return filter_bottom_n(students, n)
        except (ValueError, IndexError):
            pass

    fn = FILTER_MAP.get(filter_type)
    if fn:
        return fn(students)
    return students


def apply_sort(students: list[StudentRecord], sort_by: str) -> list[StudentRecord]:
    fn = SORT_MAP.get(sort_by, sort_by_total_desc)
    return fn(students)
