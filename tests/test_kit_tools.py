"""Kit tools (docs/plans/KIT_TOOLS_CONTRACT.md): deterministic liberal-arts desks, offline, no model."""
import json
import math
import random
import time
import unittest
from fractions import Fraction
from unittest import mock

from test_lab import LOCAL, TestClient, server  # noqa: F401  (sets up the temp content dir first)
import kit_tools
import mcp_tools_kits
import practice_polity
import practice_music
from kit_tools import run


def ok(kind, op, args):
    r = run(kind, op, args)
    assert r["ok"], r
    return r["result"]


def err(kind, op, args):
    r = run(kind, op, args)
    assert not r["ok"], r
    return r["error"]


class Polity(unittest.TestCase):
    FIX = [({"A": 340000, "B": 280000, "C": 160000, "D": 60000}, 7), ({"X": 100, "Y": 100, "Z": 50}, 5),
           ({"Green": 47000, "Blue": 16000, "Red": 15900, "Gold": 12000}, 8)]

    def test_dhondt_matches_practice_helper(self):
        for votes, seats in self.FIX:
            self.assertEqual(ok("polity", "allocate", {"method": "dhondt", "seats": seats, "votes": votes})["seats"],
                             practice_polity._calc_dhondt(votes, seats))

    def test_sainte_lague_textbook(self):
        # Wikipedia's 8-seat example: 53000/24000/23000/15000... here the classic 100k/80k/30k/20k, 8 seats
        votes = {"A": 100000, "B": 80000, "C": 30000, "D": 20000}
        self.assertEqual(ok("polity", "allocate", {"method": "sainte_lague", "seats": 8, "votes": votes})["seats"],
                         {"A": 3, "B": 3, "C": 1, "D": 1})
        self.assertEqual(ok("polity", "allocate", {"method": "dhondt", "seats": 8, "votes": votes})["seats"],
                         {"A": 4, "B": 3, "C": 1, "D": 0})

    def test_allocate_shape_shares_gallagher(self):
        r = ok("polity", "allocate", {"method": "dhondt", "seats": 4, "votes": {"A": 60, "B": 40}})
        self.assertEqual([x["party"] for x in r["rounds"]], ["A", "B", "A", "A"])
        self.assertEqual(r["rounds"][0], {"seat": 1, "party": "A", "quotient": 60.0})
        self.assertEqual(r["shares"]["A"], {"votes_pct": 60.0, "seats_pct": 75.0})
        self.assertAlmostEqual(r["gallagher"], 15.0, places=3)  # sqrt(((15)^2+(15)^2)/2)
        self.assertEqual(sum(r["seats"].values()), 4)

    def test_ties_by_votes_then_name(self):
        r = ok("polity", "allocate", {"method": "dhondt", "seats": 1, "votes": {"B": 50, "A": 50}})
        self.assertEqual(r["seats"], {"B": 0, "A": 1})
        r = ok("polity", "allocate", {"method": "dhondt", "seats": 2, "votes": {"A": 100, "B": 50}})
        self.assertEqual(r["seats"], {"A": 2, "B": 0})  # second seat: 50 vs 50, the bigger total (A) wins
        self.assertEqual(r["seats"], practice_polity._calc_dhondt({"A": 100, "B": 50}, 2))

    def test_fptp(self):
        d = [{"A": 10, "B": 5}, {"A": 4, "B": 6}, {"A": 7, "B": 7}, {"A": 1}]
        r = ok("polity", "allocate", {"method": "fptp", "districts": d})
        self.assertEqual(r["seats"], {"A": 3, "B": 1})  # the 7-7 tie goes to the higher total (A: 22 vs B: 18)
        self.assertEqual(len(r["rounds"]), 4)

    def test_irv_matches_practice_helper(self):
        cands = ["A", "B", "C", "D"]
        groups = [(["A", "B"], 5), (["B", "C"], 4), (["C", "B"], 3), (["D", "C", "B"], 2), (["A"], 1), (["C"], 2)]
        r = ok("polity", "irv", {"candidates": cands, "ballots": [{"ranking": k, "count": n} for k, n in groups]})
        expanded = [list(k) for k, n in groups for _ in range(n)]
        rounds, elim, winner = practice_polity._calc_irv(cands, expanded)
        self.assertEqual((r["rounds"], r["eliminated"], r["winner"]), (rounds, elim, winner))

    def test_irv_random_cross_check(self):
        rnd = random.Random(3)
        cands = list("ABCDE")
        for _ in range(40):
            groups = [(rnd.sample(cands, rnd.randint(1, 5)), rnd.randint(1, 6)) for _ in range(rnd.randint(1, 8))]
            r = ok("polity", "irv", {"candidates": cands, "ballots": [{"ranking": k, "count": n} for k, n in groups]})
            exp = practice_polity._calc_irv(cands, [list(k) for k, n in groups for _ in range(n)])
            self.assertEqual((r["rounds"], r["eliminated"], r["winner"]), exp)

    def test_stv_droop_small_example(self):
        # 100 ballots, 2 seats: Droop quota floor(100/3)+1 = 34
        ballots = [{"ranking": ["A", "B"], "count": 40}, {"ranking": ["B", "C"], "count": 30},
                   {"ranking": ["C", "D"], "count": 20}, {"ranking": ["D"], "count": 10}]
        r = ok("polity", "stv", {"candidates": list("ABCD"), "ballots": ballots, "seats": 2})
        self.assertEqual(r["quota"], 34)
        self.assertEqual(r["elected"], ["A", "B"])
        self.assertEqual(r["rounds"][0]["who"], "A")
        # A's 6 surplus (6/40 of each ballot) moves to B: 30 + 40*6/40 = 36
        self.assertEqual(r["rounds"][1]["tally"]["B"], "36")

    def test_stv_fraction_surplus_and_exclusion(self):
        ballots = [{"ranking": ["A", "B"], "count": 50}, {"ranking": ["C"], "count": 20}, {"ranking": ["D", "C"], "count": 15},
                   {"ranking": ["B"], "count": 15}]
        r = ok("polity", "stv", {"candidates": list("ABCD"), "ballots": ballots, "seats": 2})
        self.assertEqual(r["quota"], 34)
        self.assertEqual(r["rounds"][0]["action"], "elect")
        self.assertEqual(r["rounds"][0]["who"], "A")
        self.assertEqual(r["rounds"][1]["tally"]["B"], "31")  # 15 + 50 * 16/50
        self.assertEqual(r["rounds"][1]["action"], "exclude")  # nobody at quota: D (15) goes, then C leads
        self.assertEqual(len(r["elected"]), 2)
        r = ok("polity", "stv", {"candidates": list("ABC"), "seats": 1, "ballots": [
            {"ranking": ["A", "B"], "count": 7}, {"ranking": ["B"], "count": 5}, {"ranking": ["C"], "count": 5}]})
        self.assertEqual(r["quota"], 9)  # floor(17/2)+1
        self.assertEqual(r["elected"], ["A"])
        self.assertEqual([x["action"] for x in r["rounds"]], ["exclude", "exclude", "elect"])

    def test_power_textbook(self):
        # UN Security Council: 5 permanent veto members + 10 others, quota 9 (a veto is a weight-7 vs 1 trick)
        w = {"P1": 7, "P2": 7, "P3": 7, "P4": 7, "P5": 7}
        w.update({f"N{i}": 1 for i in range(1, 11)})
        r = ok("polity", "power", {"weights": w, "quota": 39})
        self.assertEqual(r["shapley_shubik"]["P1"]["exact"], "421/2145")  # the textbook 0.1963 per permanent member
        self.assertEqual(r["shapley_shubik"]["P1"]["value"], 0.1963)
        self.assertEqual(r["shapley_shubik"]["N1"]["value"], 0.0019)  # and 0.0019 per non-permanent member
        self.assertEqual(Fraction(r["shapley_shubik"]["P1"]["exact"]) * 5 + Fraction(r["shapley_shubik"]["N1"]["exact"]) * 10, 1)
        self.assertEqual(r["dummies"], [])

    def test_power_small_known(self):
        r = ok("polity", "power", {"weights": {"A": 3, "B": 2, "C": 1, "D": 1}})  # quota 4
        self.assertEqual(r["quota"], 4)
        self.assertEqual({p: v["exact"] for p, v in r["shapley_shubik"].items()}, {"A": "1/2", "B": "1/6", "C": "1/6", "D": "1/6"})
        self.assertEqual({p: v["swings"] for p, v in r["banzhaf"].items()}, {"A": 6, "B": 2, "C": 2, "D": 2})
        self.assertEqual(r["minimal_winning"], [["A", "B"], ["A", "C"], ["A", "D"], ["B", "C", "D"]])
        self.assertAlmostEqual(r["banzhaf"]["A"]["normalized"], 0.5)

    def test_power_dummy_and_matches_helper(self):
        r = ok("polity", "power", {"weights": {"A": 5, "B": 4, "C": 1, "Z": 0}})
        self.assertIn("Z", r["dummies"])
        rnd = random.Random(7)
        for n in range(2, 7):
            w = {f"P{i}": rnd.randint(0, 9) for i in range(n)}
            if sum(w.values()) == 0:
                w["P0"] = 1
            quota = sum(w.values()) // 2 + 1
            r = ok("polity", "power", {"weights": w})
            _, idx = practice_polity._calc_shapley_shubik(quota, w)
            for p in w:
                self.assertAlmostEqual(r["shapley_shubik"][p]["value"], idx[p], places=3)
            self.assertAlmostEqual(sum(v["value"] for v in r["shapley_shubik"].values()), 1.0, places=2)

    def test_power_truncated(self):
        r = ok("polity", "power", {"weights": {f"P{i:02d}": 1 for i in range(15)}, "quota": 8})
        self.assertEqual(len(r["minimal_winning"]), 200)  # C(15,8) = 6435
        self.assertTrue(r["truncated"])

    def test_polity_arg_errors(self):
        self.assertEqual(err("polity", "allocate", {"method": "x"})["at"], "method")
        self.assertEqual(err("polity", "allocate", {"method": "dhondt", "seats": 5, "votes": {"A": -1}})["at"], "votes.A")
        self.assertEqual(err("polity", "allocate", {"method": "dhondt", "seats": 651, "votes": {"A": 1}})["at"], "seats")
        self.assertEqual(err("polity", "allocate", {"method": "dhondt", "seats": 5, "votes": {f"P{i}": 1 for i in range(31)}})["at"], "votes")
        self.assertEqual(err("polity", "power", {"weights": {"A": 1, "B": 1}, "quota": 3})["at"], "quota")
        self.assertEqual(err("polity", "power", {"weights": {"A": 1}})["at"], "weights")
        self.assertEqual(err("polity", "stv", {"candidates": ["A"], "seats": 1, "ballots": [{"ranking": ["Q"]}]})["at"], "ballots.0.ranking.0")
        self.assertEqual(err("polity", "stv", {"candidates": ["A", "B"], "seats": 3, "ballots": [{"ranking": ["A"]}]})["at"], "seats")


