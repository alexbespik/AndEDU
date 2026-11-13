"""
Categorical syllogisms (logic engine): mood and figure, the traditional rules with the one that breaks named, and the
form's name (Barbara, Celarent...).

Statements: A "All S are P", E "No S are P", I "Some S are P", O "Some S are not P". S is the minor term (subject of
the conclusion), P the major term (its predicate), M the middle term (in both premises, not in the conclusion).
Figures (major premise, minor premise): 1 M-P, S-M · 2 P-M, S-M · 3 M-P, M-S · 4 P-M, M-S.

Two readings of universal statements:
- boolean (the default, modern logic): "All S are P" does not say there are any S. 15 forms are valid; two universal
  premises never give a particular conclusion (the existential fallacy).
- aristotelian: every term names something that exists. 24 forms are valid; the 9 extra ones are reported with
  needs_existence_of, the term whose existence the form relies on.
"""
import re
from typing import Any, Dict, List, Tuple

from logic_formula import LogicError

TYPES = "AEIO"
READINGS = ("boolean", "aristotelian")
_FIGURES = {1: (("M", "P"), ("S", "M")), 2: (("P", "M"), ("S", "M")),
            3: (("M", "P"), ("M", "S")), 4: (("P", "M"), ("M", "S"))}
# which positions a statement distributes: (subject, predicate)
_DISTRIBUTES = {"A": (True, False), "E": (True, True), "I": (False, False), "O": (False, True)}
# (mood, figure) -> (name, term needed to exist; None when valid under the boolean reading)
NAMES: Dict[Tuple[str, int], Tuple[str, Any]] = {
    ("AAA", 1): ("Barbara", None), ("EAE", 1): ("Celarent", None), ("AII", 1): ("Darii", None),
    ("EIO", 1): ("Ferio", None), ("AAI", 1): ("Barbari", "S"), ("EAO", 1): ("Celaront", "S"),
    ("EAE", 2): ("Cesare", None), ("AEE", 2): ("Camestres", None), ("EIO", 2): ("Festino", None),
    ("AOO", 2): ("Baroco", None), ("EAO", 2): ("Cesaro", "S"), ("AEO", 2): ("Camestros", "S"),
    ("AII", 3): ("Datisi", None), ("IAI", 3): ("Disamis", None), ("OAO", 3): ("Bocardo", None),
    ("EIO", 3): ("Ferison", None), ("AAI", 3): ("Darapti", "M"), ("EAO", 3): ("Felapton", "M"),
    ("AEE", 4): ("Calemes", None), ("IAI", 4): ("Dimatis", None), ("EIO", 4): ("Fresison", None),
    ("AAI", 4): ("Bamalip", "P"), ("AEO", 4): ("Calemos", "S"), ("EAO", 4): ("Fesapo", "M"),
}
_MESSAGES = {
    "undistributed_middle": "The middle term is not distributed in either premise.",
    "illicit_major": "The major term is distributed in the conclusion but not in the major premise.",
    "illicit_minor": "The minor term is distributed in the conclusion but not in the minor premise.",
    "exclusive_premises": "Both premises are negative.",
    "affirmative_from_negative": "A premise is negative, so the conclusion must be negative too.",
    "negative_from_affirmative": "Both premises are affirmative, so the conclusion cannot be negative.",
    "existential_fallacy": "Two universal premises cannot give a particular conclusion unless the terms are assumed to exist.",
}
_FORM_RE = re.compile(r"^\s*([AEIOaeio]{3})\s*-?\s*([1-4])\s*$")
_ROLE = {"S": "minor", "P": "major", "M": "middle"}


def _statement(raw: Any, where: str) -> Tuple[str, str, str]:
    if not isinstance(raw, dict):
        raise LogicError("bad_statement", f"The {where} must be an object {{type, subject, predicate}}.")
    kind = str(raw.get("type", "")).upper()
    subject, predicate = raw.get("subject"), raw.get("predicate")
    if kind not in TYPES:
        raise LogicError("bad_statement", f"The {where}'s type must be A, E, I or O.")
    for term in (subject, predicate):
        if not isinstance(term, str) or not term.strip() or len(term) > 80:
            raise LogicError("bad_statement", f"The {where} needs a subject and a predicate (up to 80 characters).")
    subject, predicate = " ".join(subject.split()), " ".join(predicate.split())
    if subject.casefold() == predicate.casefold():
        raise LogicError("bad_statement", f"The {where} has the same term twice.")
    return kind, subject, predicate


