"""
Rhetoric practice types: stasis_classify, trope_hunter, dispositio_sort, enthymeme_excavator.
Exports NORMALIZERS, GRADERS, and SECRET_FIELDS.
Standard library only.
"""
from typing import Any, Dict, List, Optional, Set

SECRET_FIELDS: Set[str] = {"correct_stasis", "target_trope", "solution", "unstated_premise"}

STASES = {"conjecture", "definition", "quality", "policy", "procedure"}

CLASSICAL_DISPOSITIO = ["exordium", "narratio", "partitio", "confirmatio", "refutatio", "peroratio"]


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


# ---- 1. stasis_classify ----
def _np_stasis_classify(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    case = _s(p.get("case") or p.get("text"), 1000)
    stasis = _s(p.get("correct_stasis") or p.get("stasis") or p.get("solution"), 40).lower()
    if not case or stasis not in STASES:
        return None
    return {
        **base,
        "case": case,
        "correct_stasis": stasis,
        "options": ["conjecture", "definition", "quality", "policy"],
    }


def _grade_stasis_classify(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("correct_stasis", "").lower()
    sub = str(submission or "").strip().lower()
    ok = (sub == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Correct rhetorical stasis identified: '{expected}'!" if ok else f"Incorrect stasis. The debate turns on '{expected}'.",
        "details": {"submitted": sub},
    }


# ---- 2. trope_hunter ----
def _np_trope_hunter(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    passage = _s(p.get("passage") or p.get("text"), 800)
    target = _s(p.get("target_trope") or p.get("trope") or p.get("solution"), 80).lower()
    options = [_s(x, 80).lower() for x in p.get("options", []) if _s(x, 80)]
    if not passage or not target:
        return None
    if options and target not in options:
        options.append(target)
    return {
        **base,
        "passage": passage,
        "target_trope": target,
        "options": options,
    }


def _grade_trope_hunter(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("target_trope", "").lower()
    sub = str(submission or "").strip().lower()
    ok = (sub == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Correct rhetorical trope spotted: '{expected}'!" if ok else "Incorrect trope identification.",
        "details": {"submitted": sub},
    }


# ---- 3. dispositio_sort ----
def _np_dispositio_sort(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_sections = p.get("sections")
    parts = p.get("parts") or []
    solution = p.get("solution")
    if not isinstance(solution, list) or len(solution) < 3:
        # Check if parts or sections are provided and match classical dispositio
        if isinstance(parts, list) and len(parts) >= 3:
            solution = [p for p in CLASSICAL_DISPOSITIO if p in parts]
    if not isinstance(solution, list) or len(solution) < 3:
        return None
    clean_sol = [str(x).strip().lower() for x in solution]
    return {
        **base,
        "parts": parts or clean_sol,
        "sections": raw_sections or {},
        "solution": clean_sol,
    }


def _grade_dispositio_sort(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = [x.strip().lower() for x in item.get("solution", [])]
    if not isinstance(submission, list):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be an ordered list of dispositio parts", "details": {}}
    sub = [str(x).strip().lower() for x in submission]
    ok = (sub == expected)
    matches = sum(1 for a, b in zip(sub, expected) if a == b)
    score = round(matches / max(len(expected), 1), 2)
    return {
        "ok": ok,
        "score": 1.0 if ok else score,
        "feedback": "Classical oration sequenced into canonical dispositio!" if ok else f"Sequence matched {matches}/{len(expected)} parts.",
        "details": {"submitted": sub},
    }


# ---- 4. enthymeme_excavator ----
def _np_enthymeme_excavator(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    premise = _s(p.get("stated_premise") or p.get("premise"), 500)
    conclusion = _s(p.get("conclusion"), 500)
    options = [_s(x, 500) for x in p.get("options", []) if _s(x, 500)]
    solution = p.get("solution") or p.get("unstated_premise")
    if not premise or not conclusion or len(options) < 2:
        return None
    if isinstance(solution, int) and 0 <= solution < len(options):
        sol_text = options[solution]
    else:
        sol_text = _s(solution, 500)
    if not sol_text or sol_text not in options:
        return None
    return {
        **base,
        "stated_premise": premise,
        "conclusion": conclusion,
        "options": options,
        "solution": sol_text,
        "unstated_premise": sol_text,
    }


def _grade_enthymeme_excavator(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = str(item.get("solution", "")).strip().lower()
    options = item.get("options", [])
    if isinstance(submission, int) and 0 <= submission < len(options):
        sub_text = options[submission].strip().lower()
    else:
        sub_text = str(submission or "").strip().lower()

    ok = (sub_text == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Correct unstated bridge premise excavated!" if ok else "The selected premise does not validly complete the enthymeme.",
        "details": {"submitted": sub_text},
    }


NORMALIZERS = {
    "stasis_classify": _np_stasis_classify,
    "trope_hunter": _np_trope_hunter,
    "dispositio_sort": _np_dispositio_sort,
    "enthymeme_excavator": _np_enthymeme_excavator,
}

GRADERS = {
    "stasis_classify": _grade_stasis_classify,
    "trope_hunter": _grade_trope_hunter,
    "dispositio_sort": _grade_dispositio_sort,
    "enthymeme_excavator": _grade_enthymeme_excavator,
}