class Music(unittest.TestCase):
    def chord(self, s, a, t, b):
        return {"s": s, "a": a, "t": t, "b": b}

    def test_clean_and_issues_match_helper(self):
        good = [self.chord("E5", "G4", "C4", "C3"), self.chord("D5", "G4", "B3", "G2")]
        r = ok("music", "lint", {"chords": good})
        self.assertTrue(r["clean"], r)
        bad = [self.chord("C5", "G4", "E4", "C3"), self.chord("D5", "A4", "F4", "D3")]
        r = ok("music", "lint", {"chords": bad})
        rules = {(i["rule"], tuple(i["voices"]), tuple(i["at"])) for i in r["issues"]}
        helper = practice_music._lint_satb([{k: practice_music._parse_pitch(v) for k, v in c.items()} for c in bad])
        got = [i for i in r["issues"] if i["rule"] in ("voice_crossing", "parallel_fifth", "parallel_octave")]
        self.assertEqual(len(got), len(helper))

    def test_crossing_spacing_range(self):
        r = ok("music", "lint", {"chords": [self.chord("C4", "E4", "G3", "C3"), self.chord("C6", "G3", "C3", "C2")]})
        got = {(i["rule"], tuple(i["voices"]), tuple(i["at"])) for i in r["issues"]}
        self.assertIn(("voice_crossing", ("S", "A"), (0,)), got)
        self.assertIn(("spacing", ("S", "A"), (1,)), got)
        self.assertIn(("range", ("S",), (1,)), got)
        self.assertIn(("range", ("B",), (1,)), got)
        self.assertFalse(r["clean"])

    def test_clean_progression(self):
        r = ok("music", "lint", {"chords": [self.chord("E5", "G4", "C4", "C3"), self.chord("D5", "F4", "B3", "G2")]})
        self.assertTrue(r["clean"], r)
        self.assertEqual(r["issues"], [])

    def test_midi_and_bad_pitch(self):
        ok("music", "lint", {"chords": [self.chord(76, 67, 60, 48), self.chord(74, 65, 59, 43)]})
        e = err("music", "lint", {"chords": [self.chord("C5", "G4", "E4", "C3"), self.chord("C5", "G4", "H9", "C3")]})
        self.assertEqual((e["code"], e["at"]), ("bad_args", "chords.1.t"))
        self.assertEqual(err("music", "lint", {"chords": [self.chord(10, 67, 60, 48)] * 2})["at"], "chords.0.s")
        self.assertEqual(err("music", "lint", {"chords": [self.chord("C5", "G4", "E4", "C3")]})["at"], "chords")

    def test_tuning_textbook(self):
        rows = ok("music", "tuning", {})["rows"]
        self.assertEqual(len(rows), 13)
        fifth = rows[7]["systems"]
        self.assertEqual(fifth["equal"]["cents"], 700.0)
        self.assertEqual(fifth["just"]["cents"], 701.955)
        self.assertEqual(fifth["just"]["ratio"], "3/2")
        self.assertAlmostEqual(fifth["equal"]["vs_equal_cents"], 0.0)
        self.assertAlmostEqual(fifth["just"]["vs_equal_cents"], 1.955, places=3)
        self.assertEqual(fifth["just"]["beat_hz"], 0.0)
        self.assertGreater(fifth["equal"]["beat_hz"], 0)
        third = rows[4]["systems"]
        self.assertAlmostEqual(third["just"]["cents"], 386.3137, places=3)
        # syntonic comma: Pythagorean major third (81/64) minus just (5/4) = 21.51 cents
        self.assertAlmostEqual(third["pythagorean"]["cents"] - third["just"]["cents"], 21.5063, places=3)
        # Pythagorean comma: 12 fifths minus 7 octaves = 23.46 cents
        comma = 12 * fifth["pythagorean"]["cents"] - 7 * rows[12]["systems"]["pythagorean"]["cents"]
        self.assertAlmostEqual(comma, 23.46, places=2)
        self.assertEqual(rows[12]["systems"]["just"]["hz"], 523.26)
        self.assertEqual(rows[0]["systems"]["equal"]["hz"], 261.63)

    def test_tuning_args(self):
        r = ok("music", "tuning", {"root_hz": 440, "systems": ["just"], "semitones": [0, 4, 7]})
        self.assertEqual([x["semitones"] for x in r["rows"]], [0, 4, 7])
        self.assertEqual(r["rows"][2]["systems"]["just"]["hz"], 660.0)
        self.assertEqual(err("music", "tuning", {"root_hz": 5})["at"], "root_hz")
        self.assertEqual(err("music", "tuning", {"systems": ["meantone"]})["at"], "systems.0")
        self.assertEqual(err("music", "tuning", {"semitones": [13]})["at"], "semitones.0")
        self.assertEqual(err("music", "tuning", {"semitones": list(range(14))})["at"], "semitones")


