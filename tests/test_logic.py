"""The deterministic logic engine (logic_*.py): parser, truth tables, forms, syllogisms, proofs, argument maps, CLI."""
import json
import random
import subprocess
import sys
import time
import unittest
from itertools import product
from pathlib import Path

import logic_engine
import logic_proof
from logic_argmap import check_map
from logic_formula import (MAX_DEPTH, MAX_INPUT_LEN, LogicError, check_validity, classify, equivalent, parse,
                           to_string, truth_table)
from logic_forms import FORMS, identify
from logic_syllogism import NAMES, check_syllogism, violations

ROOT = Path(__file__).resolve().parent.parent


def P(text):
    return parse(text)


class Parser(unittest.TestCase):
    def test_precedence_and_grouping(self):
        self.assertEqual(P("~P & Q | R -> S"), P("(((~P) & Q) | R) -> S"))
        self.assertEqual(P("A -> B -> C"), P("A -> (B -> C)"))
        self.assertEqual(P("A & B & C"), P("(A & B) & C"))
        self.assertEqual(P("A | B & C"), P("A | (B & C)"))
        self.assertEqual(P("~~A"), ("not", ("not", ("var", "A"))))

    def test_notations_agree(self):
        same = P("~P & Q -> R <-> S")
        for text in ("¬P ∧ Q → R ↔ S", "!P /\\ Q => R <=> S", "not P and Q implies R iff S", "NOT P AND Q IMPLIES R IFF S"):
            self.assertEqual(P(text), same, text)
        self.assertEqual(P("A | B"), P("A \\/ B"))
        self.assertEqual(P("⊥"), P("_|_"))
        self.assertEqual(P("Rain -> Wet_2"), ("imp", ("var", "Rain"), ("var", "Wet_2")))

    def test_errors_carry_a_position(self):
        cases = {"(P & Q": ("unbalanced", 0), "P & Q)": ("unbalanced", 5), "P &": ("unexpected_end", 3),
                 "P Q": ("missing_connective", 2), "A <-> B <-> C": ("chained_iff", 8), "& P": ("missing_operand", 0),
                 "p -> q": ("bad_letter", 0), "if P then Q": ("unsupported_word", 0), "P $ Q": ("bad_character", 2),
                 "": ("empty", None)}
        for text, (code, pos) in cases.items():
            with self.subTest(text=text):
                with self.assertRaises(LogicError) as e:
                    P(text)
                self.assertEqual((e.exception.code, e.exception.pos), (code, pos))

    def test_limits(self):
        with self.assertRaises(LogicError) as e:
            P("P & " * 200 + "P")
        self.assertEqual(e.exception.code, "too_long")
        with self.assertRaises(LogicError) as e:
            P("(" * (MAX_DEPTH + 5) + "P" + ")" * (MAX_DEPTH + 5))
        self.assertEqual(e.exception.code, "too_deep")
        self.assertLessEqual(len("(" * (MAX_DEPTH + 5) + "P" + ")" * (MAX_DEPTH + 5)), MAX_INPUT_LEN)
        nine = " & ".join("ABCDEFGHI")
        with self.assertRaises(LogicError) as e:
            truth_table([P(nine)])
        self.assertEqual(e.exception.code, "too_many_letters")

    def test_round_trip_fuzz(self):
        rng = random.Random(20261113)

        def gen(d):
            if d == 0 or rng.random() < 0.25:
                return rng.choice([("var", "P"), ("var", "Q"), ("var", "R"), ("bot",)])
            op = rng.choice(["not", "and", "or", "imp", "iff"])
            return ("not", gen(d - 1)) if op == "not" else (op, gen(d - 1), gen(d - 1))
        for _ in range(500):
            f = gen(6)
            self.assertEqual(P(to_string(f)), f)
            self.assertEqual(P(to_string(f, unicode=True)), f)


