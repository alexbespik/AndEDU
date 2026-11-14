"""
Art History practice types: composition_vector, label_architecture, iconography_decode, stylistic_taxonomy.
Exports NORMALIZERS, GRADERS, and SECRET_FIELDS.
Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"focal_point", "solution", "period"}


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


# ---- 1. composition_vector ----
def _np_composition_vector(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_pt = p.get("focal_point") or p.get("point") or p.get("target")
    x, y = None, None
    if isinstance(raw_pt, dict):
        x, y = raw_pt.get("x"), raw_pt.get("y")
    elif isinstance(raw_pt, (list, tuple)) and len(raw_pt) == 2:
        x, y = raw_pt[0], raw_pt[1]
    if x is None or y is None:
        return None
    try:
        xf, yf = float(x), float(y)
    except (ValueError, TypeError):
        return None
    tol = p.get("tolerance", 0.035)
    try:
        tol = min(0.1, max(0.005, float(tol)))
    except (ValueError, TypeError):
        tol = 0.035

    return {
        **base,
        "image_url": _s(p.get("image_url") or p.get("image"), 400),
        "focal_point": {"x": round(xf, 4), "y": round(yf, 4)},
        "tolerance": tol,
    }


def _grade_composition_vector(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    target = item.get("focal_point", {})
    tx, ty = target.get("x", 0.5), target.get("y", 0.5)
    tol = item.get("tolerance", 0.035)

    sx, sy = None, None
    if isinstance(submission, dict):
        sx, sy = submission.get("x"), submission.get("y")
    elif isinstance(submission, (list, tuple)) and len(submission) == 2:
        sx, sy = submission[0], submission[1]

    if sx is None or sy is None:
        return {"ok": False, "score": 0.0, "feedback": "Submission must provide x and y coordinates", "details": {}}
    try:
        sxf, syf = float(sx), float(sy)
    except (ValueError, TypeError):
        return {"ok": False, "score": 0.0, "feedback": "Coordinates must be numbers", "details": {}}

    dist = math.hypot(sxf - tx, syf - ty)
    ok = (dist <= tol)
    score = 1.0 if ok else max(0.0, round(1.0 - (dist / (tol * 4.0)), 2))
    return {
        "ok": ok,
        "score": score,
        "feedback": f"Focal point located accurately! (distance: {round(dist, 4)} <= {tol})" if ok else f"Focal point off target (distance: {round(dist, 4)} > {tol}).",
        "details": {"distance": round(dist, 4), "tolerance": tol},
    }


# ---- 2. label_architecture ----
def _np_label_architecture(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    elements = [_s(x, 100) for x in p.get("elements", []) if _s(x, 100)]
    solution = p.get("solution") or p.get("expected")
    if not isinstance(solution, dict) or not solution:
        return None
    clean_sol = {str(k).strip(): str(v).strip() for k, v in solution.items()}
    return {
        **base,
        "elements": elements or list(clean_sol.values()),
        "labels": list(clean_sol.keys()),
        "solution": clean_sol,
        "image_url": _s(p.get("image_url") or p.get("image"), 400),
    }


def _grade_label_architecture(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("solution", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be a mapping of labels to elements", "details": {}}

    correct = 0
    total = max(len(expected), 1)
    for k, v in expected.items():
        if str(submission.get(k, "")).strip().lower() == v.strip().lower():
            correct += 1

    score = round(correct / total, 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "All architectural features identified correctly!" if ok else f"Correct on {correct}/{total} architectural labels.",
        "details": {"accuracy": score},
    }


# ---- 3. iconography_decode ----
def _np_iconography_decode(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    symbols = [_s(x, 120) for x in p.get("symbols", []) if _s(x, 120)]
    solution = p.get("solution") or p.get("attributes")
    if not isinstance(solution, dict) or not solution:
        return None
    clean_sol = {str(k).strip(): str(v).strip() for k, v in solution.items()}
    return {
        **base,
        "symbols": symbols or list(clean_sol.keys()),
        "solution": clean_sol,
    }


def _grade_iconography_decode(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("solution", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be a mapping of symbols to figures/attributes", "details": {}}

    correct = 0
    total = max(len(expected), 1)
    for k, v in expected.items():
        sub_val = str(submission.get(k, "")).strip().lower()
        if sub_val == v.strip().lower():
            correct += 1

    score = round(correct / total, 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Iconographic symbols decoded successfully!" if ok else f"Decoded {correct}/{total} iconographic attributes.",
        "details": {"accuracy": score},
    }


# ---- 4. stylistic_taxonomy ----
def _np_stylistic_taxonomy(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    traits = [_s(x, 200) for x in p.get("traits", []) if _s(x, 200)]
    period = _s(p.get("period") or p.get("movement"), 100)
    options = [_s(x, 100) for x in p.get("options", []) if _s(x, 100)]
    if not traits or not period:
        return None
    if options and period not in options:
        options.append(period)
    return {
        **base,
        "traits": traits,
        "period": period,
        "options": options,
    }


def _grade_stylistic_taxonomy(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = str(item.get("period", "")).strip().lower()
    sub = str(submission or "").strip().lower()
    ok = (sub == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Correct period taxonomy: {item.get('period')}!" if ok else "Incorrect stylistic classification.",
        "details": {"submitted": submission},
    }


NORMALIZERS = {
    "composition_vector": _np_composition_vector,
    "label_architecture": _np_label_architecture,
    "iconography_decode": _np_iconography_decode,
    "stylistic_taxonomy": _np_stylistic_taxonomy,
}

GRADERS = {
    "composition_vector": _grade_composition_vector,
    "label_architecture": _grade_label_architecture,
    "iconography_decode": _grade_iconography_decode,
    "stylistic_taxonomy": _grade_stylistic_taxonomy,
}
