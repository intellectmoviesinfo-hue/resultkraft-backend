"""Parser for Kumaun University result PDFs."""

import re
from typing import Optional
from .base import BaseUniversityParser, ParsedStudent, SubjectMarks


class KumaunParser(BaseUniversityParser):
    name = "Kumaun University"
    trigger_words = ["KUMAUN UNIVERSITY", "NAINITAL", "KUMAUN"]
    max_ext = 75
    max_int = 25
    max_total = 100
    pass_mark = 33

    def extract_student_identity(self, card: str) -> Optional[ParsedStudent]:
        name_match = re.search(
            r'(?:Student\s*)?Name\s*[:.]\s*(.+?)(?:\s{2,}|\n|\r)',
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
        for line in card.split("\n"):
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 10:
                continue
            triplet = self.find_marks_triplet(line_stripped)
            if not triplet:
                continue
            ext, internal, total = triplet
            grade = self.extract_grade(line_stripped)
            parts = re.split(r'\s{2,}|\t', line_stripped)
            subject_name = re.sub(r'\s+', ' ', parts[0]).strip()
            if len(subject_name) < 2:
                continue
            pf = self.determine_pass_fail(total, ext)
            if not grade:
                grade = "F" if pf == "FAIL" else ("A" if total >= 70 else "B+" if total >= 60 else "B" if total >= 50 else "C" if total >= 40 else "D" if total >= 33 else "F")
            subjects[subject_name] = SubjectMarks(ext, internal, total, grade, pf)
        return subjects
