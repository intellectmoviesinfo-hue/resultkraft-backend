"""
Parser for Sri Dev Suman University (Uttarakhand) result PDFs.
Trigger words: SRI DEV SUMAN, SDSU, UTTARAKHAND
"""

import re
from typing import Optional

from .base import BaseUniversityParser, ParsedStudent, SubjectMarks


class SriDevSumanParser(BaseUniversityParser):
    name = "Sri Dev Suman University"
    trigger_words = ["SRI DEV SUMAN", "SDSU", "SDSUV"]
    max_ext = 75
    max_int = 25
    max_total = 100
    pass_mark = 33

    def extract_student_identity(self, card: str) -> Optional[ParsedStudent]:
        name_match = re.search(
            r'Name\s*:\s*(.+?)\s{2,}Roll\s*No\s*[:.]\s*(\S+)', card
        )
        if not name_match:
            # Try alternate pattern
            name_match = re.search(
                r'Name\s*:\s*(.+?)(?:\n|\r)', card
            )
            roll_match = re.search(r'Roll\s*No\s*[:.]\s*(\S+)', card)
            if not name_match or not roll_match:
                return None
            name = name_match.group(1).strip()
            roll = roll_match.group(1).strip()
        else:
            name = name_match.group(1).strip()
            roll = name_match.group(2).strip()

        father_match = re.search(
            r"Father'?s?\s*Name\s*:\s*(.+?)(?:\s{2,}|(?:\n|\r))", card
        )
        enroll_match = re.search(
            r'Enroll?ment\s*No\s*[:.]\s*(\S+)', card
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
            if not line_stripped:
                continue

            # Subject lines typically contain TH or PR and have numbers
            if not re.search(r'\b(TH|PR|THEORY|PRACTICAL)\b', line_stripped, re.IGNORECASE):
                # Also check if line has subject-like pattern with numbers
                if not re.search(r'[A-Za-z]{3,}.*\d+.*\d+.*\d+', line_stripped):
                    continue

            triplet = self.find_marks_triplet(line_stripped)
            if not triplet:
                continue

            ext, internal, total = triplet
            grade = self.extract_grade(line_stripped)

            # Extract subject name (everything before the first number cluster)
            subject_name_match = re.match(
                r'^(.*?)\s*(?:\d+\s*(?:TH|PR)?)',
                line_stripped,
                re.IGNORECASE,
            )
            if subject_name_match:
                subject_name = subject_name_match.group(1).strip()
            else:
                subject_name = re.split(r'\s{2,}|\t', line_stripped)[0].strip()

            # Clean up subject name
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
