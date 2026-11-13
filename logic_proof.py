"""
Natural-deduction proof checking (logic engine), Fitch style, with the rules of forall x: Calgary (P. D. Magnus,
Tim Button, Richard Zach et al., Fall 2025 edition, CC BY 4.0; quick reference in its appendix C).

Basic rules: PR (premise), AS (assumption, opens a subproof), R, &I, &E, |I, |E, ->I, ->E, <->I, <->E, ~I, ~E, X, IP.
Derived rules, allowed unless rules = "basic": DS, MT, DNE, LEM, DeM. Common other names work too (MP = ->E,
CP = ->I, symbols ∧ ∨ → ↔ ¬ for & | -> <-> ~).

A proof is {"premises"?: [...], "goal"?: "...", "rules"?: "derived" | "basic",
"lines": [{"formula": "P -> Q", "rule": "->I", "cites": ["2-4"], "depth": 0}, ...]}. Lines are numbered from 1.
`depth` is how many subproofs the line is inside (default: an AS line one deeper than the line before, any other
line the same); an AS line opens a subproof (and closes any finished one at its depth). With a goal, PR lines must
be among `premises` (none listed: a theorem, proved from nothing). A cite is a line number, or a subproof "i-j" (also [i, j]) from its assumption i to its last line j.
A line may cite only what is still in scope: earlier lines not inside a subproof that has closed, and closed
subproofs whose enclosing subproofs are still open. Every line gets its own verdict, so one mistake does not hide
the rest; a line citing a wrong line is marked depends_on_error.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from logic_formula import BOT, Formula, LogicError, parse, to_string

MAX_PROOF_LINES = 200
MAX_PROOF_DEPTH = 20
BASIC = {"PR", "AS", "R", "&I", "&E", "|I", "|E", "->I", "->E", "<->I", "<->E", "~I", "~E", "X", "IP"}
DERIVED = {"DS", "MT", "DNE", "LEM", "DEM"}
_ALIASES = {
    "PREMISE": "PR", "P": "PR", "PREM": "PR", "ASSUMPTION": "AS", "ASSUME": "AS", "HYP": "AS", "A": "AS",
    "REIT": "R", "REITERATION": "R", "MP": "->E", "CP": "->I", "RAA": "~I", "EXPLOSION": "X", "EFQ": "X",
    "DN": "DNE", "ANDI": "&I", "ANDE": "&E", "ORI": "|I", "ORE": "|E", "NOTI": "~I", "NOTE": "~E",
}
_SPAN = re.compile(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$")


def _rule_key(raw: Any) -> str:
    text = str(raw or "").upper().replace(" ", "")
    for a, b in (("∧", "&"), ("∨", "|"), ("↔", "<->"), ("→", "->"), ("¬", "~"), ("⊃", "->"), ("≡", "<->")):
        text = text.replace(a, b)
    return _ALIASES.get(text, text)


def _cites(raw: Any) -> Tuple[List[int], List[Tuple[int, int]]]:
    """Line numbers and subproof spans, in the order given."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        raw = [raw]
    lines, spans = [], []
    for c in raw[:10]:
        if isinstance(c, bool):
            raise LogicError("bad_cite", "A cite is a line number or a span like 3-5.")
        if isinstance(c, int):
            lines.append(c)
        elif isinstance(c, list) and len(c) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in c):
            spans.append((c[0], c[1]))
        elif isinstance(c, str) and len(c) > 12:
            raise LogicError("bad_cite", "A cite is a line number or a span like 3-5.")
        elif isinstance(c, str) and c.strip().isdigit():
            lines.append(int(c))
        elif isinstance(c, str) and _SPAN.match(c):
            m = _SPAN.match(c)
            spans.append((int(m.group(1)), int(m.group(2))))
        else:
            raise LogicError("bad_cite", f"'{c}' is not a line number or a span like 3-5.")
    return lines, spans