class Classics(unittest.TestCase):
    def test_harris_order_phases_redundant(self):
        edges = [["pit", "floor"], ["floor", "wall"], ["pit", "wall"], ["topsoil", "pit"]]
        r = ok("classics", "harris", {"contexts": ["wall", "floor", "pit", "topsoil", "lone"], "edges": edges})
        self.assertEqual(r["order"], ["lone", "topsoil", "pit", "floor", "wall"])
        self.assertEqual(r["phases"], [["lone", "topsoil"], ["pit"], ["floor"], ["wall"]])
        self.assertEqual(r["redundant"], [["pit", "wall"]])
        self.assertEqual(r["isolated"], ["lone"])

    def test_harris_cycle_is_a_result(self):
        r = ok("classics", "harris", {"contexts": ["a", "b", "c", "d"], "edges": [["d", "a"], ["a", "b"], ["b", "c"], ["c", "a"]]})
        self.assertEqual(r, {"cycle": ["a", "b", "c"]})
        self.assertEqual(ok("classics", "harris", {"contexts": ["a"], "edges": [["a", "a"]]}), {"cycle": ["a"]})

    def test_harris_errors(self):
        self.assertEqual(err("classics", "harris", {"contexts": ["a"], "edges": [["a", "zz"]]})["at"], "edges.0.1")
        self.assertEqual(err("classics", "harris", {"contexts": ["a", "a"]})["at"], "contexts")
        self.assertEqual(err("classics", "harris", {"contexts": ["a" * 61]})["at"], "contexts.0")

    def test_leiden_tokens_and_readings(self):
        r = ok("classics", "leiden", {"text": "D(is) M(anibus)\n[ab]c[---] <x>{y}[[z]]"})
        kinds = [t["kind"] for t in r["tokens"]]
        for k in ("expansion", "restored", "lost", "addition", "deletion", "erasure"):
            self.assertIn(k, kinds)
        self.assertEqual(r["edited"].split("\n")[0], "Dis Manibus")
        self.assertEqual(r["edited"].split("\n")[1], "abc x")
        self.assertNotIn("z", r["edited"])
        self.assertIn("y", r["diplomatic"])
        self.assertEqual(r["normalized"], "dis manibus abc x")
        self.assertEqual(r["problems"], [])
        self.assertEqual(r["tokens"][-1]["line"], 2)

    def test_leiden_underdot_vacat_lost_forms(self):
        r = ok("classics", "leiden", {"text": "ạbc|[.3]d vac."})
        self.assertEqual(r["counts"]["uncertain"], 1)
        self.assertEqual(r["counts"]["vacat"], 1)
        self.assertEqual(r["counts"]["lost"], 1)
        self.assertEqual(r["edited"], "abc\nd ")
        self.assertEqual([t["line"] for t in r["tokens"] if t["kind"] == "lost"], [2])
        self.assertEqual(ok("classics", "leiden", {"text": "[...]"})["counts"], {"lost": 1})
        self.assertEqual(ok("classics", "leiden", {"text": "⟦ab⟧"})["counts"], {"erasure": 1})

    def test_leiden_uncertain_letter_keeps_its_accents(self):
        r = ok("classics", "leiden", {"text": "ἐ̣πὶ"})
        self.assertEqual([t["kind"] for t in r["tokens"]], ["uncertain", "text"])
        self.assertEqual(r["tokens"][0]["text"], "ἐ̣")
        self.assertEqual(r["tokens"][1]["text"], "πὶ")
        self.assertEqual(r["edited"], "ἐπὶ")

    def test_leiden_problems(self):
        self.assertEqual(ok("classics", "leiden", {"text": "ab[cd"})["problems"], [{"code": "unbalanced", "at": 2}])
        self.assertEqual(ok("classics", "leiden", {"text": "ab)c"})["problems"], [{"code": "unbalanced", "at": 2}])
        self.assertEqual(ok("classics", "leiden", {"text": "[a(b)c]"})["problems"][0]["code"], "nested")
        self.assertEqual(err("classics", "leiden", {"text": "x" * 2001})["at"], "text")
        self.assertEqual(err("classics", "leiden", {"text": "\n" * 41})["at"], "text")
        self.assertEqual(err("classics", "leiden", {})["at"], "text")


