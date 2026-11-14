"""
Classics practice types: epigraphy_transcribe, harris_matrix_build, cursus_honorum_order, athenian_sortition_sim.
Exports NORMALIZERS, GRADERS, and SECRET_FIELDS.
Standard library only.
"""
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"transcription", "solution", "quotas"}


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


def _normalize_epigraphy(text: str) -> str:
    """Normalizes Latin and Greek epigraphic text:
    - Normalizes unicode (NFKD)
    - Converts ligatures (æ -> ae, œ -> oe)
    - Strips accents/diacritics and punctuation
    - Normalizes lowercase and whitespace
    """
    s = unicodedata.normalize("NFKD", text)
    s = s.replace("æ", "ae").replace("Æ", "AE").replace("œ", "oe").replace("Œ", "OE")
    s = "".join(c for c in s if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() else " " for c in s).lower()
    return " ".join(cleaned.split())


# ---- 1. epigraphy_transcribe ----
def _np_epigraphy_transcribe(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_insc = _s(p.get("inscription_raw") or p.get("inscription"), 1000)
    trans = _s(p.get("transcription") or p.get("solution"), 1000)
    if not raw_insc or not trans:
        return None
    return {
        **base,
        "inscription_raw": raw_insc,
        "transcription": trans,
        "language": _s(p.get("language") or "latin", 40),
    }


def _grade_epigraphy_transcribe(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = _normalize_epigraphy(item.get("transcription", ""))
    sub = _normalize_epigraphy(str(submission or ""))
    ok = (sub == expected)
    score = 1.0 if ok else 0.0
    return {
        "ok": ok,
        "score": score,
        "feedback": "Epigraphic inscription transcribed accurately!" if ok else "Transcription differs from normalized epigraphic reading.",
        "details": {"submitted": sub},
    }


# ---- 2. harris_matrix_build ----
def _np_harris_matrix_build(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    strata = [_s(x, 60) for x in p.get("strata", []) if _s(x, 60)]
    if len(strata) < 2:
        return None
    raw_rel = p.get("relationships") or []
    solution = p.get("solution") or []
    if not isinstance(solution, list) or not solution:
        # Default solution from relationships
        clean_sol = []
        for r in raw_rel:
            if isinstance(r, dict) and "above" in r and "below" in r:
                clean_sol.append([str(r["above"]), str(r["below"])])
            elif isinstance(r, (list, tuple)) and len(r) == 2:
                clean_sol.append([str(r[0]), str(r[1])])
        solution = clean_sol
    if not solution:
        return None
    return {
        **base,
        "strata": strata,
        "relationships": raw_rel,
        "solution": [[str(x[0]), str(x[1])] for x in solution if len(x) == 2],
    }


def _grade_harris_matrix_build(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = {f"{x[0]}->{x[1]}" for x in item.get("solution", []) if len(x) == 2}
    sub_edges: Set[str] = set()
    if isinstance(submission, list):
        for e in submission:
            if isinstance(e, (list, tuple)) and len(e) == 2:
                sub_edges.add(f"{e[0]}->{e[1]}")
            elif isinstance(e, dict) and "above" in e and "below" in e:
                sub_edges.add(f"{e['above']}->{e['below']}")
            elif isinstance(e, str) and "->" in e:
                parts = e.split("->")
                sub_edges.add(f"{parts[0].strip()}->{parts[1].strip()}")

    tp = len(expected & sub_edges)
    total = max(len(expected), 1)
    score = round(tp / total, 2)
    ok = (score == 1.0 and len(sub_edges) == len(expected))
    return {
        "ok": ok,
        "score": score,
        "feedback": "Stratigraphic Harris Matrix verified!" if ok else f"Correct on {tp}/{total} stratigraphic relations.",
        "details": {"submitted": sorted(list(sub_edges))},
    }


# ---- 3. cursus_honorum_order ----
def _np_cursus_honorum_order(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    offices = [_s(x, 100) for x in p.get("offices", []) if _s(x, 100)]
    solution = p.get("solution") or p.get("canonical_order")
    if not isinstance(solution, list) or len(solution) < 3:
        return None
    clean_sol = [_s(x, 100) for x in solution if _s(x, 100)]
    return {
        **base,
        "offices": offices or clean_sol,
        "solution": clean_sol,
    }


def _grade_cursus_honorum_order(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = [x.strip().lower() for x in item.get("solution", [])]
    if not isinstance(submission, list):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be an ordered list of offices", "details": {}}
    sub = [str(x).strip().lower() for x in submission]
    ok = (sub == expected)
    matches = sum(1 for a, b in zip(sub, expected) if a == b)
    score = round(matches / max(len(expected), 1), 2)
    return {
        "ok": ok,
        "score": 1.0 if ok else score,
        "feedback": "Roman cursus honorum sequenced in proper constitutional hierarchy!" if ok else f"Sequence matched {matches}/{len(expected)} offices.",
        "details": {"submitted": sub},
    }


# ---- 4. athenian_sortition_sim ----
def _np_athenian_sortition_sim(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    candidates = p.get("candidates") or {}
    quotas = p.get("quotas") or {}
    if not isinstance(candidates, dict) or not isinstance(quotas, dict) or not quotas:
        return None
    clean_cands = {str(k): [str(c) for c in v] for k, v in candidates.items() if isinstance(v, list)}
    clean_quotas = {str(k): int(v) for k, v in quotas.items() if isinstance(v, (int, float))}
    return {
        **base,
        "candidates": clean_cands,
        "quotas": clean_quotas,
    }


def _grade_athenian_sortition_sim(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    candidates = item.get("candidates", {})
    quotas = item.get("quotas", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must map tribes to chosen citizen lists", "details": {}}

    for tribe, required_quota in quotas.items():
        chosen = submission.get(tribe, [])
        if not isinstance(chosen, list):
            return {"ok": False, "score": 0.0, "feedback": f"Selection for tribe '{tribe}' must be a list.", "details": {}}
        if len(chosen) != required_quota:
            return {
                "ok": False,
                "score": 0.0,
                "feedback": f"Tribe '{tribe}' required {required_quota} allocations but got {len(chosen)}.",
                "details": {"tribe": tribe},
            }
        pool = set(candidates.get(tribe, []))
        if len(set(chosen)) != len(chosen):
            return {"ok": False, "score": 0.0, "feedback": f"Duplicate allocation detected in tribe '{tribe}'.", "details": {}}
        if not set(chosen).issubset(pool):
            return {"ok": False, "score": 0.0, "feedback": f"Allocated citizens in tribe '{tribe}' not found in registered tribe kleroterion candidate pool.", "details": {}}

    return {
        "ok": True,
        "score": 1.0,
        "feedback": "Democratic sortition lottery verified: all tribal quotas and candidate pools satisfied without bias.",
        "details": {},
    }


NORMALIZERS = {
    "epigraphy_transcribe": _np_epigraphy_transcribe,
    "harris_matrix_build": _np_harris_matrix_build,
    "cursus_honorum_order": _np_cursus_honorum_order,
    "athenian_sortition_sim": _np_athenian_sortition_sim,
}

GRADERS = {
    "epigraphy_transcribe": _grade_epigraphy_transcribe,
    "harris_matrix_build": _grade_harris_matrix_build,
    "cursus_honorum_order": _grade_cursus_honorum_order,
    "athenian_sortition_sim": _grade_athenian_sortition_sim,
}