class Truth(unittest.TestCase):
    def test_table_order(self):
        t = truth_table([P("P -> Q")])
        self.assertEqual(t["vars"], ["P", "Q"])
        self.assertEqual([r["values"] for r in t["rows"]][:2], [{"P": True, "Q": True}, {"P": True, "Q": False}])
        self.assertEqual([r["results"][0] for r in t["rows"]], [True, False, True, True])

    def test_validity(self):
        self.assertTrue(check_validity([P("P -> Q"), P("P")], P("Q"))["valid"])
        bad = check_validity([P("P -> Q"), P("Q")], P("P"))
        self.assertEqual((bad["valid"], bad["counterexample"]), (False, {"P": False, "Q": True}))
        self.assertTrue(check_validity([], P("P | ~P"))["valid"])
        self.assertTrue(check_validity([P("P & ~P")], P("Q"))["valid"])  # explosion
        self.assertEqual(check_validity([P("P -> Q"), P("Q")], P("P")), bad)  # the same answer every time

    def test_classify_and_equivalence(self):
        self.assertEqual(classify(P("P | ~P"))["kind"], "tautology")
        self.assertEqual(classify(P("P & ~P"))["kind"], "contradiction")
        self.assertEqual(classify(P("P -> Q"))["kind"], "contingent")
        self.assertTrue(equivalent(P("P -> Q"), P("~P | Q"))["equivalent"])
        self.assertTrue(equivalent(P("~(P & Q)"), P("~P | ~Q"))["equivalent"])
        self.assertTrue(equivalent(P("P -> Q"), P("~Q -> ~P"))["equivalent"])
        diff = equivalent(P("P -> Q"), P("Q -> P"))
        self.assertEqual((diff["equivalent"], diff["counterexample"]), (False, {"P": True, "Q": False}))

    def test_worst_case_is_fast(self):
        premises = [P(" | ".join("ABCDEFGH")) for _ in range(20)]
        start = time.perf_counter()
        check_validity(premises, P("A & B & C & D & E & F & G & H"))
        self.assertLess(time.perf_counter() - start, 1.0)


class Forms(unittest.TestCase):
    def ids(self, premises, conclusion):
        return [m["id"] for m in identify([P(p) for p in premises], P(conclusion))["matches"]]

    def test_named_forms_by_structure(self):
        self.assertEqual(self.ids(["Rain -> Wet", "Rain"], "Wet"), ["modus_ponens"])
        self.assertEqual(self.ids(["Rain", "Rain -> Wet"], "Wet"), ["modus_ponens"])  # premise order
        self.assertEqual(self.ids(["(P & Q) -> R", "R"], "P & Q"), ["affirming_the_consequent"])
        self.assertEqual(self.ids(["X -> Y", "~X"], "~Y"), ["denying_the_antecedent"])
        self.assertEqual(self.ids(["A | B", "B"], "~A"), ["affirming_a_disjunct"])
        self.assertEqual(self.ids(["P -> Q", "~Q"], "~P"), ["modus_tollens"])
        self.assertEqual(self.ids(["P | Q", "~Q"], "P"), ["disjunctive_syllogism"])
        self.assertEqual(self.ids(["P -> Q", "R -> S", "P | R"], "Q | S"), ["constructive_dilemma"])
        self.assertEqual(self.ids(["P -> Q"], "Q -> P"), ["converting_a_conditional"])
        self.assertEqual(self.ids(["P", "Q"], "R"), [])

    def test_every_named_form_agrees_with_the_truth_table(self):
        for fid, _, kind, prem, concl in FORMS:
            with self.subTest(form=fid):
                self.assertEqual(check_validity(prem, concl)["valid"], kind == "valid")

    def test_overlapping_fallacy_instance_is_flagged(self):
        r = identify([P("P -> P"), P("P")], P("P"))
        self.assertTrue(r["valid"])
        fallacy = [m for m in r["matches"] if m["kind"] == "fallacy"]
        self.assertTrue(fallacy and all("note" in m for m in fallacy))


