"""One-time script to build Moss indexes from academic data JSON files."""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from moss import DocumentInfo, MossClient, MutationOptions

DATA_DIR = Path(__file__).parent / "data"
INDEXES = ("degree_audit", "course_registry", "major_requirements")


def load_json(filename: str) -> list:
    path = DATA_DIR / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def degree_audit_to_doc(record: dict, idx: int) -> DocumentInfo:
    categories = record.get("categories", {})
    cat_lines = []
    for cat, info in categories.items():
        earned = info.get("earned", 0)
        required = info.get("required", 0)
        remaining = info.get("courses_remaining", [])
        remaining_str = ", ".join(remaining) if remaining else "none"
        cat_lines.append(
            f"{cat}: {earned}/{required} credits earned, courses remaining: {remaining_str}"
        )

    completed = ", ".join(record.get("completed_courses", [])) or "none"
    in_progress = ", ".join(record.get("in_progress", [])) or "none"

    text = (
        f"Student {record.get('name', 'Unknown')} (ID: {record.get('student_id', idx)}). "
        f"Major: {record.get('major', 'Undeclared')}. "
        f"Year: {record.get('year', 'Unknown')}. "
        f"GPA: {record.get('gpa', 'N/A')}. "
        f"Credits: {record.get('credits_earned', 0)} earned of "
        f"{record.get('credits_total', 0)} required. "
        f"Completed courses: {completed}. "
        f"In progress: {in_progress}. "
        f"Category progress: {'; '.join(cat_lines) or 'none'}."
    )

    return DocumentInfo(
        id=record.get("student_id", f"student-{idx}"),
        text=text,
        metadata={
            "type": "degree_audit",
            "name": record.get("name", ""),
            "major": record.get("major", ""),
        },
    )


def course_registry_to_doc(record: dict, idx: int) -> DocumentInfo:
    prereqs = ", ".join(record.get("prerequisites", [])) or "none"
    offered = ", ".join(record.get("offered", [])) or "unknown"

    text = (
        f"Course {record.get('course_id', f'course-{idx}')}: {record.get('title', 'Untitled')}. "
        f"Credits: {record.get('credits', 0)}. "
        f"Prerequisites: {prereqs}. "
        f"Offered: {offered}. "
        f"Description: {record.get('description', '')}"
    )

    return DocumentInfo(
        id=record.get("course_id", f"course-{idx}"),
        text=text,
        metadata={
            "type": "course_registry",
            "course_id": record.get("course_id", ""),
        },
    )


def major_requirements_to_doc(record: dict, idx: int) -> DocumentInfo:
    courses = ", ".join(record.get("courses", [])) or "none"

    text = (
        f"Major {record.get('major', 'Unknown')}, category {record.get('category', 'General')}. "
        f"Required credits: {record.get('required_credits', 0)}. "
        f"Required courses: {courses}. "
        f"Description: {record.get('description', '')}"
    )

    return DocumentInfo(
        id=f"{record.get('major', 'major')}-{record.get('category', idx)}-{idx}",
        text=text,
        metadata={
            "type": "major_requirements",
            "major": record.get("major", ""),
            "category": record.get("category", ""),
        },
    )


def build_docs(index_name: str, records: list) -> list[DocumentInfo]:
    if not records:
        return []

    converters = {
        "degree_audit": degree_audit_to_doc,
        "course_registry": course_registry_to_doc,
        "major_requirements": major_requirements_to_doc,
    }
    converter = converters[index_name]
    return [converter(record, i) for i, record in enumerate(records)]


async def upsert_index(client: MossClient, index_name: str, docs: list[DocumentInfo]) -> None:
    if not docs:
        print(f"  {index_name}: no documents (skipping)")
        return

    try:
        result = await client.create_index(index_name, docs, "moss-minilm")
        print(f"  {index_name}: created with {result.doc_count} documents")
    except Exception:
        result = await client.add_docs(
            index_name, docs, MutationOptions(upsert=True)
        )
        print(f"  {index_name}: upserted {result.doc_count} documents")


async def main() -> None:
    load_dotenv(".env.local")

    project_id = os.environ.get("MOSS_PROJECT_ID")
    project_key = os.environ.get("MOSS_PROJECT_KEY")
    if not project_id or not project_key:
        raise SystemExit("MOSS_PROJECT_ID and MOSS_PROJECT_KEY must be set in .env.local")

    client = MossClient(project_id, project_key)

    data_sources = {
        "degree_audit": load_json("degree_audit.json"),
        "course_registry": load_json("course_registry.json"),
        "major_requirements": load_json("major_requirements.json"),
    }

    print("Building Moss indexes...")
    for index_name in INDEXES:
        docs = build_docs(index_name, data_sources[index_name])
        await upsert_index(client, index_name, docs)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