def parse_spec(spec: Any) -> Dict[str, Any]:
    """{"form": "AAA-1"} (terms named S, P, M) or {"major", "minor", "conclusion"} statements with real terms.
    Returns mood, figure and the terms; LogicError when it is not a standard-form syllogism."""
    if isinstance(spec, str):
        spec = {"form": spec}
    if not isinstance(spec, dict):
        raise LogicError("bad_syllogism", "Give a form such as \"AAA-1\" or the three statements.")
    if spec.get("form") is not None:
        m = _FORM_RE.match(str(spec["form"]))
        if not m:
            raise LogicError("bad_form", "A form is a mood and a figure, such as AAA-1 or EIO-3.")
        return {"mood": m.group(1).upper(), "figure": int(m.group(2)), "terms": {"S": "S", "P": "P", "M": "M"}}
    major = _statement(spec.get("major"), "major premise")
    minor = _statement(spec.get("minor"), "minor premise")
    concl = _statement(spec.get("conclusion"), "conclusion")
    key = lambda t: t.casefold()  # noqa: E731
    s, p = concl[1], concl[2]
    terms = {key(major[1]), key(major[2]), key(minor[1]), key(minor[2]), key(s), key(p)}
    if len(terms) != 3:
        raise LogicError("four_terms", f"A syllogism has exactly three terms; these statements use {len(terms)}.")
    if key(p) not in (key(major[1]), key(major[2])) and key(p) in (key(minor[1]), key(minor[2])):
        major, minor = minor, major  # the premise with the major term is the major premise
    major_terms, minor_terms = {key(major[1]), key(major[2])}, {key(minor[1]), key(minor[2])}
    if key(p) not in major_terms or key(s) not in minor_terms or key(s) in major_terms or key(p) in minor_terms:
        raise LogicError("bad_syllogism", "The major premise must hold the conclusion's predicate and the middle term; "
                                          "the minor premise its subject and the middle term.")
    middle = next(t for t in (major[1], major[2]) if key(t) != key(p))
    letter = lambda t: "S" if key(t) == key(s) else "P" if key(t) == key(p) else "M"  # noqa: E731
    shape = ((letter(major[1]), letter(major[2])), (letter(minor[1]), letter(minor[2])))
    figure = next(f for f, sh in _FIGURES.items() if sh == shape)
    return {"mood": major[0] + minor[0] + concl[0], "figure": figure, "terms": {"S": s, "P": p, "M": middle}}


def violations(mood: str, figure: int, reading: str = "boolean") -> List[str]:
    """The rule codes this mood and figure break (empty: valid under that reading)."""
    (maj_s, maj_p), (min_s, min_p) = _FIGURES[figure]
    dist = {}  # term -> distributed in (major, minor, conclusion)

    def mark(kind, subj, pred, slot):
        ds, dp = _DISTRIBUTES[kind]
        dist.setdefault(subj, [False, False, False])[slot] |= ds
        dist.setdefault(pred, [False, False, False])[slot] |= dp
    mark(mood[0], maj_s, maj_p, 0)
    mark(mood[1], min_s, min_p, 1)
    mark(mood[2], "S", "P", 2)
    negative = [k in "EO" for k in mood]
    out = []
    if not (dist["M"][0] or dist["M"][1]):
        out.append("undistributed_middle")
    if dist["P"][2] and not dist["P"][0]:
        out.append("illicit_major")
    if dist["S"][2] and not dist["S"][1]:
        out.append("illicit_minor")
    if negative[0] and negative[1]:
        out.append("exclusive_premises")
    if (negative[0] or negative[1]) and not negative[2]:
        out.append("affirmative_from_negative")
    if not (negative[0] or negative[1]) and negative[2]:
        out.append("negative_from_affirmative")
    if reading == "boolean" and mood[0] in "AE" and mood[1] in "AE" and mood[2] in "IO":
        out.append("existential_fallacy")
    return out


def check_syllogism(spec: Any, reading: str = "boolean") -> Dict[str, Any]:
    if reading not in READINGS:
        raise LogicError("bad_reading", "The reading is boolean or aristotelian.")
    parsed = parse_spec(spec)
    mood, figure, terms = parsed["mood"], parsed["figure"], parsed["terms"]
    broken = violations(mood, figure, reading)
    name, needs = NAMES.get((mood, figure), (None, None))
    valid = not broken
    return {
        "form": f"{mood}-{figure}", "mood": mood, "figure": figure, "reading": reading,
        "name": name, "valid": valid,
        "violations": [{"rule": r, "message": _MESSAGES[r]} for r in broken],
        "needs_existence_of": [{"term": terms[needs], "role": _ROLE[needs]}] if valid and needs else [],
        "terms": {"minor": terms["S"], "major": terms["P"], "middle": terms["M"]},
    }