class Literature(unittest.TestCase):
    def test_iambic_pentameter(self):
        r = ok("literature", "scan", {"stresses": "x / x / x / x / x /"})
        self.assertEqual((r["meter"], r["line_name"], r["foot_count"], r["fit"], r["feminine_ending"]), ("iambic", "pentameter", 5, 1.0, False))
        self.assertTrue(all(f["name"] == "iamb" and not f["substitution"] for f in r["feet"]))

    def test_feminine_and_substitution(self):
        r = ok("literature", "scan", {"stresses": "x/x/x/x/x/x"})
        self.assertTrue(r["feminine_ending"])
        self.assertEqual(r["foot_count"], 5)
        r = ok("literature", "scan", {"stresses": "/xx/x/x/x/", "meter": "iambic"})
        self.assertEqual(r["feet"][0]["name"], "trochee")
        self.assertTrue(r["feet"][0]["substitution"])
        self.assertEqual(r["fit"], 0.8)
        r = ok("literature", "scan", {"stresses": "u u / u u / u u /"})
        self.assertEqual((r["meter"], r["line_name"], r["fit"]), ("anapestic", "trimeter", 1.0))

    def test_trochaic_and_dactylic_and_fixed_meter(self):
        r = ok("literature", "scan", {"stresses": "/x/x/x/x"})
        self.assertEqual((r["meter"], r["line_name"], r["fit"]), ("trochaic", "tetrameter", 1.0))
        r = ok("literature", "scan", {"stresses": "/xx/xx/xx/xx/xx/x", "meter": "dactylic"})
        self.assertEqual((r["foot_count"], r["line_name"]), (6, "hexameter"))
        self.assertEqual(ok("literature", "scan", {"stresses": "x/x/", "meter": "trochaic"})["meter"], "trochaic")

    def test_scan_errors(self):
        self.assertEqual(err("literature", "scan", {"stresses": "x/q"})["at"], "stresses.2")
        self.assertEqual(err("literature", "scan", {"stresses": "x" * 25})["at"], "stresses")
        self.assertEqual(err("literature", "scan", {"stresses": " "})["at"], "stresses")
        self.assertEqual(err("literature", "scan", {"stresses": "x/", "meter": "free"})["at"], "meter")

    def test_form_sonnets(self):
        r = ok("literature", "form", {"form": "shakespearean_sonnet", "rhymes": list("XYXYZWZWQRQRTT")})
        self.assertEqual((r["scheme_expected"], r["scheme_given"], r["mismatches"], r["fit"], r["line_count_ok"]),
                         ("ABABCDCDEFEFGG", "ABABCDCDEFEFGG", [], 1.0, True))
        r = ok("literature", "form", {"form": "shakespearean_sonnet", "rhymes": list("ABBACDCDEFEFGG")})
        self.assertEqual(r["mismatches"], [2, 3])
        r = ok("literature", "form", {"form": "petrarchan_sonnet", "rhymes": list("ABBAABBACDCDCD")})
        self.assertEqual(r["scheme_expected"], "ABBAABBACDCDCD")
        self.assertEqual(r["fit"], 1.0)
        r = ok("literature", "form", {"form": "petrarchan_sonnet", "rhymes": list("abbaabbacdedce")})
        self.assertEqual(r["mismatches"], [])
        self.assertEqual(r["expected_lines"], 14)

    def test_form_others(self):
        r = ok("literature", "form", {"form": "limerick", "rhymes": list("AABBA")})
        self.assertEqual(r["fit"], 1.0)
        r = ok("literature", "form", {"form": "limerick", "rhymes": list("AABB")})
        self.assertFalse(r["line_count_ok"])
        self.assertLess(r["fit"], 1.0)
        r = ok("literature", "form", {"form": "terza_rima", "rhymes": list("ABABCBCDC")})
        self.assertEqual((r["scheme_expected"], r["line_count_ok"], r["mismatches"]), ("ABABCBCDC", True, []))
        self.assertEqual(ok("literature", "form", {"form": "terza_rima", "rhymes": list("ABABCBC")})["line_count_ok"], True)
        self.assertEqual(ok("literature", "form", {"form": "terza_rima", "rhymes": list("ABABC")})["line_count_ok"], False)

    def test_villanelle_refrains(self):
        scheme = list("ABA" * 5 + "ABAA")
        lines = [f"line {i}" for i in range(19)]
        lines[5] = lines[11] = lines[17] = "Do not go gentle!"
        lines[0] = "do not go gentle"
        lines[2] = "Rage, rage"
        lines[8] = "rage rage"
        lines[14] = "Rage, Rage."
        lines[18] = "something else"
        r = ok("literature", "form", {"form": "villanelle", "rhymes": scheme, "lines": lines})
        self.assertEqual(r["expected_lines"], 19)
        self.assertEqual({x["line"]: x["ok"] for x in r["refrains"]}, {6: True, 12: True, 18: True, 9: True, 15: True, 19: False})
        self.assertLess(r["fit"], 1.0)
        self.assertEqual(ok("literature", "form", {"form": "villanelle", "rhymes": scheme})["refrains"], [])

    def test_form_errors(self):
        self.assertEqual(err("literature", "form", {"form": "ode", "rhymes": ["A"]})["at"], "form")
        self.assertEqual(err("literature", "form", {"form": "limerick", "rhymes": []})["at"], "rhymes")
        self.assertEqual(err("literature", "form", {"form": "limerick", "rhymes": ["A"], "lines": ["x" * 301]})["at"], "lines.0")


