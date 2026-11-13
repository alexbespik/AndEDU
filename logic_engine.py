"""
The deterministic logic engine for Philosophy: one JSON entry point over logic_formula, logic_forms,
logic_syllogism, logic_proof and logic_argmap. No model, no network: the same request always gets the same answer.

check(request) -> {"ok": true, "result": {...}} or {"ok": false, "error": {"code", "message", "pos"?}}; it never
raises on bad input. Used by scripts/logic_check.py; the practice types and MCP tools come later.
"""
from typing import Any, Callable, Dict

from logic_argmap import check_map
from logic_formula import (MAX_DEPTH, MAX_INPUT_LEN, MAX_PREMISES, MAX_VARS, LogicError, check_validity, classify,
                           equivalent, parse, parse_all, to_string, truth_table, variables)
from logic_forms import identify
from logic_proof import check_proof
from logic_syllogism import check_syllogism

GUIDE = f"""Logic engine ops (request {{"op": ..., ...}}):
- parse {{formula}}: canonical form, unicode form and letters. Notation: ~ & | -> <-> (also ¬ ∧ ∨ → ↔, not/and/or/
  implies/iff), ⊥ or _|_, letters start with a capital (P, Q2, Rain). -> groups right; <-> never chains.
- truth_table {{formulas: [...]}}: every row, all-true first.
- validity {{premises: [...], conclusion}}: valid, or the first row with true premises and a false conclusion.
- classify {{formula}}: tautology | contradiction | contingent.   equivalence {{a, b}}: equivalent, or a row where they differ.
- forms {{premises, conclusion}}: named valid forms and formal fallacies, matched by form (any letters, any premise order).
- syllogism {{form: "AAA-1"}} or {{major, minor, conclusion: {{type: A|E|I|O, subject, predicate}}}}, reading:
  boolean (default, 15 valid forms) | aristotelian (24, the extra 9 with needs_existence_of).
- proof {{premises?, goal?, rules?: derived|basic, lines: [{{formula, rule, cites, depth}}]}}: forall x: Calgary rules,
  a verdict per line. With a goal, PR lines must be among premises (none: a theorem).
- argmap {{map: {{claims, edges, main}}}}: unsupported, disconnected, circular, unanswered objections, invalid inferences.
Limits: {MAX_INPUT_LEN} characters per formula, {MAX_VARS} letters per table, nesting {MAX_DEPTH}, {MAX_PREMISES} premises.
Informal fallacies (straw man, ad hominem, slippery slope) depend on meaning: no script can judge them reliably, so
the engine never gives a verdict on them."""


def _parse(req):
    f = parse(req.get("formula"))
    return {"formula": to_string(f), "unicode": to_string(f, unicode=True), "letters": variables(f)}


def _table(req):
    return truth_table(parse_all(req.get("formulas"), "formulas"))


def _validity(req):
    premises = parse_all(req.get("premises", []), "premises")
    conclusion = parse(req.get("conclusion"))
    return {**check_validity(premises, conclusion), "premises": [to_string(p) for p in premises],
            "conclusion": to_string(conclusion)}


def _classify(req):
    f = parse(req.get("formula"))
    return {"formula": to_string(f), **classify(f)}


def _equivalence(req):
    return equivalent(parse(req.get("a")), parse(req.get("b")))


def _forms(req):
    return identify(parse_all(req.get("premises", []), "premises"), parse(req.get("conclusion")))


def _syllogism(req):
    spec = {k: req[k] for k in ("form", "major", "minor", "conclusion") if k in req}
    return check_syllogism(spec, req.get("reading", "boolean"))


OPS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "parse": _parse, "truth_table": _table, "validity": _validity, "classify": _classify,
    "equivalence": _equivalence, "forms": _forms, "syllogism": _syllogism,
    "proof": check_proof, "argmap": lambda req: check_map(req.get("map")),
    "guide": lambda req: {"guide": GUIDE},
}


def check(request: Any) -> Dict[str, Any]:
    if not isinstance(request, dict) or request.get("op") not in OPS:
        return {"ok": False, "error": {"code": "bad_op", "message": f"op is one of: {', '.join(OPS)}."}}
    try:
        return {"ok": True, "result": OPS[request["op"]](request)}
    except LogicError as e:
        return {"ok": False, "error": e.to_dict()}
    except (RecursionError, MemoryError):
        return {"ok": False, "error": {"code": "too_complex", "message": "The input is too complex to check."}}
    except Exception:  # a shape the checks above missed: still an answer, never a crash (tests cover the known shapes)
        return {"ok": False, "error": {"code": "bad_input", "message": "The engine could not read this input."}}
