"""
Abstract base class for university-specific PDF parsers.
Each university has a slightly different PDF layout.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParsedStudent:
    roll_no: str
    student_name: str
    father_name: str = ""
    enrollment_no: str = ""
    subjects: dict = field(default_factory=dict)
    # subjects = {"Subject Name": {"ext": 45, "int": 20, "total": 65, "grade": "B+"}}


@dataclass
class SubjectMarks:
    ext_marks: float
    int_marks: float
    total_marks: float
    grade: str = ""
    pass_fail: str = ""


class BaseUniversityParser(ABC):
    """Base class all university parsers inherit from."""

    name: str = "Unknown University"
    trigger_words: list[str] = []
    max_ext: int = 75
    max_int: int = 25
    max_total: int = 100
    pass_mark: int = 33  # Minimum total marks to pass

    def __init__(self, marking_scheme: Optional[str] = None):
        """
        marking_scheme: optional override like "75+25", "80+20", "70+30", "100+0"
        Falls back to class defaults if missing or malformed.
        """
        if marking_scheme and "+" in marking_scheme:
            try:
                e_str, i_str = marking_scheme.split("+", 1)
                ext = int(e_str.strip())
                ints = int(i_str.strip())
                if ext > 0 and (ext + ints) > 0:
                    # Per-instance override; class attrs untouched
                    self.max_ext = ext
                    self.max_int = ints
                    self.max_total = ext + ints
                    # Pass mark = 33% of total, matching SDSU/UGC convention
                    self.pass_mark = max(1, round(self.max_total * 0.33))
            except (ValueError, AttributeError):
                pass

    @classmethod
    def can_parse(cls, text: str) -> bool:
        text_upper = text.upper()
        return any(trigger in text_upper for trigger in cls.trigger_words)

    def parse(self, full_text: str, subject_filter: Optional[str] = None) -> tuple[list[ParsedStudent], list[str]]:
        """
        Parse the full PDF text and return (students, subjects_found).
        If subject_filter is provided, only extract that subject's marks.
        """
        cards = self.split_into_cards(full_text)
        seen_rolls = set()
        students = []
        all_subjects = set()

        for card in cards:
            if not card.strip():
                continue

            student = self.extract_student_identity(card)
            if not student or not student.roll_no:
                continue

            # Deduplication
            if student.roll_no in seen_rolls:
                continue
            seen_rolls.add(student.roll_no)

            subjects = self.extract_subjects(card)
            all_subjects.update(subjects.keys())

            if subject_filter:
                if subject_filter in subjects:
                    student.subjects = {subject_filter: subjects[subject_filter]}
                    students.append(student)
            else:
                student.subjects = subjects
                if subjects:
                    students.append(student)

        return students, sorted(all_subjects)

    def split_into_cards(self, text: str) -> list[str]:
        return text.split("\f")

    @abstractmethod
    def extract_student_identity(self, card: str) -> Optional[ParsedStudent]:
        pass

    @abstractmethod
    def extract_subjects(self, card: str) -> dict[str, SubjectMarks]:
        pass

    def find_marks_triplet(self, line: str) -> Optional[tuple[float, float, float]]:
        """
        Scan right-to-left for a valid (ext, int, total) triplet
        where ext + int = total, with constraints.
        """
        nums = re.findall(r'\b(\d+(?:\.\d+)?)\b', line)
        nums_float = [float(n) for n in nums]

        for k in range(len(nums_float) - 3, -1, -1):
            e, n, t = nums_float[k], nums_float[k + 1], nums_float[k + 2]
            if (abs(e + n - t) < 1
                    and e <= self.max_ext
                    and n <= self.max_int
                    and t <= self.max_total
                    and n >= 1):
                return (e, n, t)
        return None

    def find_absent_marks(self, line: str) -> Optional[tuple[float, float, float]]:
        """
        Handle "absent in external exam" rows where the external mark is the
        literal token ``AB`` instead of a number, e.g.:

            PRACTICAL TH DSC 1 1 AB 20 20 0.00 0.00 F
            GEOMETRICAL FORMS STUDY (2D & 3D) PR GE 4 AB 19 19 0.00 0.00 F

        The student sat only the internal assessment, so external = 0 and the
        obtained total equals the internal mark. The number immediately after
        ``AB`` is the internal mark.

        Returns ``(0.0, internal, internal)`` or ``None``. Only fires when
        ``AB`` appears as a standalone token directly followed by a number, so
        it never matches an "AB" embedded inside a subject name (e.g. "LAB").
        Callers should already have confirmed the line is a subject row.
        """
        m = re.search(r'\bAB\b\s+(\d+(?:\.\d+)?)', line)
        if not m:
            return None
        internal = float(m.group(1))
        if internal <= 0 or internal > self.max_int:
            return None
        return (0.0, internal, internal)

    def extract_grade(self, line: str) -> str:
        match = re.search(r'\b([A-F][+]?)\s*$', line.strip())
        if match:
            return match.group(1)
        return ""

    def determine_pass_fail(self, total: float, ext: float = 0) -> str:
        if total < self.pass_mark:
            return "FAIL"
        return "PASS"

    @staticmethod
    def normalize_subject_name(name: str) -> str:
        """Fix common university typos and normalize subject names."""
        corrections = {
            "BRITISH POERTY": "BRITISH POETRY",
            "BRITSH POETRY": "BRITISH POETRY",
            "MANAGMENT": "MANAGEMENT",
            "ADMINSTRATION": "ADMINISTRATION",
            "GEOGRAPY": "GEOGRAPHY",
            "ECNOMICS": "ECONOMICS",
            "POLITCAL": "POLITICAL",
            "SCIENSE": "SCIENCE",
            "MATHAMATICS": "MATHEMATICS",
            "ENVIROMENT": "ENVIRONMENT",
        }
        cleaned = " ".join(name.strip().split())
        upper = cleaned.upper()
        for typo, fix in corrections.items():
            if typo in upper:
                upper = upper.replace(typo, fix)
        # Title case the result
        return upper.title()