class Rhetoric(unittest.TestCase):
    def test_toulmin(self):
        r = ok("rhetoric", "toulmin", {"claim": "c", "data": "d", "warrant": "w", "qualifier": "usually"})
        self.assertTrue(r["complete"])
        self.assertEqual(r["missing"], ["backing", "rebuttal"])
        self.assertEqual(r["notes"], ["A qualifier without a rebuttal leaves the exception unstated"])
        r = ok("rhetoric", "toulmin", {"claim": "c", "data": "  "})
        self.assertFalse(r["complete"])
        self.assertFalse(r["present"]["data"])
        self.assertEqual(err("rhetoric", "toulmin", {"claim": "x" * 1001})["at"], "claim")
        self.assertEqual(err("rhetoric", "toulmin", {"claim": 5})["at"], "claim")

    def test_appeals(self):
        r = ok("rhetoric", "appeals", {"segments": [{"text": "a" * 10, "tags": ["ethos"]}, {"text": "b" * 20, "tags": ["logos", "pathos"]},
                                                       {"text": "c" * 5, "tags": []}]})
        self.assertEqual(r["totals"], {"ethos": 10.0, "logos": 10.0, "pathos": 10.0})
        self.assertEqual(r["untagged_chars"], 5)
        self.assertAlmostEqual(sum(r["shares"].values()), 1.0, places=3)
        self.assertAlmostEqual(r["point"]["x"], 0.5, places=3)
        self.assertAlmostEqual(r["point"]["y"], math.sqrt(3) / 6, places=3)
        pure = ok("rhetoric", "appeals", {"segments": [{"text": "abc", "tags": ["logos"]}]})
        self.assertEqual(pure["point"], {"x": 0.5, "y": 0.866})
        self.assertEqual(ok("rhetoric", "appeals", {"segments": []})["shares"], {"ethos": 0.0, "logos": 0.0, "pathos": 0.0})
        self.assertEqual(err("rhetoric", "appeals", {"segments": [{"text": "a", "tags": ["pathos", "kairos"]}]})["at"], "segments.0.tags.1")
        self.assertEqual(err("rhetoric", "appeals", {"segments": [{"text": "a"}] * 101})["at"], "segments")


