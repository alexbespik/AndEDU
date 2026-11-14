"""
Academic Advising Rule Engine & Degree Requirement Validator.
Supports:
- Cardinality clauses: k-of-n course selections
- Credit pools: Minimum credit thresholds across eligible departmental levels
- Min-grade enforcement: Hierarchical letter grade comparisons
- Columbia 3+2 Combined Plan Pre-Engineering dual-degree tracking
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

GRADE_RANKS: Dict[str, float] = {
    "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
    "P": 2.0, "PASS": 2.0, "CR": 2.0, "T": 2.0, "TRANSFER": 2.0,
}


def is_grade_sufficient(earned_grade: Optional[str], min_grade: str = "D-") -> bool:
    """Returns True if earned_grade satisfies the required min_grade threshold."""
    if not earned_grade:
        return False
    clean_earned = earned_grade.strip().upper()
    clean_min = min_grade.strip().upper()
    rank_earned = GRADE_RANKS.get(clean_earned, 0.0)
    rank_min = GRADE_RANKS.get(clean_min, 0.7)
    return rank_earned >= rank_min


def normalize_code(code: str) -> str:
    """Normalizes course codes e.g. 'math 111' -> 'MATH 111'."""
    return re.sub(r"\s+", " ", (code or "").strip()).upper()


def evaluate_req_node(
    node: Dict[str, Any],
    completed_courses: List[Dict[str, Any]],
    used_courses: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluates an arbitrary degree requirement AST node against completed courses.
    Node types:
    - 'course': Single course requirement with optional min_grade
    - 'k_of_n': Cardinality requirement (at least k of n items satisfied)
    - 'credit_pool': Minimum credit sum from eligible courses
    - 'all_of': Logical AND of children
    - 'one_of': Logical OR of children (k_of_n with k=1)
    """
    if used_courses is None:
        used_courses = set()

    node_type = node.get("type", "course")
    name = node.get("name", "")

    # 1. Single course
    if node_type == "course":
        target_code = normalize_code(node.get("code", ""))
        min_grade = node.get("min_grade", "D-")
        for rec in completed_courses:
            rec_code = normalize_code(rec.get("code", ""))
            if rec_code == target_code and rec_code not in used_courses:
                earned_grade = rec.get("grade", "P")
                if is_grade_sufficient(earned_grade, min_grade):
                    credits_val = float(rec.get("credits") or 3.0)
                    return {
                        "met": True,
                        "name": name or target_code,
                        "earned_credits": credits_val,
                        "satisfied_courses": [target_code],
                        "missing": [],
                        "details": {"code": target_code, "grade": earned_grade, "min_grade": min_grade},
                    }
        return {
            "met": False,
            "name": name or target_code,
            "earned_credits": 0.0,
            "satisfied_courses": [],
            "missing": [target_code],
            "details": {"code": target_code, "min_grade": min_grade},
        }

    # 2. Cardinality clause: k_of_n
    if node_type in ("k_of_n", "one_of"):
        k = 1 if node_type == "one_of" else int(node.get("k", 1))
        children = node.get("children", [])
        satisfied_sub = []
        missing_sub = []
        earned_cr = 0.0
        matched_courses: List[str] = []

        local_used = set(used_courses)
        for child in children:
            res = evaluate_req_node(child, completed_courses, local_used)
            if res["met"]:
                satisfied_sub.append(res)
                earned_cr += res["earned_credits"]
                for c in res["satisfied_courses"]:
                    matched_courses.append(c)
                    local_used.add(c)
            else:
                missing_sub.append(res)

        met = len(satisfied_sub) >= k
        return {
            "met": met,
            "name": name or f"{k}-of-{len(children)} requirement",
            "k": k,
            "needed": max(0, k - len(satisfied_sub)),
            "earned_credits": earned_cr,
            "satisfied_courses": matched_courses,
            "missing": [c.get("code") or c.get("name") for c in missing_sub] if not met else [],
            "details": {"satisfied_count": len(satisfied_sub), "required_count": k},
        }

    # 3. Credit Pool
    if node_type == "credit_pool":
        min_credits = float(node.get("min_credits", 9.0))
        prefixes = [p.upper() for p in node.get("prefixes", [])]
        level_min = int(node.get("level_min", 100))
        level_max = int(node.get("level_max", 499))
        min_grade = node.get("min_grade", "D-")
        specific_options = [normalize_code(c) for c in node.get("options", [])]

        pool_earned = 0.0
        pool_courses: List[str] = []

        for rec in completed_courses:
            rec_code = normalize_code(rec.get("code", ""))
            if rec_code in used_courses:
                continue

            parts = rec_code.split()
            dept = parts[0] if parts else ""
            num_match = re.search(r"\d+", parts[1] if len(parts) > 1 else "")
            num = int(num_match.group(0)) if num_match else 0

            match_dept = (dept in prefixes) if prefixes else True
            match_level = (level_min <= num <= level_max)
            match_option = (rec_code in specific_options) if specific_options else False

            if (match_dept and match_level) or match_option:
                if is_grade_sufficient(rec.get("grade", "P"), min_grade):
                    cr = float(rec.get("credits") or 3.0)
                    pool_earned += cr
                    pool_courses.append(rec_code)

        met = (pool_earned >= min_credits)
        return {
            "met": met,
            "name": name or f"{min_credits}-credit pool",
            "min_credits": min_credits,
            "earned_credits": pool_earned,
            "satisfied_courses": pool_courses,
            "missing": [f"{min_credits - pool_earned:.1f} credits needed"] if not met else [],
            "details": {"earned": pool_earned, "target": min_credits},
        }

    # 4. Logical AND: all_of
    if node_type == "all_of":
        children = node.get("children", [])
        all_met = True
        total_cr = 0.0
        all_satisfied: List[str] = []
        all_missing: List[str] = []

        local_used = set(used_courses)
        for child in children:
            res = evaluate_req_node(child, completed_courses, local_used)
            total_cr += res["earned_credits"]
            all_satisfied.extend(res["satisfied_courses"])
            local_used.update(res["satisfied_courses"])
            if not res["met"]:
                all_met = False
                all_missing.extend(res["missing"])

        return {
            "met": all_met,
            "name": name or "All required components",
            "earned_credits": total_cr,
            "satisfied_courses": all_satisfied,
            "missing": all_missing,
            "details": {},
        }

    return {"met": False, "name": name, "earned_credits": 0.0, "satisfied_courses": [], "missing": [], "details": {}}


