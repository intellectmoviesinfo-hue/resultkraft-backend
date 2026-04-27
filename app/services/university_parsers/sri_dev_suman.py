"""
Parser for Sri Dev Suman University (Uttarakhand) result PDFs.
Trigger words: SRI DEV SUMAN, SDSU, UTTARAKHAND

Each PDF page is one student's grade card.
Subject lines look like:
  PHYSICAL GEOGRAPHY TH DSC 1 3 30 21 51 6.00 18.00 B
  GEOMETRICAL FORMS STUDY (2D & 3D) PR GE 4 60 22 82 9.00 36.00 A+
  िहदी भाषा: याकरण (खड अ ) TH AEC 2 32 20 52 6.00 12.00 B

Pattern:  <subject name>  TH|PR  DSC|GE|SEC|AEC|VAC  [credit]  ext  int  total  gp  gv  letter
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

    # A subject row always contains "TH" or "PR" followed by a course-type code.
    # Anything before that boundary is the subject name.
    _SUBJECT_LINE_RE = re.compile(
        r'^(?P<name>.+?)\s+(?P<paper>TH|PR)\s+(?P<course>DSC|GE|SEC|AEC|VAC)\b',
    )

    # Header rows we should never treat as subjects.
    _HEADER_PHRASES = (
        "max marks",
        "course credits",
        "external internal",
        "subject course",
        "type of paper",
        "grade letter",
    )

    def extract_student_identity(self, card: str) -> Optional[ParsedStudent]:
        # Name and Roll No live on the same line:  "Name : AAFREEN Roll No : 4251260010001"
        m = re.search(
            r'Name\s*:\s*(?P<name>.+?)\s+Roll\s*No\s*[:.]\s*(?P<roll>\S+)',
            card,
        )
        if not m:
            return None
        name = m.group("name").strip()
        roll = m.group("roll").strip()
        if not name or not roll:
            return None

        father = ""
        enrollment = ""

        # Father's Name and Enrollment No are on the same line too.
        m2 = re.search(
            r"Father'?s?\s*Name\s*:\s*(?P<f>.+?)\s+Enroll?ment\s*No\s*[:.]\s*(?P<e>\S+)",
            card,
        )
        if m2:
            father = m2.group("f").strip()
            enrollment = m2.group("e").strip()
        else:
            f_m = re.search(r"Father'?s?\s*Name\s*:\s*(.+?)(?:\n|\r)", card)
            e_m = re.search(r"Enroll?ment\s*No\s*[:.]\s*(\S+)", card)
            if f_m:
                father = f_m.group(1).strip()
            if e_m:
                enrollment = e_m.group(1).strip()

        return ParsedStudent(
            roll_no=roll,
            student_name=name,
            father_name=father,
            enrollment_no=enrollment,
        )

    def extract_subjects(self, card: str) -> dict[str, SubjectMarks]:
        subjects: dict[str, SubjectMarks] = {}

        for raw_line in card.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            line_lower = line.lower()
            if any(p in line_lower for p in self._HEADER_PHRASES):
                continue

            m = self._SUBJECT_LINE_RE.match(line)
            if not m:
                continue

            subject_name = self._clean_subject_name(m.group("name"))
            if not subject_name:
                continue

            triplet = self.find_marks_triplet(line)
            if not triplet:
                # Likely an absent student row (AB 20 20 …) or a page-header artifact.
                continue
            ext, internal, total = triplet
            grade = self.extract_grade(line) or self._calculate_grade(total)

            # SDSU rule: a printed "F" grade overrides any maths;
            # otherwise require both total ≥ pass_mark and ext ≥ 25/75 (theory qualifier).
            if grade and grade.upper().startswith("F"):
                pass_fail = "FAIL"
            elif total < self.pass_mark or ext < 25:
                pass_fail = "FAIL"
            else:
                pass_fail = "PASS"

            subjects[subject_name] = SubjectMarks(
                ext_marks=ext,
                int_marks=internal,
                total_marks=total,
                grade=grade,
                pass_fail=pass_fail,
            )

        return subjects

    def _clean_subject_name(self, raw: str) -> str:
        s = " ".join(raw.split())
        # Drop trailing punctuation like ":" or stray brackets
        s = s.strip(" :;,-")
        if len(s) < 3:
            return ""
        # Reject lines that decoded mostly to non-letters (rare PDF artifacts)
        if not re.search(r"[A-Za-zऀ-ॿ]{3,}", s):
            return ""
        return self.normalize_subject_name(s)

    def _calculate_grade(self, total: float) -> str:
        if total >= 90:
            return "O"
        if total >= 80:
            return "A+"
        if total >= 70:
            return "A"
        if total >= 60:
            return "B+"
        if total >= 50:
            return "B"
        if total >= 40:
            return "C"
        if total >= 33:
            return "D"
        return "F"