def _model_valid(mood, figure, reading):
    """Brute force over every model of three terms (8 regions, each empty or not)."""
    figs = {1: (("M", "P"), ("S", "M")), 2: (("P", "M"), ("S", "M")), 3: (("M", "P"), ("M", "S")), 4: (("P", "M"), ("M", "S"))}
    terms = "SPM"
    regions = list(product((True, False), repeat=3))

    def holds(kind, x, y, model):
        xi, yi = terms.index(x), terms.index(y)
        inhabited = [r for r, on in zip(regions, model) if on]
        some_x_y = any(r[xi] and r[yi] for r in inhabited)
        some_x_not_y = any(r[xi] and not r[yi] for r in inhabited)
        return {"A": not some_x_not_y, "E": not some_x_y, "I": some_x_y, "O": some_x_not_y}[kind]
    (a, b), (c, d) = figs[figure]
    for model in product((True, False), repeat=8):
        if reading == "aristotelian":
            inhabited = [r for r, on in zip(regions, model) if on]
            if not all(any(r[i] for r in inhabited) for i in range(3)):
                continue
        if holds(mood[0], a, b, model) and holds(mood[1], c, d, model) and not holds(mood[2], "S", "P", model):
            return False
    return True


class Syllogisms(unittest.TestCase):
    def test_rules_match_the_models_for_all_256_forms(self):
        for reading in ("boolean", "aristotelian"):
            valid = []
            for mood in ("".join(m) for m in product("AEIO", repeat=3)):
                for figure in range(1, 5):
                    with self.subTest(form=f"{mood}-{figure}", reading=reading):
                        broken = violations(mood, figure, reading)
                        self.assertEqual(not broken, _model_valid(mood, figure, reading))
                        if not broken:
                            valid.append((mood, figure))
            expected = {k for k, (_, needs) in NAMES.items() if reading == "aristotelian" or needs is None}
            self.assertEqual(set(valid), expected)
            self.assertEqual(len(valid), 15 if reading == "boolean" else 24)

    def test_names_and_named_violations(self):
        for form, name in (("AAA-1", "Barbara"), ("EAE-2", "Cesare"), ("AII-3", "Datisi"), ("AEE-4", "Calemes")):
            r = check_syllogism(form)
            self.assertEqual((r["name"], r["valid"]), (name, True))
        self.assertEqual([v["rule"] for v in check_syllogism("AAA-2")["violations"]], ["undistributed_middle"])
        self.assertIn("illicit_minor", [v["rule"] for v in check_syllogism("AAA-3")["violations"]])
        self.assertIn("illicit_major", [v["rule"] for v in check_syllogism("AEE-1")["violations"]])
        self.assertIn("exclusive_premises", [v["rule"] for v in check_syllogism("EEE-1")["violations"]])
        darapti = check_syllogism("AAI-3", "aristotelian")
        self.assertEqual((darapti["valid"], darapti["needs_existence_of"]), (True, [{"term": "M", "role": "middle"}]))
        self.assertEqual([v["rule"] for v in check_syllogism("AAI-3")["violations"]], ["existential_fallacy"])

    def test_statements_with_real_terms(self):
        r = check_syllogism({
            "major": {"type": "A", "subject": "humans", "predicate": "mortals"},
            "minor": {"type": "A", "subject": "Greeks", "predicate": "humans"},
            "conclusion": {"type": "A", "subject": "Greeks", "predicate": "mortals"}})
        self.assertEqual((r["form"], r["name"], r["terms"]["middle"]), ("AAA-1", "Barbara", "humans"))
        swapped = check_syllogism({  # premises in the other order: still the same syllogism
            "minor": {"type": "A", "subject": "humans", "predicate": "mortals"},
            "major": {"type": "A", "subject": "Greeks", "predicate": "humans"},
            "conclusion": {"type": "A", "subject": "Greeks", "predicate": "mortals"}})
        self.assertEqual(swapped["form"], "AAA-1")
        with self.assertRaises(LogicError) as e:
            check_syllogism({"major": {"type": "A", "subject": "cats", "predicate": "pets"},
                             "minor": {"type": "A", "subject": "dogs", "predicate": "animals"},
                             "conclusion": {"type": "A", "subject": "dogs", "predicate": "pets"}})
        self.assertEqual(e.exception.code, "four_terms")


def L(formula, rule, cites=None, depth=0):
    return {"formula": formula, "rule": rule, "cites": cites or [], "depth": depth}


def proof(*lines, **extra):
    """An exercise whose premises are its PR lines, unless given."""
    if "goal" in extra and "premises" not in extra:
        extra["premises"] = [ln["formula"] for ln in lines if ln.get("rule") == "PR"]
    return logic_proof.check_proof({"lines": list(lines), **extra})


