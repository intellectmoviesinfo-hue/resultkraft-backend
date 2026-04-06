"""
Generic fallback parser for any unrecognized university PDF.
Uses flexible regex patterns that work across most Indian university formats.
"""

import re
from typing import Optional
from .base import BaseUniversityParser, ParsedStudent, SubjectMarks


class GenericParser(BaseUniversityParser):
    name = "Unknown University"
    trigger_words = []  # Fallback - always available
    max_ext = 100
    max_int = 50
    max_total = 150
    pass_mark = 33

    @classmethod
    def can_parse(cls, text: str) -> bool:
        return True  # Always available as fallback

    def extract_student_identity(self, card: str) -> Optional[ParsedStudent]:
        # Try multiple name patterns
        name_patterns = [
            r'(?:Student\s*)?Name\s*[:.]\s*(.+?)(?:\s{2,}|\n|\r)',
            r'Name\s+of\s+(?:Student|Candidate)\s*[:.]\s*(.+?)(?:\s{2,}|\n|\r)',
            r'Candidate\s*[:.]\s*(.+?)(?:\s{2,}|\n|\r)',
        ]
        name = None
        for pattern in name_patterns:
            m = re.search(pattern, card, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                break

        # Try multiple roll number patterns
        roll_patterns = [
            r'Roll\s*No\s*[:.]\s*(\S+)',
            r'Roll\s*Number\s*[:.]\s*(\S+)',
            r'Reg\s*\.?\s*No\s*[:.]\s*(\S+)',
            r'Registration\s*No\s*[:.]\s*(\S+)',
            r'Seat\s*No\s*[:.]\s*(\S+)',
        ]
        roll = None
        for pattern in roll_patterns:
            m = re.search(pattern, card, re.IGNORECASE)
            if m:
                roll = m.group(1).strip()
                break

        if not name or not roll:
            return None

        father_match = re.search(
            r"(?:Father|Parent)'?s?\s*Name\s*[:.]\s*(.+?)(?:\s{2,}|\n|\r)",
            card, re.IGNORECASE
        )
        enroll_match = re.search(
            r'Enroll?ment\s*No\s*[:.]\s*(\S+)', card, re.IGNORECASE
        )

        return ParsedStudent(
            roll_no=roll,
            student_name=name,
            father_name=father_match.group(1).strip() if father_match else "",
            enrollment_no=enroll_match.group(1).strip() if enroll_match else "",
        )

    def extract_subjects(self, card: str) -> dict[str, SubjectMarks]:
        subjects = {}
        lines = card.split("\n")

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 10:
                continue

            # Try standard triplet extraction
            triplet = self.find_marks_triplet(line_stripped)
            if not triplet:
                # Try with relaxed constraints for different marking schemes
                triplet = self._find_relaxed_triplet(line_stripped)
                if not triplet:
                    continue

            ext, internal, total = triplet
            grade = self.extract_grade(line_stripped)

            # Extract subject name
            parts = re.split(r'\s{2,}|\t', line_stripped)
            subject_name = re.sub(r'\s+', ' ', parts[0]).strip()

            # Remove trailing numbers/codes from subject name
            subject_name = re.sub(r'\s*\d+\s*$', '', subject_name).strip()

            if len(subject_name) < 2:
                continue

            pf = self.determine_pass_fail(total, ext)
            if not grade:
                grade = self._calculate_grade(total)

            subjects[subject_name] = SubjectMarks(ext, internal, total, grade, pf)

        return subjects

    def _find_relaxed_triplet(self, line: str) -> Optional[tuple[float, float, float]]:
        """Try alternative marking schemes (e.g., 100+50=150, 70+30=100)."""
        nums = [float(n) for n in re.findall(r'\b(\d+(?:\.\d+)?)\b', line)]

        # Try various max mark combinations
        for max_e, max_i, max_t in [(100, 50, 150), (70, 30, 100), (80, 20, 100), (60, 40, 100)]:
            for k in range(len(nums) - 3, -1, -1):
                e, n, t = nums[k], nums[k + 1], nums[k + 2]
                if abs(e + n - t) < 1 and e <= max_e and n <= max_i and t <= max_t and n >= 1:
                    return (e, n, t)
        return None

    def _calculate_grade(self, total: float) -> str:
        pct = (total / self.max_total) * 100 if self.max_total > 0 else 0
        if pct >= 90:
            return "O"
        elif pct >= 80:
            return "A+"
        elif pct >= 70:
            return "A"
        elif pct >= 60:
            return "B+"
        elif pct >= 50:
            return "B"
        elif pct >= 40:
            return "C"
        elif pct >= 33:
            return "D"
        else:
            return "F"
