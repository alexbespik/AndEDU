"""
Philosophy practice types: truth_table, validity, syllogism, proof_steps, argument_map, spot_parts, fallacy_id.
server.py merges NORMALIZERS into PRACTICE_NORMALIZERS; each function gets the raw item `p` and `base`
= {id, type, prompt, explanation, concept} and returns the cleaned item, or None to drop it.
Standard library and local logic modules only: this module never imports server.py.
Bodies live in src/practice/philosophy.jsx.
"""
from typing import Any, Dict, List, Optional

import logic_argmap
import logic_formula
import logic_proof
import logic_syllogism


def _s(v: Any, limit: int) -> str:
    return str(v if v is not None else "").strip()[:limit]


def _choice(options: Any, answer: Any) -> Optional[tuple[List[str], str]]:
    raw = [_s(o, 200) for o in options] if isinstance(options, list) else []
    if not raw or any(not o for o in raw) or len(set(raw)) != len(raw) or not (2 <= len(raw) <= 5):
        return None
    if isinstance(answer, int) and not isinstance(answer, bool) and 0 <= answer < len(raw):
        answer = raw[answer]
    answer = _s(answer, 200)
    return (raw, answer) if answer in raw else None


def _np_truth_table(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Truth table completion: student fills in truth values for propositional formula(s).
    Fields: `formulas` (1-3 propositional formula strings, using at most 4 variables).
    Ground truth truth-table rows and variable assignments are computed deterministically using logic_formula.
    Dropped if formulas cannot be parsed, variable count is 0 or exceeds 4, or formulas is not a list."""
    raw_forms = p.get("formulas")
    if isinstance(raw_forms, str):
        raw_forms = [raw_forms]
    if not isinstance(raw_forms, list) or not (1 <= len(raw_forms) <= 3):
        return None
    try:
        parsed = [logic_formula.parse(f) for f in raw_forms]
    except (logic_formula.LogicError, Exception):
        return None
    vars_set = logic_formula.variables(*parsed)
    if not (1 <= len(vars_set) <= 4):
        return None
    try:
        table = logic_formula.truth_table(parsed)
    except Exception:
        return None
    letters = table.get("vars") or table.get("letters") or []
    clean_rows = [
        {
            "assignment": r.get("values", {}),
            "values": r.get("results", []),
        }
        for r in table.get("rows", [])
    ]
    return {
        **base,
        "prompt": base.get("prompt") or "Complete the truth table for the given formula(s).",
        "formulas": [logic_formula.to_string(f) for f in parsed],
        "letters": letters,
        "vars": letters,
        "rows": clean_rows,
    }


def _np_validity(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Argument validity assessment: determine whether a propositional argument is valid or invalid.
    If invalid, identify the counterexample truth assignment that makes all premises true and conclusion false.
    Fields: `premises` (1-5 propositional formulas), `conclusion` (propositional formula).
    Ground truth validity and counterexamples are evaluated deterministically using logic_formula.check_validity.
    Dropped if parsing fails, premises or conclusion are missing, or total distinct variables exceed 6."""
    raw_prems = p.get("premises")
    if not isinstance(raw_prems, list) or not (1 <= len(raw_prems) <= 5):
        return None
    raw_concl = p.get("conclusion")
    if not isinstance(raw_concl, str) or not raw_concl.strip():
        return None
    try:
        parsed_prems = [logic_formula.parse(pr) for pr in raw_prems]
        parsed_concl = logic_formula.parse(raw_concl)
    except (logic_formula.LogicError, Exception):
        return None
    vars_set = logic_formula.variables(*parsed_prems, parsed_concl)
    if not (1 <= len(vars_set) <= 6):
        return None
    try:
        val = logic_formula.check_validity(parsed_prems, parsed_concl)
    except Exception:
        return None
    return {
        **base,
        "prompt": base.get("prompt") or "Determine whether the argument is valid or invalid. If invalid, identify the counterexample.",
        "premises": [logic_formula.to_string(pr) for pr in parsed_prems],
        "conclusion": logic_formula.to_string(parsed_concl),
        "valid": val["valid"],
        "counterexample": val["counterexample"],
    }


def _np_syllogism(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Categorical syllogism exercise: evaluate validity, mood, figure, and form name (e.g. Barbara) or rule violations.
    Fields: either `form` (\"AAA-1\" ... \"EAO-4\") OR `major`, `minor`, `conclusion` statement objects ({type: A|E|I|O, subject, predicate}).
    Optional `reading`: \"boolean\" (default, modern logic) or \"aristotelian\".
    Ground truth validity, formal violations, and existential requirements are determined deterministically using logic_syllogism.
    Dropped if the specification does not conform to standard syllogistic form."""
    reading = p.get("reading", "boolean")
    if reading not in logic_syllogism.READINGS:
        reading = "boolean"
    if p.get("form"):
        spec: Any = {"form": str(p["form"]).strip()}
    elif p.get("major") and p.get("minor") and p.get("conclusion"):
        spec = {"major": p["major"], "minor": p["minor"], "conclusion": p["conclusion"]}
    else:
        return None
    try:
        res = logic_syllogism.check_syllogism(spec, reading=reading)
    except (logic_formula.LogicError, Exception):
        return None
    item = {
        **base,
        "prompt": base.get("prompt") or "Evaluate the validity and form of this categorical syllogism.",
        "form": res["form"],
        "mood": res["mood"],
        "figure": res["figure"],
        "reading": res["reading"],
        "name": res["name"],
        "valid": res["valid"],
        "violations": res["violations"],
        "needs_existence_of": res["needs_existence_of"],
        "terms": res["terms"],
    }
    if isinstance(spec.get("major"), dict):
        item["major"] = spec["major"]
        item["minor"] = spec["minor"]
        item["conclusion"] = spec["conclusion"]
    return item


def _np_proof_steps(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fitch-style natural deduction proof steps: verify or complete a proof from premises to goal.
    Fields: `premises` (list of formulas, empty for theorems), `goal` (target formula string),
    `lines` (list of proof line objects: [{formula, rule, cites, depth}]), optional `rules` (\"derived\"|\"basic\").
    Ground truth line-by-line justification and goal discharge are evaluated deterministically using logic_proof.check_proof.
    Dropped if lines are missing, formulas fail to parse, or proof format is malformed."""
    raw_prems = p.get("premises", [])
    if isinstance(raw_prems, str):
        raw_prems = [raw_prems]
    if not isinstance(raw_prems, list):
        return None
    raw_goal = p.get("goal")
    raw_lines = p.get("lines")
    if not isinstance(raw_lines, list) or not (1 <= len(raw_lines) <= 50):
        return None
    rules = p.get("rules", "derived")
    if rules not in ("derived", "basic"):
        rules = "derived"
    try:
        chk = logic_proof.check_proof({"premises": raw_prems, "goal": raw_goal, "rules": rules, "lines": raw_lines})
    except (logic_formula.LogicError, Exception):
        return None
    proven = bool(chk.get("complete") and chk.get("valid"))
    return {
        **base,
        "prompt": base.get("prompt") or "Complete or verify the proof steps to reach the conclusion.",
        "premises": [logic_formula.to_string(logic_formula.parse(pr)) for pr in raw_prems if str(pr).strip()],
        "goal": logic_formula.to_string(logic_formula.parse(raw_goal)) if raw_goal else "",
        "rules": rules,
        "lines": raw_lines,
        "verdicts": chk["lines"],
        "proven": proven,
        "valid": chk.get("valid", False),
        "complete": chk.get("complete", False),
    }


def _np_argument_map(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Argument mapping analysis: examine structural relationships (support and attack edges) between claims.
    Fields: `map` ({claims: [{id, text, role?, kind?, formal?}], edges: [{from: [ids], to: id, type: supports|attacks}], main?: id}).
    Ground truth structural findings (circularity, unsupported claims, invalid inferences) are checked deterministically using logic_argmap.check_map.
    Dropped if map is empty, edges or claims are malformed, or claims exceed limits."""
    raw_map = p.get("map") if isinstance(p.get("map"), dict) else p
    if not isinstance(raw_map, dict):
        return None
    try:
        chk = logic_argmap.check_map(raw_map)
    except (logic_formula.LogicError, Exception):
        return None
    claims = [
        {"id": str(c["id"]), "text": _s(c.get("text"), 500),
         **({"role": c["role"]} if c.get("role") in logic_argmap.ROLES else {}),
         **({"formal": _s(c.get("formal"), 200)} if c.get("formal") else {})}
        for c in raw_map.get("claims", [])
        if isinstance(c, dict) and c.get("id")
    ]
    if not claims:
        return None
    edges = [
        {"from": list(e["from"]) if isinstance(e.get("from"), list) else [e.get("from")],
         "to": str(e["to"]), "type": e["type"]}
        for e in raw_map.get("edges", [])
        if isinstance(e, dict) and e.get("type") in ("supports", "attacks")
    ]
    main = raw_map.get("main")
    return {
        **base,
        "prompt": base.get("prompt") or "Analyze the argument map and identify structural weaknesses or valid inferences.",
        "map": {"claims": claims, "edges": edges, **({"main": main} if main else {})},
        "findings": chk["findings"],
        "notes": chk["notes"],
    }


def _np_spot_parts(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Argument structure identification: identify component parts of an argument or categorical proposition.
    Fields: `text` (passage or argument text), `options` (2-5 candidate parts/roles/terms), `answer` (the correct part/role, or its index),
    and optional `target` (e.g. \"Identify the main conclusion\", \"Identify the middle term\").
    Dropped if text is empty, options are invalid (<2 or >5 distinct), or answer is not in options."""
    text = _s(p.get("text"), 1500)
    if not text:
        return None
    ch = _choice(p.get("options"), p.get("answer"))
    if not ch:
        return None
    target = _s(p.get("target") or p.get("question") or "Identify the requested argument component.", 300)
    return {
        **base,
        "prompt": base.get("prompt") or target,
        "text": text,
        "target": target,
        "options": ch[0],
        "answer": ch[1],
    }


def _np_fallacy_id(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fallacy identification: identify formal or informal fallacies committed in an argument.
    Fields: `argument` (passage containing the fallacious reasoning), `options` (2-5 fallacy names),
    `answer` (correct fallacy name, or its index), optional `fallacy_type` (\"formal\"|\"informal\"), and optional `why` (explanation).
    Dropped if argument is empty, options are invalid (<2 or >5 distinct), or answer is not in options."""
    arg_text = _s(p.get("argument") or p.get("text"), 1500)
    if not arg_text:
        return None
    ch = _choice(p.get("options"), p.get("answer"))
    if not ch:
        return None
    ftype = p.get("fallacy_type")
    ftype = ftype if ftype in ("formal", "informal") else None
    why = _s(p.get("why"), 500)
    return {
        **base,
        "prompt": base.get("prompt") or "Identify the fallacy in this argument.",
        "argument": arg_text,
        "options": ch[0],
        "answer": ch[1],
        **({"fallacy_type": ftype} if ftype else {}),
        **({"why": why} if why else {}),
    }


NORMALIZERS = {
    "truth_table": _np_truth_table,
    "validity": _np_validity,
    "syllogism": _np_syllogism,
    "proof_steps": _np_proof_steps,
    "argument_map": _np_argument_map,
    "spot_parts": _np_spot_parts,
    "fallacy_id": _np_fallacy_id,
}
