"""
AI command router.
50+ pre-built Python commands run instantly at zero cost.
Gemini is ONLY called when no pre-built pattern matches.
"""
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.schemas.extraction import StudentRecord
from app.services.analytics.engine import (
    apply_filter, apply_sort, calculate_analytics
)

router = APIRouter()


class CommandRequest(BaseModel):
    extraction_id: str
    command: str


class CommandResponse(BaseModel):
    source: str  # "python" or "gemini"
    result_type: str  # "table", "stat", "text"
    students: list[StudentRecord] = []
    text: str = ""
    stat_label: str = ""
    stat_value: str = ""


# Regex pattern -> (filter_type, value_group_or_none)
COMMAND_PATTERNS: list[tuple[str, str, str]] = [
    # Filters
    (r'\bfail|not pass|flunk', "filter", "fail"),
    (r'\bpass(?!ed\s+ext)', "filter", "pass"),
    (r'grade\s*a\b', "filter", "grade_a"),
    (r'grade\s*b\s*\+', "filter", "grade_b_plus"),
    (r'grade\s*b\b', "filter", "grade_b"),
    (r'grade\s*c\b', "filter", "grade_c"),
    (r'above\s+average|better\s+than\s+average', "filter", "above_average"),
    (r'below\s+average|worse\s+than\s+average', "filter", "below_average"),
    (r'at.risk|remedial|struggling|need\s+help', "filter", "at_risk"),
    (r'passed\s+ext.*failed|external.*fail', "filter", "passed_ext_failed"),
    (r'high\s+internal|internal\s+above\s+20', "filter", "high_internal"),
    (r'high\s+external|external\s+above\s+60', "filter", "high_external"),
    # Sorts
    (r'sort\s+by\s+name|name.*sort|alphabetical', "sort", "name"),
    (r'sort\s+by\s+roll|roll.*sort', "sort", "roll_no"),
    (r'sort\s+by\s+father|father.*sort', "sort", "father_name"),
    (r'sort\s+by\s+external|external.*sort', "sort", "external"),
    (r'sort\s+by\s+internal|internal.*sort', "sort", "internal"),
    (r'sort\s+by\s+grade|grade.*sort', "sort", "grade"),
    (r'sort\s+by\s+rank|rank.*sort', "sort", "rank"),
    (r'rank\s+list|ranked|high\s+to\s+low|highest\s+first', "sort", "total_desc"),
    (r'low\s+to\s+high|lowest\s+first', "sort", "total_asc"),
]

STAT_PATTERNS: list[tuple[str, str]] = [
    (r'pass\s+percent|pass\s+rate|how\s+many\s+passed', "pass_percentage"),
    (r'average|mean\s+score|class\s+average', "class_average"),
    (r'highest|topper|maximum|top\s+score', "highest_score"),
    (r'lowest|minimum|lowest\s+score', "lowest_score"),
    (r'median', "median_score"),
    (r'standard\s+deviation|std\s+dev|spread', "std_deviation"),
    (r'total\s+student|how\s+many\s+student|count', "total_students"),
]