class _Wrong(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _need(lines, spans, n_lines, n_spans, rule):
    if len(lines) != n_lines or len(spans) != n_spans:
        parts = [f"{n_lines} line{'s' if n_lines != 1 else ''}"] if n_lines else []
        if n_spans:
            parts.append(f"{n_spans} subproof{'s' if n_spans != 1 else ''}")
        raise _Wrong("bad_cites", f"{rule} cites {' and '.join(parts) or 'nothing'}.")


def _either(pairs, test):
    """True when test(x, y) holds for the cited items in either order."""
    a, b = pairs
    return test(a, b) or test(b, a)


def _check_rule(rule: str, phi: Formula, lines: List[Formula], spans: List[Tuple[Formula, Formula]]) -> None:
    """Raises _Wrong when phi does not follow by `rule` from the cited formulas (lines) and subproofs (first, last)."""
    def bad(msg):
        raise _Wrong("wrong_form", msg)
    if rule == "R":
        _need(lines, spans, 1, 0, rule)
        if lines[0] != phi:
            bad("R repeats a line exactly.")
    elif rule == "&I":
        _need(lines, spans, 2, 0, rule)
        if not (phi[0] == "and" and _either(lines, lambda a, b: (phi[1], phi[2]) == (a, b))):
            bad("&I joins the two cited lines: A, B give A & B.")
    elif rule == "&E":
        _need(lines, spans, 1, 0, rule)
        c = lines[0]
        if not (c[0] == "and" and phi in (c[1], c[2])):
            bad("&E takes one conjunct of a cited A & B.")
    elif rule == "|I":
        _need(lines, spans, 1, 0, rule)
        if not (phi[0] == "or" and lines[0] in (phi[1], phi[2])):
            bad("|I adds a disjunct to the cited line: A gives A | B or B | A.")
    elif rule == "|E":
        _need(lines, spans, 1, 2, rule)
        d = lines[0]
        if d[0] != "or":
            bad("|E cites a disjunction A | B first.")
        ok = _either(spans, lambda s1, s2: s1[0] == d[1] and s2[0] == d[2] and s1[1] == phi and s2[1] == phi)
        if not ok:
            bad("|E needs a subproof from each disjunct, both ending in the line's formula.")
    elif rule == "->I":
        _need(lines, spans, 0, 1, rule)
        first, last = spans[0]
        if phi != ("imp", first, last):
            bad("->I: a subproof from A to B gives A -> B.")
    elif rule == "->E":
        _need(lines, spans, 2, 0, rule)
        if not _either(lines, lambda c, a: c == ("imp", a, phi)):
            bad("->E: A -> B and A give B.")
    elif rule == "<->I":
        _need(lines, spans, 0, 2, rule)
        if not (phi[0] == "iff" and _either(spans, lambda s1, s2: s1 == (phi[1], phi[2]) and s2 == (phi[2], phi[1]))):
            bad("<->I: subproofs from A to B and from B to A give A <-> B.")
    elif rule == "<->E":
        _need(lines, spans, 2, 0, rule)
        if not _either(lines, lambda c, a: c in (("iff", a, phi), ("iff", phi, a))):
            bad("<->E: A <-> B and one side give the other side.")
    elif rule == "~I":
        _need(lines, spans, 0, 1, rule)
        first, last = spans[0]
        if last != BOT or phi != ("not", first):
            bad("~I: a subproof from A to ⊥ gives ~A.")
    elif rule == "~E":
        _need(lines, spans, 2, 0, rule)
        if phi != BOT or not _either(lines, lambda n, a: n == ("not", a)):
            bad("~E: ~A and A give ⊥.")
    elif rule == "X":
        _need(lines, spans, 1, 0, rule)
        if lines[0] != BOT:
            bad("X: from ⊥, any formula.")
    elif rule == "IP":
        _need(lines, spans, 0, 1, rule)
        first, last = spans[0]
        if last != BOT or first != ("not", phi):
            bad("IP: a subproof from ~A to ⊥ gives A.")
    elif rule == "DS":
        _need(lines, spans, 2, 0, rule)
        if not _either(lines, lambda d, n: d[0] == "or" and ((n == ("not", d[1]) and phi == d[2]) or
                                                             (n == ("not", d[2]) and phi == d[1]))):
            bad("DS: A | B and ~A give B (or ~B gives A).")
    elif rule == "MT":
        _need(lines, spans, 2, 0, rule)
        if not (phi[0] == "not" and _either(lines, lambda c, n: c == ("imp", phi[1], n[1]) if n[0] == "not" else False)):
            bad("MT: A -> B and ~B give ~A.")
    elif rule == "DNE":
        _need(lines, spans, 1, 0, rule)
        if lines[0] != ("not", ("not", phi)):
            bad("DNE: ~~A gives A.")
    elif rule == "LEM":
        _need(lines, spans, 0, 2, rule)
        if not _either(spans, lambda s1, s2: s2[0] == ("not", s1[0]) and s1[1] == phi and s2[1] == phi):
            bad("LEM: subproofs from A and from ~A, both ending in B, give B.")
    elif rule == "DEM":
        _need(lines, spans, 1, 0, rule)
        if not _de_morgan(lines[0], phi):
            bad("DeM swaps ~(A | B) with ~A & ~B, or ~(A & B) with ~A | ~B.")
    else:
        raise _Wrong("unknown_rule", "Unknown rule.")


def _de_morgan(a: Formula, b: Formula) -> bool:
    def pair(x, y):
        if x[0] == "not" and x[1][0] in ("and", "or"):
            inner = x[1]
            flip = "or" if inner[0] == "and" else "and"
            return y == (flip, ("not", inner[1]), ("not", inner[2]))
        return False
    return pair(a, b) or pair(b, a)


def check_proof(proof: Any) -> Dict[str, Any]:
    if not isinstance(proof, dict):
        raise LogicError("bad_proof", "A proof is an object with a list of lines.")
    raw_lines = proof.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise LogicError("bad_proof", "A proof needs a list of lines.")
    if len(raw_lines) > MAX_PROOF_LINES:
        raise LogicError("too_long", f"A proof may have at most {MAX_PROOF_LINES} lines.")
    rules_mode = proof.get("rules", "derived")
    if rules_mode not in ("derived", "basic"):
        raise LogicError("bad_rules", "rules is \"derived\" (the default) or \"basic\".")
    allowed = BASIC | (DERIVED if rules_mode == "derived" else set())
    given = [parse(p) for p in proof.get("premises") or []] if isinstance(proof.get("premises") or [], list) else None
    if given is None:
        raise LogicError("bad_proof", "premises must be a list of formulas.")
    goal = parse(proof["goal"]) if proof.get("goal") not in (None, "") else None

    # pass 1: structure. path[n] = the open subproofs (their assumption lines) around line n.
    n_lines = len(raw_lines)
    formulas: List[Optional[Formula]] = [None] * (n_lines + 1)
    path: List[Tuple[int, ...]] = [()] * (n_lines + 1)
    results: List[Dict[str, Any]] = [{} for _ in range(n_lines + 1)]
    sub_end: Dict[int, int] = {}  # assumption line -> last line of its subproof
    stack: List[int] = []
    seen_body = False
    for n, raw in enumerate(raw_lines, start=1):
        res = results[n]
        res.update(n=n, ok=True)
        if not isinstance(raw, dict):
            res.update(ok=False, code="bad_line", message="Each line is an object with formula, rule and cites.")
            path[n] = tuple(stack)
            continue
        try:
            formulas[n] = parse(raw.get("formula"))
        except LogicError as e:
            res.update(ok=False, code="parse_error", message=e.message, pos=e.pos)
        rule = _rule_key(raw.get("rule"))
        res["rule"] = rule
        depth = raw.get("depth", len(stack) + 1 if rule == "AS" else len(stack))  # AS nests by default
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0 or depth > MAX_PROOF_DEPTH:
            res.update(ok=False, code="bad_depth", message=f"depth is a whole number from 0 to {MAX_PROOF_DEPTH}.")
            depth = len(stack)
        if rule == "AS":
            if depth < 1 or depth > len(stack) + 1:
                res.update(ok=False, code="bad_depth",
                           message="An assumption opens a subproof one level deeper than the line before it (or starts a new one at the same level).")
                depth = len(stack) + 1
            del stack[depth - 1:]
            stack.append(n)
            seen_body = True
        else:
            if depth > len(stack):
                res.update(ok=False, code="bad_depth", message="Only an assumption (AS) can start a deeper subproof.")
                depth = len(stack)
            del stack[depth:]
            if rule == "PR":
                if stack or seen_body:
                    res.update(ok=False, code="premise_position", message="Premises come first, outside any subproof.")
            else:
                seen_body = True
        path[n] = tuple(stack)
        for a in stack:
            sub_end[a] = n

    # pass 2: rules and citations
    for n, raw in enumerate(raw_lines, start=1):
        res = results[n]
        if not res["ok"] or not isinstance(raw, dict):
            continue
        rule, phi = res["rule"], formulas[n]
        try:
            if rule not in BASIC | DERIVED:
                raise _Wrong("unknown_rule", f"Unknown rule '{raw.get('rule')}'.")
            if rule not in allowed:
                raise _Wrong("rule_not_allowed", f"{rule} is a derived rule; this exercise allows only the basic rules.")
            try:
                cite_lines, cite_spans = _cites(raw.get("cites"))
            except LogicError as e:
                raise _Wrong(e.code, e.message)
            if rule in ("PR", "AS"):
                if cite_lines or cite_spans:
                    raise _Wrong("bad_cites", f"{rule} cites nothing.")
                # with a goal, premises are only the listed ones (none listed: a theorem, proved from nothing)
                if rule == "PR" and (given or goal is not None) and phi not in given:
                    raise _Wrong("not_a_premise", "This is not one of the argument's premises."
                                 if given else "This proof has no premises: start with an assumption (AS).")
                continue
            here = path[n]
            line_formulas, span_formulas = [], []
            for i in cite_lines:
                if not 1 <= i < n:
                    raise _Wrong("bad_cites", f"Line {i} does not come before line {n}.")
                if here[:len(path[i])] != path[i]:
                    raise _Wrong("not_in_scope", f"Line {i} is inside a subproof that has closed.")
                if not results[i]["ok"]:
                    raise _Wrong("depends_on_error", f"Line {i} has a mistake.")
                line_formulas.append(formulas[i])
            for a, b in cite_spans:
                if a in here:
                    raise _Wrong("not_in_scope", f"The subproof from line {a} is still open at line {n}: close it first.")
                if a not in sub_end or sub_end[a] != b or path[b] != path[a]:
                    raise _Wrong("bad_cites", f"{a}-{b} is not a whole subproof (from its assumption to its last line).")
                if b >= n:
                    raise _Wrong("not_in_scope", f"Subproof {a}-{b} must be closed before line {n}.")
                outer = path[a][:-1]
                if here[:len(outer)] != outer:
                    raise _Wrong("not_in_scope", f"Subproof {a}-{b} is inside a subproof that has closed.")
                if not (results[a]["ok"] and results[b]["ok"]):
                    raise _Wrong("depends_on_error", f"Subproof {a}-{b} has a mistake.")
                span_formulas.append((formulas[a], formulas[b]))
            _check_rule(rule, phi, line_formulas, span_formulas)
        except _Wrong as w:
            res.update(ok=False, code=w.code, message=w.message)

    out_lines = [results[n] for n in range(1, n_lines + 1)]
    valid = all(r["ok"] for r in out_lines)
    last = n_lines
    reached = goal is not None and path[last] == () and formulas[last] == goal
    complete = valid and reached
    out = {"valid": valid, "complete": complete, "rules": rules_mode, "lines": out_lines}
    if goal is not None:
        out["goal"] = to_string(goal)
        if not reached:
            out["goal_message"] = "The last line, outside every subproof, must be the goal."
    return out
