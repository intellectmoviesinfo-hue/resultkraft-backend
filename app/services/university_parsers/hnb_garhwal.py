"""
Parser for HNB Garhwal University result PDFs.
Trigger words: HNB GARHWAL, HEMWATI NANDAN, SRINAGAR GARHWAL
"""

import re
from typing import Optional

from .base import BaseUniversityParser, ParsedStudent, SubjectMarks


class HNBGarhwalParser(BaseUniversityParser):
    name = "HNB Garhwal University"
    trigger_words = ["HNB GARHWAL", "HEMWATI NANDAN", "SRINAGAR GARHWAL", "HNBGU"]
    max_ext = 75
    max_int = 25
    max_total = 100
    pass_mark = 33

    def extract_student_identity(self, card: str) -> Optional[ParsedStudent]:
        name_match = re.search(
            r'(?:Student\s*)?Name\s*[:.]\s*(.+?)(?:\s{2,}|Roll\s*No)',
            card, re.IGNORECASE
        )
        roll_match = re.search(r'Roll\s*No\s*[:.]\s*(\S+)', card, re.IGNORECASE)

        if not name_match or not roll_match:
            return None

        father_match = re.search(
            r"Father'?s?\s*Name\s*[:.]\s*(.+?)(?:\s{2,}|\n|\r)",
            card, re.IGNORECASE
        )
        enroll_match = re.search(
            r'Enroll?ment\s*No\s*[:.]\s*(\S+)', card, re.IGNORECASE
        )

        return ParsedStudent(
            roll_no=roll_match.group(1).strip(),
            student_name=name_match.group(1).strip(),
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

            triplet = self.find_marks_triplet(line_stripped)
            if not triplet:
                continue

            ext, internal, total = triplet
            grade = self.extract_grade(line_stripped)

            # Extract subject name
            parts = re.split(r'\s{2,}|\t', line_stripped)
            subject_name = parts[0].strip() if parts else ""

            subject_name = re.sub(r'\s+', ' ', subject_name).strip()
            if len(subject_name) < 2:
                continue

            subjects[subject_name] = SubjectMarks(
                ext_marks=ext,
                int_marks=internal,
                total_marks=total,
                grade=grade or self._calculate_grade(total),
                pass_fail=self.determine_pass_fail(total, ext),
            )

        return subjects

    def _calculate_grade(self, total: float) -> str:
        if total >= 90:
            return "O"
        elif total >= 80:
            return "A+"
        elif total >= 70:
            return "A"
        elif total >= 60:
            return "B+"
        elif total >= 50:
            return "B"
        elif total >= 40:
            return "C"
        elif total >= 33:
            return "D"
        else:
            return "F"