class RunContract(unittest.TestCase):
    def test_error_codes(self):
        self.assertEqual(err("polity", "nope", {})["code"], "bad_op")
        self.assertEqual(err("alchemy", "x", {})["code"], "bad_op")
        self.assertEqual(err("art_history", "x", {})["code"], "bad_op")
        self.assertEqual(err("polity", "power", [])["code"], "bad_args")
        self.assertEqual(err("polity", "power", None)["code"], "bad_args")
        self.assertEqual(err("polity", "power", {"weights": {"A": float("nan"), "B": 1}})["code"], "bad_args")
        self.assertEqual(err("polity", "power", {"weights": {"A": float("inf"), "B": 1}})["code"], "bad_args")
        self.assertEqual(err("rhetoric", "toulmin", {"claim": "x" * (kit_tools.MAX_ARGS_BYTES + 1)})["code"], "too_large")
        deep = cur = {}
        for _ in range(100_000):
            cur["a"] = {}
            cur = cur["a"]
        self.assertIn(err("polity", "power", {"weights": deep})["code"], ("too_complex", "too_large"))
        mid = cur = {}
        for _ in range(3000):
            cur["a"] = {}
            cur = cur["a"]
        self.assertFalse(run("polity", "power", {"weights": mid})["ok"])  # nesting within the cap is a clean error
        with mock.patch.dict(kit_tools.TOOLS["polity"], {"power": lambda a: 1 / 0}):
            self.assertEqual(err("polity", "power", {})["code"], "bad_input")
        with mock.patch.dict(kit_tools.TOOLS["polity"], {"power": lambda a: (_ for _ in ()).throw(MemoryError())}):
            self.assertEqual(err("polity", "power", {})["code"], "too_complex")
        self.assertEqual(kit_tools.ToolError("bad_args", "m", "x.y").to_dict(), {"code": "bad_args", "message": "m", "at": "x.y"})

    def test_run_never_raises_on_junk(self):
        junk = [None, [], [1, 2], "x", 5, 1.5, True, {}, {"a": None}, {"method": []}, {"weights": "x"}, {"chords": {}},
                {"text": None}, {"text": ["x"]}, {"stresses": 5}, {"segments": "s"}, {"candidates": 7, "ballots": 2},
                {"contexts": [[]], "edges": [[1, 2]]}, {"rhymes": [None], "form": "limerick"}, {"text": "[" * 1500},
                {"text": "x" * 100_000}, {"votes": {"A": "9" * 5000}, "seats": 2, "method": "dhondt"},
                {"weights": {"A": 10 ** 30, "B": 1}}, {"semitones": [1.5]}, {"root_hz": "440"}]
        rnd = random.Random(1)
        for kind, ops in kit_tools.TOOLS.items():
            for op in ops:
                for j in junk + [{"x": rnd.random()} for _ in range(5)]:
                    r = run(kind, op, j)
                    self.assertIn("ok", r)
                    self.assertEqual(r["ok"], "result" in r)
                    json.dumps(r, allow_nan=False)
        for k, o in ((None, None), (1, 2), ([], {}), ("polity", None)):
            self.assertFalse(run(k, o, {})["ok"])

    def test_guide(self):
        g = kit_tools.guide()
        self.assertEqual(set(g), {"polity", "music", "classics", "literature", "rhetoric"})
        for kind, ops in g.items():
            for op, doc in ops.items():
                self.assertTrue(doc.strip(), (kind, op))
        self.assertNotIn("art_history", kit_tools.TOOLS)

    def test_results_are_json_finite(self):
        r = run("music", "tuning", {})
        json.dumps(r, allow_nan=False)


