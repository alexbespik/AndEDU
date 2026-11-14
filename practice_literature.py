"""
Literature practice types: scansion, volta_spot, rhyme_scheme_audit, chronology_unravel.
Exports NORMALIZERS, GRADERS, and SECRET_FIELDS.
Standard library only.
"""
import re
from typing import Any, Dict, List, Optional, Set

SECRET_FIELDS: Set[str] = {"stress_pattern", "target_index", "target_line", "rhyme_scheme", "canonical_order"}


def _s(v: Any, limit: int = 1000) -> str:
    return str(v if v is not None else "").strip()[:limit]


# ---- 1. scansion ----
def _np_scansion(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    line = _s(p.get("line") or p.get("text"), 500)
    if not line:
        return None
    meter = _s(p.get("meter"), 120) or "iambic pentameter"
    raw_pattern = p.get("stress_pattern") or p.get("pattern")
    if isinstance(raw_pattern, list):
        pat_str = " ".join(str(x).strip() for x in raw_pattern)
    elif isinstance(raw_pattern, str):
        pat_str = " ".join(re.findall(r"[01u/]", raw_pattern))
    else:
        return None
    # Normalize u -> 0, / -> 1
    normalized_pattern = " ".join("1" if c in ("1", "/") else "0" for c in pat_str.split())
    if not normalized_pattern:
        return None
    return {
        **base,
        "line": line,
        "meter": meter,
        "stress_pattern": normalized_pattern,
    }


def _grade_scansion(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("stress_pattern", "")
    exp_tokens = expected.split()
    if not exp_tokens:
        return {"ok": False, "score": 0.0, "feedback": "Missing expected stress pattern in item", "details": {}}

    if isinstance(submission, list):
        sub_str = " ".join(str(x).strip() for x in submission)
    elif isinstance(submission, str):
        sub_str = submission.strip()
    else:
        return {"ok": False, "score": 0.0, "feedback": "Submission must be a string or list of stresses", "details": {}}

    sub_tokens = ["1" if c in ("1", "/") else "0" for c in re.findall(r"[01u/]", sub_str)]
    if len(sub_tokens) != len(exp_tokens):
        return {
            "ok": False,
            "score": 0.0,
            "feedback": f"Expected {len(exp_tokens)} syllables but got {len(sub_tokens)}.",
            "details": {"expected_length": len(exp_tokens), "submitted_length": len(sub_tokens)},
        }

    correct_count = sum(1 for e, s in zip(exp_tokens, sub_tokens) if e == s)
    score = round(correct_count / len(exp_tokens), 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Correct metrical scansion!" if ok else f"Scansion matched {correct_count}/{len(exp_tokens)} syllables.",
        "details": {"submitted": " ".join(sub_tokens), "accuracy": score},
    }


# ---- 2. volta_spot ----
def _np_volta_spot(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lines = [_s(x, 300) for x in p.get("lines", []) if _s(x, 300)]
    if len(lines) < 2:
        return None
    target_idx = p.get("target_index")
    if target_idx is None and p.get("target_line") is not None:
        try:
            target_idx = int(p["target_line"]) - 1
        except (ValueError, TypeError):
            target_idx = None
    if target_idx is None:
        return None
    try:
        target_idx = int(target_idx)
    except (ValueError, TypeError):
        return None
    if not (0 <= target_idx < len(lines)):
        return None
    return {
        **base,
        "lines": lines,
        "target_index": target_idx,
    }


def _grade_volta_spot(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("target_index")
    lines = item.get("lines", [])
    try:
        sub = int(submission)
    except (ValueError, TypeError):
        return {"ok": False, "score": 0.0, "feedback": "Please submit a valid line number or index", "details": {}}

    # Accept either 0-based or 1-based index
    if sub == expected or sub == expected + 1:
        return {
            "ok": True,
            "score": 1.0,
            "feedback": f"Correct! Line {expected + 1} marks the volta (poetic turn).",
            "details": {"line": lines[expected] if expected < len(lines) else ""},
        }
    return {
        "ok": False,
        "score": 0.0,
        "feedback": "The chosen line is not the poetic volta.",
        "details": {"submitted": sub},
    }


# ---- 3. rhyme_scheme_audit ----
def _np_rhyme_scheme_audit(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lines = [_s(x, 300) for x in p.get("lines", []) if _s(x, 300)]
    if len(lines) < 2:
        return None
    raw_scheme = _s(p.get("rhyme_scheme") or p.get("expected"), 100)
    if not raw_scheme:
        return None
    # Normalize uppercase letters
    cleaned_scheme = " ".join("".join(re.findall(r"[A-Za-z]", part)).upper() for part in raw_scheme.split())
    if not cleaned_scheme:
        return None
    return {
        **base,
        "lines": lines,
        "rhyme_scheme": cleaned_scheme,
    }


def _grade_rhyme_scheme_audit(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("rhyme_scheme", "").replace(" ", "").upper()
    if isinstance(submission, list):
        sub_clean = "".join(str(x).strip().upper() for x in submission)
    else:
        sub_clean = "".join(re.findall(r"[A-Za-z]", str(submission or ""))).upper()

    ok = (sub_clean == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Rhyme scheme verified successfully!" if ok else "Incorrect rhyme scheme audit.",
        "details": {"submitted": sub_clean},
    }


# ---- 4. chronology_unravel ----
def _np_chronology_unravel(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_events = p.get("events")
    if not isinstance(raw_events, list) or len(raw_events) < 2:
        return None
    events = []
    for i, e in enumerate(raw_events):
        if isinstance(e, dict):
            eid = str(e.get("id") or f"e{i + 1}")
            text = _s(e.get("text") or e.get("desc"), 400)
        else:
            eid = f"e{i + 1}"
            text = _s(e, 400)
        if text:
            events.append({"id": eid, "text": text})
    if len(events) < 2:
        return None
    canonical = p.get("canonical_order") or p.get("solution")
    if not isinstance(canonical, list) or len(canonical) != len(events):
        canonical = [e["id"] for e in events]
    canonical = [str(x) for x in canonical]
    return {
        **base,
        "events": events,
        "canonical_order": canonical,
    }


def _grade_chronology_unravel(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = [str(x) for x in item.get("canonical_order", [])]
    if not isinstance(submission, list):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be an ordered list of event IDs", "details": {}}
    sub = [str(x) for x in submission]
    if sub == expected:
        return {
            "ok": True,
            "score": 1.0,
            "feedback": "Events correctly unraveled into fabula chronological order!",
            "details": {"order": sub},
        }
    # Partial credit based on matching positions
    matches = sum(1 for a, b in zip(sub, expected) if a == b)
    score = round(matches / max(len(expected), 1), 2)
    return {
        "ok": False,
        "score": score,
        "feedback": f"Partially correct: {matches}/{len(expected)} events in their proper chronological sequence.",
        "details": {"submitted": sub, "accuracy": score},
    }


NORMALIZERS = {
    "scansion": _np_scansion,
    "volta_spot": _np_volta_spot,
    "rhyme_scheme_audit": _np_rhyme_scheme_audit,
    "chronology_unravel": _np_chronology_unravel,
}

GRADERS = {
    "scansion": _grade_scansion,
    "volta_spot": _grade_volta_spot,
    "rhyme_scheme_audit": _grade_rhyme_scheme_audit,
    "chronology_unravel": _grade_chronology_unravel,
}