class Proofs(unittest.TestCase):
    def assertProof(self, r, complete=True):
        bad = [(x["n"], x.get("code"), x.get("message")) for x in r["lines"] if not x["ok"]]
        self.assertEqual(bad, [])
        self.assertEqual(r["complete"], complete)

    def test_conditional_proof_and_hypothetical_syllogism(self):
        r = proof(L("P -> Q", "PR"), L("Q -> R", "PR"),
                  L("P", "AS", depth=1), L("Q", "->E", [1, 3], 1), L("R", "->E", [2, 4], 1),
                  L("P -> R", "->I", ["3-5"]), goal="P -> R", premises=["P -> Q", "Q -> R"])
        self.assertProof(r)

    def test_reductio_and_indirect_proof(self):
        self.assertProof(proof(L("P -> Q", "PR"), L("~Q", "PR"),
                               L("P", "AS", depth=1), L("Q", "->E", [1, 3], 1), L("⊥", "~E", [2, 4], 1),
                               L("~P", "~I", ["3-5"]), goal="~P"))
        self.assertProof(proof(L("~~P", "PR"), L("~P", "AS", depth=1), L("⊥", "¬E", [1, 2], 1),
                               L("P", "IP", ["2-3"]), goal="P"))

    def test_disjunction_elimination_with_two_subproofs(self):
        self.assertProof(proof(L("P | Q", "PR"),
                               L("P", "AS", depth=1), L("Q | P", "∨I", [2], 1),
                               L("Q", "AS", depth=1), L("Q | P", "|I", [4], 1),
                               L("Q | P", "|E", [1, "2-3", "4-5"]), goal="Q | P"))

    def test_biconditional_and_conjunction(self):
        self.assertProof(proof(L("P & Q", "PR"), L("Q", "&E", [1]), L("P", "∧E", [1]), L("Q & P", "&I", [2, 3]),
                               L("P", "AS", depth=1), L("P", "R", [5], 1), L("P <-> P", "<->I", ["5-6", "5-6"]),
                               L("P", "<->E", [7, 3]), goal="P"))

    def test_derived_rules_are_on_unless_basic(self):
        lines = (L("P -> Q", "PR"), L("~Q", "PR"), L("~P", "MT", [1, 2]))
        self.assertProof(proof(*lines, goal="~P"))
        r = proof(*lines, goal="~P", rules="basic")
        self.assertEqual(r["lines"][2]["code"], "rule_not_allowed")
        self.assertProof(proof(L("P | Q", "PR"), L("~P", "PR"), L("Q", "DS", [1, 2]), goal="Q"))
        self.assertProof(proof(L("~(P | Q)", "PR"), L("~P & ~Q", "DeM", [1]), goal="~P & ~Q"))
        self.assertProof(proof(L("~~P", "PR"), L("P", "DNE", [1]), goal="P"))
        self.assertProof(proof(L("P -> Q", "PR"), L("P", "PR"), L("Q", "MP", [1, 2]), goal="Q"))  # an alias

    def test_mistakes_are_reported_per_line(self):
        r = proof(L("P -> Q", "PR"), L("Q", "PR"), L("P", "->E", [1, 2]), L("P | R", "|I", [3]), goal="P | R")
        self.assertEqual([x["ok"] for x in r["lines"]], [True, True, False, False])
        self.assertEqual((r["lines"][2]["code"], r["lines"][3]["code"]), ("wrong_form", "depends_on_error"))
        self.assertFalse(r["complete"])

    def test_scope(self):
        # a line inside a closed subproof cannot be cited
        r = proof(L("P", "PR"), L("Q", "AS", depth=1), L("P & Q", "&I", [1, 2], 1), L("Q -> P & Q", "->I", ["2-3"]),
                  L("P & Q", "R", [3]))
        self.assertEqual(r["lines"][4]["code"], "not_in_scope")
        # a subproof cannot be cited from inside itself, nor half of it
        r = proof(L("P", "AS", depth=1), L("P", "R", [1], 1), L("P -> P", "->I", ["1-2"], 1))
        self.assertEqual(r["lines"][2]["code"], "not_in_scope")
        r = proof(L("P", "AS", depth=1), L("P", "R", [1], 1), L("P", "R", [1], 1), L("P -> P", "->I", ["1-2"]))
        self.assertEqual(r["lines"][3]["code"], "bad_cites")
        # ->I with the wrong subproof shape, a premise after the body, a jump in depth
        r = proof(L("P", "AS", depth=1), L("P", "R", [1], 1), L("Q -> P", "->I", ["1-2"]))
        self.assertEqual(r["lines"][2]["code"], "wrong_form")
        r = proof(L("P", "AS", depth=1), L("Q", "PR"))
        self.assertEqual(r["lines"][1]["code"], "premise_position")
        r = proof(L("P", "PR"), L("Q", "AS", depth=3))
        self.assertEqual(r["lines"][1]["code"], "bad_depth")

    def test_goal_and_premises(self):
        r = proof(L("P", "PR"), L("P | Q", "|I", [1]), goal="Q | P")
        self.assertTrue(r["valid"])
        self.assertFalse(r["complete"])
        self.assertIn("goal_message", r)
        r = proof(L("R", "PR"), premises=["P"])
        self.assertEqual(r["lines"][0]["code"], "not_a_premise")
        r = proof(L("P", "Magic"))
        self.assertEqual(r["lines"][0]["code"], "unknown_rule")
        # a goal cannot be reached by calling it a premise
        r = logic_proof.check_proof({"goal": "Q", "lines": [L("Q", "PR")]})
        self.assertEqual((r["lines"][0]["code"], r["complete"]), ("not_a_premise", False))
        self.assertProof(proof(L("P", "AS", depth=1), L("P", "R", [1], 1), L("P -> P", "->I", ["1-2"]), goal="P -> P",
                               premises=[]))

    def test_assumptions_nest_by_default(self):
        r = proof({"formula": "P", "rule": "AS"}, {"formula": "Q", "rule": "AS"}, {"formula": "P", "rule": "R", "cites": [1]},
                  {"formula": "Q -> P", "rule": "->I", "cites": ["2-3"], "depth": 1},
                  {"formula": "P -> (Q -> P)", "rule": "->I", "cites": ["1-4"], "depth": 0}, goal="P -> (Q -> P)")
        self.assertProof(r)

    def test_huge_cite_is_a_line_error(self):
        r = proof(L("P", "PR"), L("P", "R", ["9" * 5000]))
        self.assertEqual(r["lines"][1]["code"], "bad_cite")


