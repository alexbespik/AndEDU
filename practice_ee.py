"""
Electrical Engineering & Circuit Analysis practice types:
- circuit_kcl_kvl: Nodal voltage and mesh current analysis with Kirchhoff's laws
- bode_plot_analyzer: Frequency response analysis, cutoff frequency, gain/phase margin
- boolean_gate_minimization: Karnaugh map & Boolean algebraic minimization
- opamp_gain_calc: Ideal and rail-saturated operational amplifier circuits

Exports NORMALIZERS, GRADERS, and SECRET_FIELDS. Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"expected", "solution", "minterms", "cutoff_rad_s", "gain_margin_db", "phase_margin_deg", "vout_expected", "gain_expected"}


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        val = float(v)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. circuit_kcl_kvl
# ---------------------------------------------------------------------------
def _np_circuit_kcl_kvl(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    nodes = p.get("nodes")
    target_variable = _s(p.get("target_variable") or p.get("target") or "V1", 50)
    solution = _num(p.get("solution") if p.get("solution") is not None else p.get("expected"))
    if solution is None:
        return None
    unit = _s(p.get("unit") or "V", 20)
    tol = _num(p.get("tolerance")) or 0.05

    return {
        **base,
        "circuit_diagram": _s(p.get("circuit_diagram") or p.get("svg"), 1000),
        "target_variable": target_variable,
        "unit": unit,
        "tolerance": tol,
        "solution": solution,
        "equations": [_s(eq, 200) for eq in p.get("equations", []) if _s(eq, 200)],
    }


def _grade_circuit_kcl_kvl(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = _num(item.get("solution"))
    tol = _num(item.get("tolerance")) or 0.05
    user_val = _num(submission.get("value") if isinstance(submission, dict) else submission)

    if expected is None or user_val is None:
        return {"ok": False, "score": 0.0, "feedback": "Submission must provide a numeric value.", "details": {}}

    diff = abs(user_val - expected)
    denom = max(1.0, abs(expected))
    rel_err = diff / denom

    ok = (diff <= tol or rel_err <= tol)
    score = 1.0 if ok else max(0.0, round(1.0 - (rel_err / (tol * 5.0)), 2))
    return {
        "ok": ok,
        "score": score,
        "feedback": f"Correct! {user_val} {item.get('unit', '')} matches circuit equations." if ok else f"Off target. Expected ~{expected} {item.get('unit', '')} (error: {round(rel_err * 100, 2)}%).",
        "details": {"submitted": user_val, "expected": expected, "relative_error": round(rel_err, 4)},
    }


# ---------------------------------------------------------------------------
# 2. bode_plot_analyzer
# ---------------------------------------------------------------------------
def _np_bode_plot_analyzer(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tf = _s(p.get("transfer_function") or p.get("tf"), 200)
    cutoff = _num(p.get("cutoff_rad_s") or p.get("wc"))
    gm = _num(p.get("gain_margin_db") or p.get("gm"))
    pm = _num(p.get("phase_margin_deg") or p.get("pm"))
    if cutoff is None and gm is None and pm is None:
        return None

    return {
        **base,
        "transfer_function": tf,
        "cutoff_rad_s": cutoff,
        "gain_margin_db": gm,
        "phase_margin_deg": pm,
        "tolerance": _num(p.get("tolerance")) or 0.1,
    }


def _grade_bode_plot_analyzer(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be an object with metrics.", "details": {}}

    tol = _num(item.get("tolerance")) or 0.1
    checks = []
    for key, name in [("cutoff_rad_s", "Cutoff frequency"), ("gain_margin_db", "Gain margin"), ("phase_margin_deg", "Phase margin")]:
        exp = _num(item.get(key))
        if exp is not None:
            sub_val = _num(submission.get(key))
            if sub_val is None:
                checks.append(False)
            else:
                rel = abs(sub_val - exp) / max(1.0, abs(exp))
                checks.append(rel <= tol)

    if not checks:
        return {"ok": False, "score": 0.0, "feedback": "No criteria to evaluate.", "details": {}}

    passed = sum(1 for c in checks if c)
    total = len(checks)
    score = round(passed / total, 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Bode metrics verified!" if ok else f"Some metrics mismatched ({passed}/{total} correct).",
        "details": {"passed": passed, "total": total},
    }


# ---------------------------------------------------------------------------
# 3. boolean_gate_minimization
# ---------------------------------------------------------------------------
def _np_boolean_gate_minimization(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    variables = [_s(v, 10) for v in p.get("variables", []) if _s(v, 10)]
    minterms = p.get("minterms")
    solution = _s(p.get("solution") or p.get("expected"), 200)
    if not variables or not solution:
        return None

    clean_minterms = []
    if isinstance(minterms, list):
        for m in minterms:
            mn = _num(m)
            if mn is not None:
                clean_minterms.append(int(mn))

    return {
        **base,
        "variables": variables,
        "minterms": clean_minterms,
        "solution": solution,
    }


def _grade_boolean_gate_minimization(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    sol = _s(item.get("solution")).replace(" ", "").upper()
    user_str = _s(submission.get("expression") if isinstance(submission, dict) else submission).replace(" ", "").upper()

    if not user_str:
        return {"ok": False, "score": 0.0, "feedback": "Empty expression submitted.", "details": {}}

    # Normalize canonical term order e.g. A'B + AB'
    terms_sol = set(sol.split("+"))
    terms_user = set(user_str.split("+"))

    ok = (terms_sol == terms_user)
    score = 1.0 if ok else (0.5 if len(terms_sol & terms_user) > 0 else 0.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Minimal Boolean expression correct!" if ok else f"Mismatch in minimized terms.",
        "details": {"submitted": user_str, "expected": sol},
    }


# ---------------------------------------------------------------------------
# 4. opamp_gain_calc
# ---------------------------------------------------------------------------
def _np_opamp_gain_calc(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    topology = _s(p.get("topology") or "inverting", 50).lower()
    r1 = _num(p.get("R1") or p.get("r1"))
    rf = _num(p.get("Rf") or p.get("rf"))
    vin = _num(p.get("Vin") or p.get("vin"))
    vsat_pos = _num(p.get("Vsat_pos")) or 15.0
    vsat_neg = _num(p.get("Vsat_neg")) or -15.0

    if r1 is None or rf is None or vin is None:
        return None

    # Calculate theoretical Vout with saturation rails
    if topology == "inverting":
        gain = -(rf / r1)
    elif topology == "non_inverting":
        gain = 1.0 + (rf / r1)
    else:
        gain = -(rf / r1)

    vout_ideal = gain * vin
    vout_actual = max(vsat_neg, min(vsat_pos, vout_ideal))

    return {
        **base,
        "topology": topology,
        "R1": r1,
        "Rf": rf,
        "Vin": vin,
        "Vsat_pos": vsat_pos,
        "Vsat_neg": vsat_neg,
        "gain_expected": round(gain, 4),
        "vout_expected": round(vout_actual, 4),
    }


def _grade_opamp_gain_calc(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected_vout = _num(item.get("vout_expected"))
    user_vout = _num(submission.get("vout") if isinstance(submission, dict) else submission)

    if expected_vout is None or user_vout is None:
        return {"ok": False, "score": 0.0, "feedback": "Must submit output voltage Vout.", "details": {}}

    diff = abs(user_vout - expected_vout)
    ok = (diff <= 0.05)
    score = 1.0 if ok else max(0.0, round(1.0 - (diff / 2.0), 2))
    return {
        "ok": ok,
        "score": score,
        "feedback": f"Accurate output voltage ({user_vout} V)." if ok else f"Vout off target. Expected {expected_vout} V (account for rails).",
        "details": {"submitted": user_vout, "expected": expected_vout},
    }


NORMALIZERS = {
    "circuit_kcl_kvl": _np_circuit_kcl_kvl,
    "bode_plot_analyzer": _np_bode_plot_analyzer,
    "boolean_gate_minimization": _np_boolean_gate_minimization,
    "opamp_gain_calc": _np_opamp_gain_calc,
}

GRADERS = {
    "circuit_kcl_kvl": _grade_circuit_kcl_kvl,
    "bode_plot_analyzer": _grade_bode_plot_analyzer,
    "boolean_gate_minimization": _grade_boolean_gate_minimization,
    "opamp_gain_calc": _grade_opamp_gain_calc,
}
