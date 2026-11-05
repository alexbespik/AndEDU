"""
AI catalog classifier: infers College Curriculum (COLL 200/300) and proficiency attributes (ALV, CSI, NQR, MATH, ARTS)
for unmarked catalog courses.
"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set

import advisor
import db

ALLOWED_ATTRIBUTES: Set[str] = {"ALV", "CSI", "NQR", "COLL 200", "COLL 300", "MATH", "ARTS"}

CLASSIFY_PROMPT = """You are an academic curriculum classification engine for William & Mary.
For each of the following courses, evaluate their title, description, and prerequisites, and determine which of these official William & Mary College Curriculum attributes apply:
- ALV: Arts, Letters, Values (humanities, literature, philosophy, art history, religious studies, creative writing)
- CSI: Cultures, Societies, Individuals (social sciences, history, government, economics, sociology, anthropology, psychology)
- NQR: Natural World & Quantitative Reasoning (natural sciences, biology, chemistry, physics, mathematics, data science, computer science)
- COLL 200: Exploring Foundations (courses that explicitly bridge disciplines, anchoring in one domain while looking out to another)
- COLL 300: Cross-cultural, global, or world-community study
- MATH: Mathematics & Quantitative proficiency
- ARTS: Creative and Performing Arts practice/performance

Strict rule: Return ONLY attributes from this exact allowed set: ["ALV", "CSI", "NQR", "COLL 200", "COLL 300", "MATH", "ARTS"]. Do not invent other tags.
If none apply with high confidence, return an empty list for that course.
Return a valid JSON array of objects with "code" (string) and "attributes" (array of strings from the allowed set).

Courses to classify:
{courses_json}
"""


def get_courses_to_classify(
    school: str = "wm",
    depts: Optional[List[str]] = None,
    limit: int = 200,
    force: bool = False,
) -> List[Dict[str, Any]]:
    c = db.conn()
    sql = "SELECT * FROM catalog_courses WHERE school = ?"
    args: List[Any] = [school]
    if depts:
        cleaned_depts = [d.strip().upper() for d in depts if d.strip()]
        if cleaned_depts:
            dept_placeholders = ",".join("?" for _ in cleaned_depts)
            sql += f" AND substr(code, 1, instr(code, ' ') - 1) IN ({dept_placeholders})"
            args.extend(cleaned_depts)
    sql += " ORDER BY code"

    candidates = []
    for r in c.execute(sql, args):
        course = advisor._row(r)
        content_hash = advisor.compute_course_content_hash(course)
        if not force and course.get("inferred_hash") == content_hash:
            continue
        candidates.append(course)
        if len(candidates) >= limit:
            break
    return candidates


async def classify_catalog_courses(
    school: str = "wm",
    dry_run: bool = True,
    limit: int = 200,
    depts: Optional[List[str]] = None,
    force: bool = False,
    call_json_fn: Optional[Callable[[str], Any]] = None,
    progress_fn: Optional[Callable[[float, str], None]] = None,
) -> Dict[str, Any]:
    candidates = get_courses_to_classify(school=school, depts=depts, limit=limit, force=force)
    if not candidates:
        if progress_fn:
            progress_fn(1.0, "No courses need classification.")
        return {"total": 0, "classified": 0, "dry_run": dry_run, "updates": []}

    batches = [candidates[i:i + 40] for i in range(0, len(candidates), 40)]
    batches = batches[:20]  # Hard limit of 20 model calls per job run to guard daily budget

    all_updates: List[Dict[str, Any]] = []
    for b_idx, batch in enumerate(batches):
        if progress_fn:
            progress_fn(b_idx / len(batches), f"Classifying batch {b_idx + 1} of {len(batches)} ({len(batch)} courses)…")

        batch_input = [
            {
                "code": c["code"],
                "title": c.get("title", ""),
                "description": (c.get("description") or "")[:400],
                "prereqs": c.get("prereqs", ""),
            }
            for c in batch
        ]
        prompt = CLASSIFY_PROMPT.format(courses_json=json.dumps(batch_input, indent=2))

        batch_results = []
        if call_json_fn:
            try:
                res = call_json_fn(prompt)
                if asyncio.iscoroutine(res):
                    res = await res
                if isinstance(res, list):
                    batch_results = res
                elif isinstance(res, dict):
                    batch_results = res.get("courses") or res.get("classifications") or res.get("results") or []
            except Exception as e:
                logging.getLogger(__name__).warning("Error calling model in classifier batch %d: %s", b_idx, e)

        course_map = {c["code"]: c for c in batch}
        batch_updates = []
        for item in batch_results:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip().upper()
            if code not in course_map:
                continue
            raw_attrs = item.get("attributes") or []
            filtered_attrs = [a for a in raw_attrs if a in ALLOWED_ATTRIBUTES]
            c_obj = course_map[code]
            content_hash = advisor.compute_course_content_hash(c_obj)
            batch_updates.append({
                "code": code,
                "inferred_attributes": filtered_attrs,
                "inferred_hash": content_hash,
            })

        # If model responded, also ensure any missing batch courses get hash recorded so they aren't re-queued
        if batch_results:
            covered_codes = {u["code"] for u in batch_updates}
            for c in batch:
                if c["code"] not in covered_codes:
                    batch_updates.append({
                        "code": c["code"],
                        "inferred_attributes": [],
                        "inferred_hash": advisor.compute_course_content_hash(c),
                    })

        if not dry_run and batch_updates:
            advisor.save_inferred_attributes(batch_updates, school=school)

        all_updates.extend(batch_updates)

    if progress_fn:
        progress_fn(1.0, f"Classified {len(all_updates)} courses.")

    return {
        "total": len(candidates),
        "classified": len(all_updates),
        "batches": len(batches),
        "dry_run": dry_run,
        "updates": all_updates,
    }