class ArgumentMaps(unittest.TestCase):
    def test_unknown_ids_are_errors(self):
        with self.assertRaises(LogicError) as e:
            check_map({"claims": [{"id": "c1", "text": "x"}], "edges": [{"from": "c2", "to": "c1", "type": "supports"}]})
        self.assertIn("c2", e.exception.message)

    def test_findings_on_a_valid_map(self):
        m = {"main": "c1",
             "claims": [{"id": "c1", "text": "We should walk", "formal": "W"},
                        {"id": "c2", "text": "If it is sunny we walk", "formal": "S -> W"},
                        {"id": "c3", "text": "It is sunny", "formal": "S"},
                        {"id": "c4", "text": "It will rain", "role": "objection"},
                        {"id": "c5", "text": "Loop A"}, {"id": "c6", "text": "Loop B"}, {"id": "c7", "text": "Alone"},
                        {"id": "c8", "text": "Done", "formal": "D"}, {"id": "c9", "text": "Busy", "formal": "B"}],
             "edges": [{"from": ["c2", "c3"], "to": "c1", "type": "supports"}, {"from": "c4", "to": "c1", "type": "attacks"},
                       {"from": "c5", "to": "c6", "type": "supports"}, {"from": "c6", "to": "c5", "type": "supports"},
                       {"from": "c9", "to": "c8", "type": "supports"}, {"from": "c9", "to": "c8", "type": "supports"}]}
        r = check_map(m)
        codes = [(f["code"], f["ids"]) for f in r["findings"]]
        self.assertEqual(codes, [("circular_support", ["c5", "c6"]), ("disconnected_claim", ["c7"]),
                                 ("invalid_inference", ["c8", "c9"]), ("unanswered_objection", ["c4"])])
        self.assertEqual(r["findings"][2]["counterexample"], {"B": True, "D": False})
        self.assertEqual(len(r["warnings"]), 1)  # the duplicate edge
        self.assertEqual(check_map(m), r)  # the same order every time

    def test_unsupported_main_and_long_chain(self):
        r = check_map({"main": "a", "claims": [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}],
                       "edges": [{"from": "a", "to": "b", "type": "supports"}]})
        self.assertEqual([f["code"] for f in r["findings"]], ["unsupported_claim"])
        n = 60  # a cycle through every claim: no recursion limit
        ids = [f"c{i}" for i in range(n)]
        r = check_map({"claims": [{"id": i, "text": ""} for i in ids],
                       "edges": [{"from": ids[i], "to": ids[(i + 1) % n], "type": "supports"} for i in range(n)]})
        self.assertEqual(r["findings"][0]["ids"], sorted(ids))

    def test_bad_maps(self):
        for bad in ({"claims": []}, {"claims": [{"id": "a b", "text": ""}]},
                    {"claims": [{"id": "a", "text": ""}], "edges": [{"from": "a", "to": "a", "type": "supports"}]},
                    {"claims": [{"id": "a", "text": "", "formal": "P &"}]},
                    {"claims": [{"id": f"c{i}", "text": ""} for i in range(61)]}):
            with self.subTest(bad=bad):
                with self.assertRaises(LogicError):
                    check_map(bad)