# ---------------------------------------------------------------------------
# Columbia 3+2 Combined Plan Pre-Engineering Track Definition
# ---------------------------------------------------------------------------
COLUMBIA_3_2_PLAN: Dict[str, Any] = {
    "name": "Columbia University 3+2 Combined Plan Pre-Engineering",
    "target_gpa": 3.30,
    "foundational_requirements": {
        "type": "all_of",
        "name": "Columbia 3+2 Foundational Core",
        "children": [
            # Calculus sequence
            {"type": "course", "code": "MATH 111", "min_grade": "B", "name": "Calculus I"},
            {"type": "course", "code": "MATH 112", "min_grade": "B", "name": "Calculus II"},
            {
                "type": "one_of",
                "name": "Multivariable Calculus",
                "children": [
                    {"type": "course", "code": "MATH 212", "min_grade": "B"},
                    {"type": "course", "code": "MATH 213", "min_grade": "B"},
                ],
            },
            # Linear Algebra & ODE
            {"type": "course", "code": "MATH 211", "min_grade": "B", "name": "Linear Algebra"},
            {"type": "course", "code": "MATH 302", "min_grade": "B", "name": "Ordinary Differential Equations"},
            # Physics sequence
            {
                "type": "all_of",
                "name": "Physics I & Lab",
                "children": [
                    {
                        "type": "one_of",
                        "children": [
                            {"type": "course", "code": "PHYS 101", "min_grade": "B"},
                            {"type": "course", "code": "PHYS 107", "min_grade": "B"},
                        ],
                    },
                    {"type": "course", "code": "PHYS 101L", "min_grade": "B"},
                ],
            },
            {
                "type": "all_of",
                "name": "Physics II & Lab",
                "children": [
                    {
                        "type": "one_of",
                        "children": [
                            {"type": "course", "code": "PHYS 102", "min_grade": "B"},
                            {"type": "course", "code": "PHYS 108", "min_grade": "B"},
                        ],
                    },
                    {"type": "course", "code": "PHYS 102L", "min_grade": "B"},
                ],
            },
            # Chemistry
            {
                "type": "all_of",
                "name": "General Chemistry & Lab",
                "children": [
                    {"type": "course", "code": "CHEM 103", "min_grade": "B"},
                    {"type": "course", "code": "CHEM 103L", "min_grade": "B"},
                ],
            },
            # Computer Science
            {"type": "course", "code": "CSCI 141", "min_grade": "B", "name": "Computational Problem Solving"},
            # Economics
            {
                "type": "one_of",
                "name": "Principles of Economics",
                "children": [
                    {"type": "course", "code": "ECON 101", "min_grade": "B"},
                    {"type": "course", "code": "ECON 102", "min_grade": "B"},
                ],
            },
            # English / Writing
            {
                "type": "one_of",
                "name": "College Writing",
                "children": [
                    {"type": "course", "code": "COLL 150", "min_grade": "B"},
                    {"type": "course", "code": "WRIT 101", "min_grade": "B"},
                ],
            },
        ],
    },
}


def audit_columbia_3_2(completed_courses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluates readiness for the Columbia 3+2 Combined Plan Pre-Engineering track."""
    eval_res = evaluate_req_node(COLUMBIA_3_2_PLAN["foundational_requirements"], completed_courses)

    # Compute GPA across science & math foundation
    stem_codes = {"MATH", "PHYS", "CHEM", "CSCI", "DATA"}
    stem_grades = []
    for rec in completed_courses:
        parts = normalize_code(rec.get("code", "")).split()
        if parts and parts[0] in stem_codes:
            g = rec.get("grade", "").upper()
            if g in GRADE_RANKS and g not in ("P", "CR", "T"):
                stem_grades.append(GRADE_RANKS[g])

    stem_gpa = round(sum(stem_grades) / len(stem_grades), 2) if stem_grades else 0.0
    gpa_met = (stem_gpa >= COLUMBIA_3_2_PLAN["target_gpa"])

    return {
        "program": COLUMBIA_3_2_PLAN["name"],
        "target_gpa": COLUMBIA_3_2_PLAN["target_gpa"],
        "stem_gpa": stem_gpa,
        "gpa_met": gpa_met,
        "courses_met": eval_res["met"],
        "eligible": eval_res["met"] and gpa_met,
        "satisfied_courses": eval_res["satisfied_courses"],
        "missing_courses": eval_res["missing"],
        "earned_credits": eval_res["earned_credits"],
    }
