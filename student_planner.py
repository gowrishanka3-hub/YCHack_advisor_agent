"""Structured academic planning from student JSON data."""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

FOCUS_OPTIONS = (
    "general",
    "next_semester",
    "critical_tracking",
    "prerequisites",
    "graduation_path",
    "model_plan",
)


def load_json(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_student_record(student_id: str | None = None) -> dict | None:
    audits = load_json("degree_audit.json")
    if not audits:
        return None
    if student_id:
        for record in audits:
            if record.get("student_id") == student_id:
                return record
    return audits[0]


def get_course_registry() -> dict[str, dict]:
    return {
        c["course_id"]: c
        for c in load_json("course_registry.json")
        if c.get("course_id")
    }


def get_major_requirements(major: str | None = None) -> list[dict]:
    records = load_json("major_requirements.json")
    if major:
        return [r for r in records if r.get("major") == major]
    return records


def _normalize_course_id(course_id: str) -> str:
    return re.sub(r"\s+", " ", course_id.strip().upper())


def _taken_set(completed: list[str], in_progress: list[str]) -> set[str]:
    return {_normalize_course_id(c) for c in completed + in_progress}


def prerequisites_satisfied(
    course_id: str,
    completed: list[str],
    in_progress: list[str],
    courses_db: dict[str, dict],
) -> tuple[bool, list[str]]:
    taken = _taken_set(completed, in_progress)
    info = courses_db.get(course_id, {})
    prereqs = info.get("prerequisites") or []
    if not prereqs:
        return True, []
    missing = [p for p in prereqs if _normalize_course_id(p) not in taken]
    return len(missing) == 0, missing


def _is_catalog_course(course_id: str) -> bool:
    return bool(re.match(r"^[A-Z]{3,4}\s\d{4}", course_id.strip()))


def _offered_in_term(course_id: str, term: str | None, courses_db: dict[str, dict]) -> bool:
    if not term or not _is_catalog_course(course_id):
        return True
    offered = courses_db.get(course_id, {}).get("offered") or []
    if not offered:
        return True
    term_lower = term.lower()
    if "fall" in term_lower:
        return "Fall" in offered
    if "spring" in term_lower:
        return "Spring" in offered
    if "summer" in term_lower:
        return "Summer" in offered
    return True


def collect_remaining_courses(audit: dict) -> list[str]:
    seen: set[str] = set()
    remaining: list[str] = []
    for cat_info in audit.get("categories", {}).values():
        for course_id in cat_info.get("courses_remaining", []):
            norm = _normalize_course_id(course_id)
            if norm not in seen:
                seen.add(norm)
                remaining.append(course_id)
    return remaining


def get_model_semester_plans(requirements: list[dict]) -> list[dict]:
    return [
        req
        for req in requirements
        if req.get("category", "").startswith("Model Semester Plan")
    ]


def find_current_model_semester(
    audit: dict, plans: list[dict]
) -> tuple[dict | None, dict | None]:
    taken = _taken_set(
        audit.get("completed_courses", []),
        audit.get("in_progress", []),
    )
    sorted_plans = sorted(plans, key=lambda p: p.get("category", ""))
    current_idx = 0
    for i, plan in enumerate(sorted_plans):
        plan_courses = {
            _normalize_course_id(c)
            for c in plan.get("courses", [])
            if _is_catalog_course(c)
        }
        if plan_courses & taken:
            current_idx = i
    current = sorted_plans[current_idx] if sorted_plans else None
    next_plan = sorted_plans[current_idx + 1] if current_idx + 1 < len(sorted_plans) else None
    return current, next_plan


def recommend_courses(
    audit: dict,
    courses_db: dict[str, dict],
    term: str | None = None,
    limit: int = 6,
) -> list[dict]:
    completed = audit.get("completed_courses", [])
    in_progress = audit.get("in_progress", [])
    taken = _taken_set(completed, in_progress)
    remaining = collect_remaining_courses(audit)
    ct_remaining = set(
        audit.get("categories", {})
        .get("critical_tracking", {})
        .get("courses_remaining", [])
    )

    candidates: list[dict] = []
    for course_id in remaining:
        norm = _normalize_course_id(course_id)
        if norm in taken or not _is_catalog_course(course_id):
            continue
        if not _offered_in_term(course_id, term, courses_db):
            continue

        met, missing = prerequisites_satisfied(course_id, completed, in_progress, courses_db)
        info = courses_db.get(course_id, {})
        priority = 0
        if course_id in ct_remaining or info.get("critical_tracking"):
            priority += 10
        if met:
            priority += 5
        rec = audit.get("next_semester_recommendation", {}).get("courses", [])
        if course_id in rec:
            priority += 8

        candidates.append(
            {
                "course_id": course_id,
                "title": info.get("title", course_id),
                "credits": info.get("credits", 3),
                "prerequisites_met": met,
                "missing_prerequisites": missing,
                "critical_tracking": info.get("critical_tracking", False),
                "priority": priority,
            }
        )

    candidates.sort(
        key=lambda c: (c["prerequisites_met"], c["priority"], -c["credits"]),
        reverse=True,
    )
    return candidates[:limit]


def format_course_line(course: dict) -> str:
    flags = []
    if course.get("critical_tracking"):
        flags.append("critical tracking")
    if not course.get("prerequisites_met"):
        flags.append(f"needs {', '.join(course['missing_prerequisites'])}")
    flag_str = f" ({'; '.join(flags)})" if flags else ""
    return f"{course['course_id']} — {course['title']} ({course['credits']} cr){flag_str}"


def analyze_student_academics(
    focus: str = "general",
    course_query: str | None = None,
    term: str | None = None,
    student_id: str | None = None,
) -> str:
    if focus not in FOCUS_OPTIONS:
        return f"Invalid focus '{focus}'. Use one of: {', '.join(FOCUS_OPTIONS)}."

    audit = get_student_record(student_id)
    if not audit:
        return "No student degree audit found. Add data to data/degree_audit.json."

    courses_db = get_course_registry()
    requirements = get_major_requirements(audit.get("major"))
    model_plans = get_model_semester_plans(requirements)
    current_plan, next_plan = find_current_model_semester(audit, model_plans)

    completed = audit.get("completed_courses", [])
    in_progress = audit.get("in_progress", [])
    target_term = term or audit.get("next_semester_recommendation", {}).get("term")
    sections: list[str] = []

    sections.append(
        f"STUDENT: {audit.get('name')} ({audit.get('student_id')})\n"
        f"Major: {audit.get('major')}\n"
        f"Year: {audit.get('year')}\n"
        f"GPA: {audit.get('gpa')}\n"
        f"Credits: {audit.get('credits_earned', 0)}/{audit.get('credits_total', 120)}\n"
        f"Expected graduation: {audit.get('expected_graduation')}\n"
        f"Critical tracking: {audit.get('critical_tracking_status')} "
        f"(CT GPA {audit.get('critical_tracking_gpa', 'N/A')})"
    )

    if focus in ("general", "graduation_path", "next_semester", "model_plan"):
        sections.append(
            f"COMPLETED ({len(completed)}): {', '.join(completed) or 'none'}\n"
            f"IN PROGRESS ({len(in_progress)}): {', '.join(in_progress) or 'none'}"
        )

    if focus in ("general", "graduation_path"):
        cat_lines = []
        for cat, info in audit.get("categories", {}).items():
            remaining = info.get("courses_remaining", [])
            cat_lines.append(
                f"  {cat}: {info.get('earned', 0)}/{info.get('required', 0)} credits, "
                f"{len(remaining)} courses left"
                + (
                    f" — {', '.join(remaining[:5])}"
                    + ("..." if len(remaining) > 5 else "")
                    if remaining
                    else ""
                )
            )
            if info.get("notes"):
                cat_lines.append(f"    Note: {info['notes']}")
        sections.append("DEGREE REQUIREMENTS BY CATEGORY:\n" + "\n".join(cat_lines))

    if focus in ("general", "critical_tracking", "next_semester"):
        ct = audit.get("categories", {}).get("critical_tracking", {})
        sections.append(
            "CRITICAL TRACKING:\n"
            f"  Status: {audit.get('critical_tracking_status')}\n"
            f"  Courses still needed: {', '.join(ct.get('courses_remaining', [])) or 'none'}\n"
            f"  {ct.get('notes', '')}"
        )

    if focus in ("general", "model_plan", "next_semester"):
        if current_plan:
            sections.append(
                f"CURRENT MODEL SEMESTER ({current_plan['category']}):\n"
                f"  Planned courses: {', '.join(current_plan.get('courses', []))}\n"
                f"  {current_plan.get('description', '')}"
            )
        if next_plan:
            sections.append(
                f"NEXT MODEL SEMESTER ({next_plan['category']}):\n"
                f"  Planned courses: {', '.join(next_plan.get('courses', []))}\n"
                f"  {next_plan.get('description', '')}"
            )

    if focus in ("general", "next_semester"):
        rec = audit.get("next_semester_recommendation", {})
        if rec:
            sections.append(
                f"STORED NEXT-SEMESTER RECOMMENDATION ({rec.get('term')}):\n"
                f"  Courses: {', '.join(rec.get('courses', []))}\n"
                f"  Source: {rec.get('source', '')}"
            )

        recommendations = recommend_courses(audit, courses_db, target_term)
        ready = [c for c in recommendations if c["prerequisites_met"]]
        blocked = [c for c in recommendations if not c["prerequisites_met"]]

        rec_lines = [f"OPTIMIZED RECOMMENDATIONS FOR {target_term or 'next term'}:"]
        if ready:
            rec_lines.append("  Ready to take now (prerequisites satisfied):")
            for c in ready:
                rec_lines.append(f"    - {format_course_line(c)}")
        if blocked[:3]:
            rec_lines.append("  Not yet eligible (missing prerequisites):")
            for c in blocked[:3]:
                rec_lines.append(f"    - {format_course_line(c)}")
        total_credits = sum(c["credits"] for c in ready[:5])
        rec_lines.append(
            f"  Suggested load: {min(len(ready), 5)} courses, ~{total_credits} credits"
        )
        sections.append("\n".join(rec_lines))

    if focus == "prerequisites":
        if not course_query:
            return "For prerequisites focus, provide course_query (e.g. 'COP 4600')."
        query_norm = _normalize_course_id(course_query)
        matched_id = next(
            (cid for cid in courses_db if _normalize_course_id(cid) == query_norm),
            None,
        )
        if not matched_id:
            return f"Course '{course_query}' not found in course registry."
        info = courses_db[matched_id]
        met, missing = prerequisites_satisfied(matched_id, completed, in_progress, courses_db)
        sections.append(
            f"PREREQUISITES FOR {matched_id} ({info.get('title')}):\n"
            f"  Required: {', '.join(info.get('prerequisites') or []) or 'none'}\n"
            f"  Student has met prerequisites: {'yes' if met else 'no'}\n"
            f"  Still needed: {', '.join(missing) or 'none'}\n"
            f"  Credits: {info.get('credits')}\n"
            f"  Offered: {', '.join(info.get('offered', []))}\n"
            f"  Critical tracking: {info.get('critical_tracking', False)}"
        )

    if focus == "graduation_path":
        remaining = collect_remaining_courses(audit)
        catalog_remaining = [c for c in remaining if _is_catalog_course(c)]
        sections.append(
            f"GRADUATION PATH:\n"
            f"  Credits remaining: "
            f"{max(0, audit.get('credits_total', 120) - audit.get('credits_earned', 0))}\n"
            f"  Catalog courses remaining: {len(catalog_remaining)}\n"
            f"  Non-catalog requirements: "
            f"{', '.join(c for c in remaining if not _is_catalog_course(c)) or 'none'}\n"
            f"  Advisor notes: {audit.get('advisor_notes', '')}"
        )

    if audit.get("advisor_notes") and focus == "general":
        sections.append(f"ADVISOR NOTES: {audit['advisor_notes']}")

    return "\n\n".join(sections)


def build_optimized_graduation_plan(student_id: str | None = None) -> dict:
    audit = get_student_record(student_id)
    courses_db = get_course_registry()
    if not audit:
        return {"semesters": [], "credits_remaining": 0, "total_courses": 0}

    credits_left = max(0, audit.get("credits_total", 120) - audit.get("credits_earned", 0))
    completed = list(audit.get("completed_courses", []))
    in_progress = list(audit.get("in_progress", []))
    sim_completed = completed + in_progress
    taken = _taken_set(completed, in_progress)

    catalog_remaining = [
        c
        for c in collect_remaining_courses(audit)
        if _is_catalog_course(c) and _normalize_course_id(c) not in taken
    ]

    ordered: list[str] = []
    pool = list(catalog_remaining)
    safety = len(pool) * 3
    while pool and safety > 0:
        safety -= 1
        progress = False
        for course_id in list(pool):
            met, _ = prerequisites_satisfied(course_id, sim_completed, [], courses_db)
            if met:
                ordered.append(course_id)
                sim_completed.append(course_id)
                pool.remove(course_id)
                progress = True
        if not progress:
            ordered.extend(pool)
            break

    terms = ["Fall 2026", "Spring 2027", "Fall 2027", "Spring 2028", "Fall 2028", "Spring 2029"]
    semesters = []
    for i in range(0, len(ordered), 4):
        term_courses = ordered[i : i + 4]
        semesters.append(
            {
                "term": terms[len(semesters)] if len(semesters) < len(terms) else f"Term {len(semesters) + 1}",
                "courses": [
                    {
                        "id": cid,
                        "title": courses_db.get(cid, {}).get("title", cid),
                        "credits": courses_db.get(cid, {}).get("credits", 3),
                    }
                    for cid in term_courses
                ],
            }
        )

    return {
        "semesters": semesters,
        "credits_remaining": credits_left,
        "total_courses": len(ordered),
    }