@router.post("/ai-command", response_model=CommandResponse)
async def run_command(req: CommandRequest):
    from app.routers.extraction import _extraction_cache
    result = _extraction_cache.get(req.extraction_id)
    if not result:
        raise HTTPException(404, "Extraction not found")

    cmd = req.command.lower().strip()
    students = result.students

    # Check for top N / bottom N
    top_match = re.search(r'top\s+(\d+)', cmd)
    if top_match:
        n = int(top_match.group(1))
        filtered = apply_filter(students, f"top_{n}")
        return CommandResponse(source="python", result_type="table", students=filtered)

    bottom_match = re.search(r'bottom\s+(\d+)|weakest\s+(\d+)', cmd)
    if bottom_match:
        n = int(bottom_match.group(1) or bottom_match.group(2))
        filtered = apply_filter(students, f"bottom_{n}")
        return CommandResponse(source="python", result_type="table", students=filtered)

    # Search by name
    name_match = re.search(r'(?:search|find|show)\s+(?:student\s+)?(?:named?\s+|by\s+name\s+)?(.+)', cmd)
    roll_match = re.search(r'(?:roll|reg)\s*(?:no|number|num)?\s*[:.#]?\s*(\S+)', cmd)

    if roll_match and any(c.isdigit() for c in roll_match.group(1)):
        filtered = apply_filter(students, "search_roll", roll_match.group(1))
        return CommandResponse(source="python", result_type="table", students=filtered)

    # Marks range
    range_match = re.search(r'between\s+(\d+)\s+and\s+(\d+)', cmd)
    if range_match:
        low, high = range_match.group(1), range_match.group(2)
        filtered = apply_filter(students, "marks_range", f"{low},{high}")
        return CommandResponse(source="python", result_type="table", students=filtered)

    above_match = re.search(r'above\s+(\d+)|scored\s+more\s+than\s+(\d+)', cmd)
    if above_match:
        threshold = float(above_match.group(1) or above_match.group(2))
        filtered = [s for s in students if s.total_marks >= threshold]
        return CommandResponse(source="python", result_type="table", students=filtered)

    below_match = re.search(r'below\s+(\d+)|scored\s+less\s+than\s+(\d+)', cmd)
    if below_match:
        threshold = float(below_match.group(1) or below_match.group(2))
        filtered = [s for s in students if s.total_marks < threshold]
        return CommandResponse(source="python", result_type="table", students=filtered)

    # Check stat patterns first
    for pattern, stat_key in STAT_PATTERNS:
        if re.search(pattern, cmd):
            analytics = result.analytics or calculate_analytics(students)
            value = getattr(analytics, stat_key, None)
            if value is not None:
                return CommandResponse(
                    source="python",
                    result_type="stat",
                    stat_label=stat_key.replace("_", " ").title(),
                    stat_value=str(value),
                )

    # Check filter/sort patterns
    for pattern, action, value in COMMAND_PATTERNS:
        if re.search(pattern, cmd):
            if action == "filter":
                filtered = apply_filter(students, value)
                return CommandResponse(source="python", result_type="table", students=filtered)
            elif action == "sort":
                sorted_s = apply_sort(students, value)
                return CommandResponse(source="python", result_type="table", students=sorted_s)

    # Show all fallback
    if any(kw in cmd for kw in ["all student", "show all", "list all", "everyone"]):
        return CommandResponse(source="python", result_type="table", students=students)

    # Gemini fallback for truly unrecognized commands
    return await _gemini_fallback(req.command, students, result.analytics)


async def _gemini_fallback(command: str, students: list[StudentRecord], analytics) -> CommandResponse:
    from app.config import get_settings
    settings = get_settings()

    if not settings.gemini_api_key:
        return CommandResponse(
            source="python",
            result_type="text",
            text=(
                "I couldn't understand that command. "
                "Try: 'show failed students', 'sort by name', 'top 10 students', "
                "'pass percentage', 'students below 40', etc."
            ),
        )

    try:
        import httpx
        prompt = f"""You are analyzing student exam results. The command is: "{command}"

Available student data fields: roll_no, student_name, father_name, ext_marks, int_marks, total_marks, grade, pass_fail.
Analytics: pass%, average, highest, lowest score.

Respond with ONE of:
1. FILTER:<filter_type> where filter_type is one of: pass, fail, grade_a, grade_b_plus, grade_b, grade_c, above_average, below_average, at_risk
2. SORT:<sort_type> where sort_type is one of: total_desc, total_asc, name, roll_no, grade
3. STAT:<stat_key> where stat_key is one of: pass_percentage, class_average, highest_score, lowest_score
4. TEXT:<helpful response>

Respond with just the code, nothing else."""

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={settings.gemini_api_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        if text.startswith("FILTER:"):
            filter_type = text[7:].strip()
            from app.services.analytics.engine import apply_filter
            filtered = apply_filter(students, filter_type)
            return CommandResponse(source="gemini", result_type="table", students=filtered)
        elif text.startswith("SORT:"):
            sort_type = text[5:].strip()
            from app.services.analytics.engine import apply_sort
            sorted_s = apply_sort(students, sort_type)
            return CommandResponse(source="gemini", result_type="table", students=sorted_s)
        elif text.startswith("STAT:"):
            stat_key = text[5:].strip()
            value = getattr(analytics, stat_key, None) if analytics else None
            return CommandResponse(
                source="gemini",
                result_type="stat",
                stat_label=stat_key.replace("_", " ").title(),
                stat_value=str(value or "N/A"),
            )
        else:
            return CommandResponse(source="gemini", result_type="text", text=text[5:] if text.startswith("TEXT:") else text)

    except Exception:
        return CommandResponse(
            source="python",
            result_type="text",
            text="Command not recognized. Try: 'show failed', 'sort by name', 'top 10', 'pass percentage'.",
        )
