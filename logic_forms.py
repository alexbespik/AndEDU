"""
Named argument forms (logic engine): modus ponens, modus tollens... and the formal fallacies (affirming the
consequent, denying the antecedent...), recognised by logical form, not wording: a form's letters A, B, C, D stand for
any sub-formula, so "Rain -> Wet, Wet, so Rain" and "(P & Q) -> R, R, so P & Q" are both affirming the consequent.
Premise order does not matter. Informal fallacies (straw man, ad hominem...) depend on meaning and are not here.
"""
from itertools import permutations
from typing import Any, Dict, List, Optional, Sequence

from logic_formula import Formula, check_validity, parse, to_string

# (id, name, kind, premises, conclusion); one id may have several shapes (both disjuncts, conjoined or split premises)
_FORMS = [
    ("modus_ponens", "Modus ponens", "valid", ["A -> B", "A"], "B"),
    ("modus_tollens", "Modus tollens", "valid", ["A -> B", "~B"], "~A"),
    ("hypothetical_syllogism", "Hypothetical syllogism", "valid", ["A -> B", "B -> C"], "A -> C"),
    ("disjunctive_syllogism", "Disjunctive syllogism", "valid", ["A | B", "~A"], "B"),
    ("disjunctive_syllogism", "Disjunctive syllogism", "valid", ["A | B", "~B"], "A"),
    ("constructive_dilemma", "Constructive dilemma", "valid", ["A -> B", "C -> D", "A | C"], "B | D"),
    ("constructive_dilemma", "Constructive dilemma", "valid", ["(A -> B) & (C -> D)", "A | C"], "B | D"),
    ("destructive_dilemma", "Destructive dilemma", "valid", ["A -> B", "C -> D", "~B | ~D"], "~A | ~C"),
    ("destructive_dilemma", "Destructive dilemma", "valid", ["(A -> B) & (C -> D)", "~B | ~D"], "~A | ~C"),
    ("simplification", "Simplification", "valid", ["A & B"], "A"),
    ("simplification", "Simplification", "valid", ["A & B"], "B"),
    ("conjunction", "Conjunction", "valid", ["A", "B"], "A & B"),
    ("addition", "Addition", "valid", ["A"], "A | B"),
    ("addition", "Addition", "valid", ["A"], "B | A"),
    ("contraposition", "Contraposition", "valid", ["A -> B"], "~B -> ~A"),
    ("affirming_the_consequent", "Affirming the consequent", "fallacy", ["A -> B", "B"], "A"),
    ("denying_the_antecedent", "Denying the antecedent", "fallacy", ["A -> B", "~A"], "~B"),
    ("affirming_a_disjunct", "Affirming a disjunct", "fallacy", ["A | B", "A"], "~B"),
    ("affirming_a_disjunct", "Affirming a disjunct", "fallacy", ["A | B", "B"], "~A"),
    ("converting_a_conditional", "Converting a conditional", "fallacy", ["A -> B"], "B -> A"),
    ("negating_antecedent_and_consequent", "Negating antecedent and consequent", "fallacy", ["A -> B"], "~A -> ~B"),
]
FORMS = [(fid, name, kind, [parse(p) for p in prem], parse(concl)) for fid, name, kind, prem, concl in _FORMS]


def _unify(pattern: Formula, f: Formula, binding: Dict[str, Formula]) -> bool:
    """Matches a form's pattern against a formula, binding each pattern letter to one sub-formula (consistently)."""
    stack = [(pattern, f)]
    while stack:
        p, g = stack.pop()
        if p[0] == "var":
            bound = binding.get(p[1])
            if bound is None:
                binding[p[1]] = g
            elif bound != g:
                return False
        elif p[0] != g[0]:
            return False
        else:
            stack.extend(zip(p[1:], g[1:]))
    return True


def _match(form_premises, form_conclusion, premises, conclusion) -> Optional[Dict[str, Formula]]:
    if len(form_premises) != len(premises):
        return None
    for order in permutations(premises):
        binding: Dict[str, Formula] = {}
        if all(_unify(p, f, binding) for p, f in zip(form_premises, order)) and _unify(form_conclusion, conclusion, binding):
            return binding
    return None


def identify(premises: Sequence[Formula], conclusion: Formula) -> Dict[str, Any]:
    """Every named form the argument has (by form, in any premise order), and its truth-table verdict."""
    verdict = check_validity(premises, conclusion)
    matches: List[Dict[str, Any]] = []
    seen = set()
    if len(premises) <= 4:  # the longest form has 3 premises; permutations stay small
        for fid, name, kind, prem, concl in FORMS:
            if fid in seen:
                continue
            binding = _match(prem, concl, list(premises), conclusion)
            if binding is not None:
                seen.add(fid)
                match = {"id": fid, "name": name, "kind": kind,
                         "binding": {k: to_string(v) for k, v in sorted(binding.items())}}
                if kind == "fallacy" and verdict["valid"]:
                    match["note"] = "The form is a fallacy, but this instance happens to be valid (its parts overlap)."
                matches.append(match)
    return {"matches": matches, "valid": verdict["valid"], "counterexample": verdict["counterexample"]}