class WorstCase(unittest.TestCase):
    def under_a_second(self, kind, op, args):
        t = time.perf_counter()
        r = run(kind, op, args)
        dt = time.perf_counter() - t
        self.assertTrue(r["ok"], r)
        self.assertLess(dt, 1.0, f"{kind}.{op} took {dt:.2f}s")
        return r["result"]

    def test_power_15_players(self):
        r = self.under_a_second("polity", "power", {"weights": {f"P{i:02d}": 1000 + 7 * i for i in range(15)}})
        self.assertEqual(len(r["banzhaf"]), 15)

    def test_stv_500_groups(self):
        rnd = random.Random(5)
        cands = [f"C{i:02d}" for i in range(20)]
        ballots = [{"ranking": rnd.sample(cands, 20), "count": rnd.randint(1, 1000)} for _ in range(500)]
        self.under_a_second("polity", "stv", {"candidates": cands, "ballots": ballots, "seats": 10})
        self.under_a_second("polity", "irv", {"candidates": cands, "ballots": ballots})

    def test_allocate_big(self):
        self.under_a_second("polity", "allocate", {"method": "sainte_lague", "seats": 650, "votes": {f"P{i}": 10 ** 9 - i for i in range(30)}})
        self.under_a_second("polity", "allocate", {"method": "fptp", "districts": [{f"P{i}": 1000 + i + j for i in range(30)} for j in range(650)]})

    def test_harris_200_nodes(self):
        ctx = [f"c{i:03d}" for i in range(200)]
        edges = [[ctx[i], ctx[j]] for i in range(200) for j in range(i + 1, 200) if (i * 7 + j * 3) % 8 == 0][:1000]
        r = self.under_a_second("classics", "harris", {"contexts": ctx, "edges": edges})
        self.assertEqual(len(r["order"]), 200)
        chain = [[ctx[i], ctx[i + 1]] for i in range(199)] + [[ctx[199], ctx[0]]]
        self.assertEqual(len(self.under_a_second("classics", "harris", {"contexts": ctx, "edges": chain})["cycle"]), 200)

    def test_text_and_music_caps(self):
        self.under_a_second("classics", "leiden", {"text": "\n".join(["[ab(c)d]{e}<f>[[g]] ạ" * 4] * 40)[:2000]})
        chords = [{"s": "E5", "a": "G4", "t": "C4", "b": "C3"}] * 32
        self.under_a_second("music", "lint", {"chords": chords})
        self.under_a_second("literature", "scan", {"stresses": "x/" * 12})
        self.under_a_second("literature", "scan", {"stresses": "xx/" * 8, "meter": "dactylic"})
        self.under_a_second("rhetoric", "appeals", {"segments": [{"text": "w" * 1000, "tags": ["ethos", "logos", "pathos"]}] * 100})