class Engine(unittest.TestCase):
    def test_check_never_raises(self):
        junk = [None, 1, "x", [], {}, {"op": "nope"}, {"op": "parse"}, {"op": "parse", "formula": 5},
                {"op": "validity", "premises": "P"}, {"op": "validity", "premises": [1], "conclusion": "P"},
                {"op": "truth_table", "formulas": ["P"] * 30}, {"op": "syllogism", "form": "XYZ-9"},
                {"op": "syllogism", "major": "x"}, {"op": "syllogism", "form": "AAA-1", "reading": "odd"},
                {"op": "proof"}, {"op": "proof", "lines": [None, 3, {"formula": "P", "rule": "PR", "cites": [True]}]},
                {"op": "proof", "lines": [{"formula": "P", "rule": "PR"}] * 201}, {"op": "proof", "lines": [{}], "premises": "P"},
                {"op": "argmap"}, {"op": "argmap", "map": {"claims": [{"id": "a"}], "edges": [{"from": 3, "to": "a", "type": "supports"}]}},
                {"op": "equivalence", "a": "P"}, {"op": "argmap", "map": {"claims": [{"id": "a"}], "main": ["a"]}}, {"op": "forms", "premises": ["P"] * 21, "conclusion": "P"}]
        for req in junk:
            with self.subTest(req=req):
                out = logic_engine.check(req)
                self.assertIsInstance(out, dict)
                if not out["ok"]:
                    self.assertTrue(out["error"]["code"])
                json.dumps(out)

    def test_ops(self):
        out = logic_engine.check({"op": "validity", "premises": ["P -> Q", "P"], "conclusion": "Q"})
        self.assertEqual((out["ok"], out["result"]["valid"]), (True, True))
        self.assertIn("Informal fallacies", logic_engine.check({"op": "guide"})["result"]["guide"])
        err = logic_engine.check({"op": "validity", "premises": ["P ->"], "conclusion": "Q"})["error"]
        self.assertEqual((err["code"], err["pos"]), ("unexpected_end", 4))
        self.assertIn("Premise 1", err["message"])


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "logic_check.py"), *args, "--compact"],
                              input=stdin, capture_output=True, text=True, timeout=30)

    def test_exit_codes(self):
        r = self.run_cli("valid", "--premises", "P -> Q", "Q", "--conclusion", "P")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(json.loads(r.stdout)["result"]["counterexample"], {"P": False, "Q": True})
        self.assertEqual(self.run_cli("valid", "--premises", "P -> Q", "P", "--conclusion", "Q").returncode, 0)
        self.assertEqual(self.run_cli("parse", "P &").returncode, 2)
        r = self.run_cli("proof", "-", stdin=json.dumps({"goal": "Q", "premises": ["P -> Q", "P"], "lines": [L("P -> Q", "PR"), L("P", "PR"), L("Q", "->E", [1, 2])]}))
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