class Route(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(server.app, base_url=LOCAL)
        server._rate_hits.clear()

    def test_unknown_kind_404_and_bad_op_200(self):
        self.assertEqual(self.c.post("/api/kits/alchemy/tool", json={"op": "x"}).status_code, 404)
        self.assertEqual(self.c.post("/api/kits/art_history/tool", json={"op": "x"}).status_code, 404)
        r = self.c.post("/api/kits/polity/tool", json={"op": "nope"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["error"]["code"], "bad_op")
        self.assertEqual(self.c.post("/api/kits/polity/tool", json={}).status_code, 422)

    def test_happy_path_and_guide(self):
        r = self.c.post("/api/kits/polity/tool", json={"op": "allocate", "args": {"method": "dhondt", "seats": 3, "votes": {"A": 3, "B": 1}}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True, "result": kit_tools.run("polity", "allocate", {"method": "dhondt", "seats": 3, "votes": {"A": 3, "B": 1}})["result"]})
        g = self.c.get("/api/kits/tools")
        self.assertEqual(g.status_code, 200)
        self.assertIn("harris", g.json()["classics"])

    def test_rate_limit_429(self):
        self.assertEqual(server.RATE_LIMITS["kit_tool"], 1200)
        with mock.patch.object(server, "RATE_SCALE", 1 / 600):  # 1200 / 600 = 2 per hour
            codes = [self.c.post("/api/kits/music/tool", json={"op": "tuning"}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_accounts_mode_requires_a_session(self):
        with mock.patch.object(server, "AUTH_REQUIRED", True):
            self.assertEqual(self.c.post("/api/kits/polity/tool", json={"op": "allocate"}).status_code, 401)
            self.assertEqual(self.c.get("/api/kits/tools").status_code, 401)

    def test_logic_grade_is_sync_and_limited(self):
        import inspect
        self.assertFalse(inspect.iscoroutinefunction(server.logic_grade))
        self.assertEqual(server.RATE_LIMITS["logic_grade"], 1200)
        r = self.c.post("/api/logic/grade", json={"op": "parse", "formula": "p -> q"})
        self.assertEqual(r.status_code, 200)
        server._rate_hits.clear()
        with mock.patch.object(server, "RATE_SCALE", 1 / 600):
            codes = [self.c.post("/api/logic/grade", json={"op": "parse", "formula": "p"}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])


class McpTool(unittest.TestCase):
    def test_kit_tool_mirrors_endpoint(self):
        calls = []
        tools = {n: fn for n, _, _, fn in mcp_tools_kits.tools(lambda *a: calls.append(a) or {"ok": True}, lambda s: s,
                                                              lambda **k: k, lambda d, **k: {}, lambda d, **k: {}, lambda d, **k: {})}
        self.assertEqual(tools["kit_tool"]({"kind": "music", "op": "tuning"}), {"ok": True})
        self.assertEqual(calls[0], ("POST", "/api/kits/music/tool", {"op": "tuning", "args": {}}))


if __name__ == "__main__":
    unittest.main()
