"""STEM kit tools (docs/plans/STEM_KIT_TOOLS_CONTRACT.md): ee, ai, systems, stats, bio desks, offline, no model."""
import json
import math
import random
import time
import unittest
from fractions import Fraction

from test_lab import LOCAL, TestClient, server  # noqa: F401  (sets up the temp content dir first)
import kit_tools
import practice_ai
import practice_bio
import practice_stats
import practice_systems
from kit_tools import run

STEM = {"ee": ("dc_solve", "bode"), "ai": ("metrics", "descent"), "systems": ("cache", "bankers"),
        "stats": ("two_sample", "markov"), "bio": ("align", "orf")}


def ok(kind, op, args):
    r = run(kind, op, args)
    assert r["ok"], r
    return r["result"]


def err(kind, op, args):
    r = run(kind, op, args)
    assert not r["ok"], r
    return r["error"]


def R(a, b, v):
    return {"type": "R", "a": a, "b": b, "value": v}


class Ee(unittest.TestCase):
    def test_divider(self):
        r = ok("ee", "dc_solve", {"elements": [{"type": "V", "a": "in", "b": "0", "value": 10}, R("in", "mid", 1000),
                                                R("mid", "0", 2000)]})
        self.assertTrue(r["solvable"])
        self.assertEqual(r["nodes"]["mid"], {"exact": "20/3", "value": 6.6667})
        self.assertEqual(r["nodes"]["0"]["exact"], "0")
        self.assertEqual(r["elements"][1]["current_exact"], "1/300")
        self.assertEqual(r["elements"][2]["current_exact"], "1/300")
        self.assertEqual(r["elements"][0]["current_exact"], "-1/300")  # the source delivers: a -> b current is negative
        self.assertEqual(sum(Fraction(e["power_exact"]) for e in r["elements"]), 0)
        self.assertEqual(set(r["elements"][0]), {"index", "type", "current", "voltage", "power", "current_exact",
                                                 "voltage_exact", "power_exact"})

    def test_current_source_direction(self):
        # 2 A flowing a -> b inside the source pulls current out of node a: 1 ohm from a to ground gives -2 V at a
        r = ok("ee", "dc_solve", {"elements": [{"type": "I", "a": "a", "b": "0", "value": 2}, R("a", "0", 1)]})
        self.assertEqual(r["nodes"]["a"]["exact"], "-2")
        r = ok("ee", "dc_solve", {"elements": [{"type": "I", "a": "0", "b": "a", "value": 2}, R("a", "0", 1)]})
        self.assertEqual(r["nodes"]["a"]["exact"], "2")
        self.assertEqual(sum(Fraction(e["power_exact"]) for e in r["elements"]), 0)

    def test_wheatstone_balanced(self):
        r = ok("ee", "dc_solve", {"elements": [{"type": "V", "a": "t", "b": "0", "value": 12}, R("t", "l", 1000),
                                                R("l", "0", 1000), R("t", "r", 1000), R("r", "0", 1000),
                                                R("l", "r", 5000)]})
        self.assertEqual(r["elements"][5]["current_exact"], "0")
        self.assertEqual(r["nodes"]["l"]["exact"], "6")
        self.assertEqual(sum(Fraction(e["power_exact"]) for e in r["elements"]), 0)

    def test_floating_and_singular(self):
        r = ok("ee", "dc_solve", {"elements": [R("a", "0", 100), R("x", "y", 5)]})
        self.assertEqual((r["solvable"], r["reason"], r["nodes_unreached"]), (False, "floating_node", ["x", "y"]))
        r = ok("ee", "dc_solve", {"elements": [{"type": "I", "a": "0", "b": "a", "value": 1}, R("a", "0", 1)]})
        self.assertTrue(r["solvable"])
        r = ok("ee", "dc_solve", {"elements": [{"type": "V", "a": "a", "b": "0", "value": 5},
                                                {"type": "V", "a": "a", "b": "0", "value": 6}]})
        self.assertEqual((r["solvable"], r["reason"]), (False, "singular"))

    def test_dc_errors_and_caps(self):
        self.assertEqual(err("ee", "dc_solve", {"elements": [R("a", "b", 1)], "ground": "0"})["at"], "ground")
        self.assertEqual(err("ee", "dc_solve", {"elements": [R("a", "0", 0)]})["at"], "elements.0.value")
        self.assertEqual(err("ee", "dc_solve", {"elements": [R("a", "0", 2e9)]})["code"], "bad_args")
        self.assertEqual(err("ee", "dc_solve", {"elements": [R("a" * 13, "0", 1)]})["at"], "elements.0.a")
        self.assertEqual(err("ee", "dc_solve", {"elements": [{"type": "X", "a": "a", "b": "0", "value": 1}]})["at"], "elements.0.type")
        self.assertEqual(err("ee", "dc_solve", {"elements": [R("a", "0", 1)] * 31})["code"], "too_large")
        chain = [R(str(i), str(i + 1), 1) for i in range(13)]  # 14 nodes
        self.assertEqual(err("ee", "dc_solve", {"elements": chain, "ground": "0"})["code"], "too_complex")
        vs = [{"type": "V", "a": str(i + 1), "b": "0", "value": 1} for i in range(11)]
        self.assertEqual(err("ee", "dc_solve", {"elements": vs})["code"], "too_complex")

    def test_bode_first_order(self):
        r = ok("ee", "bode", {"num": [1], "den": [0.001, 1]})
        self.assertAlmostEqual(r["cutoff_rad_s"], 1000, delta=0.5)
        at = [s for s in r["samples"] if s["w"] == 1000][0]
        self.assertAlmostEqual(at["phase_deg"], -45, places=2)
        self.assertAlmostEqual(at["mag_db"], -3.0103, places=2)
        self.assertEqual(r["dc_gain_db"], 0.0)
        self.assertIsNone(r["gain_crossover"])
        self.assertEqual(len(r["samples"]), 121)
        self.assertEqual(set(r), {"samples", "dc_gain_db", "cutoff_rad_s", "gain_crossover", "phase_margin_deg",
                                  "phase_crossover", "gain_margin_db", "undefined_at"})

    def test_bode_resonance(self):
        r = ok("ee", "bode", {"num": [1], "den": [1, 0.2, 1], "w_min": 0.5, "w_max": 2, "points": 401})
        peak = max(r["samples"], key=lambda s: s["mag_db"])
        self.assertAlmostEqual(peak["mag_db"], 14.023, delta=0.01)
        self.assertAlmostEqual(peak["w"], 0.98995, delta=0.005)

    def test_bode_margins(self):
        r = ok("ee", "bode", {"num": [2], "den": [1, 3, 2, 0]})
        self.assertAlmostEqual(r["phase_crossover"], 1.4142, delta=1e-3)
        self.assertAlmostEqual(r["gain_margin_db"], 9.5424, places=3)
        self.assertIsNone(r["dc_gain_db"])  # an integrator has no dc gain
        # gain crossover: |2 / (jw (jw+1)(jw+2))| = 1 at w ~ 0.7494, phase margin 180 - (90 + atan(w) + atan(w/2))
        w = r["gain_crossover"]
        self.assertAlmostEqual(abs(2 / (complex(0, w) * complex(1, w) * complex(2, w))), 1, places=4)
        self.assertAlmostEqual(r["phase_margin_deg"], 180 - (90 + math.degrees(math.atan(w) + math.atan(w / 2))), places=2)

    def test_bode_phase_branch(self):
        r = ok("ee", "bode", {"num": [1], "den": [1, 2, 1, 0, 0]})  # type 2: starts near -180 (true -181.15), not +178.85
        self.assertAlmostEqual(r["samples"][0]["phase_deg"], -181.15, delta=0.05)
        self.assertLess(r["samples"][-1]["phase_deg"], -300)
        # 1/(s^2 (s+1)^2) has phase -180 - 2 atan(w): always below -180, so it never crosses it (null is right)
        self.assertIsNone(r["phase_crossover"])
        self.assertTrue(all(s["phase_deg"] < -180 for s in r["samples"]))
        # an unwrapped type-2 plant that does cross: K(s+1)/(s^2 (s+10)) rises to -180 + atan(w) - atan(w/10) > -180
        r = ok("ee", "bode", {"num": [1, 1], "den": [1, 10, 0, 0]})
        self.assertTrue(all(-180 < s["phase_deg"] < -90 for s in r["samples"]))
        # a negative gain starts near -180 (documented), a positive one near 0
        self.assertAlmostEqual(ok("ee", "bode", {"num": [-1], "den": [1, 1]})["samples"][0]["phase_deg"], -180.57, delta=0.05)
        self.assertAlmostEqual(ok("ee", "bode", {"num": [1], "den": [1, 1]})["samples"][0]["phase_deg"], -0.57, delta=0.05)
        self.assertAlmostEqual(ok("ee", "bode", {"num": [1, 0], "den": [1, 1]})["samples"][0]["phase_deg"], 89.43, delta=0.05)
        self.assertAlmostEqual(ok("ee", "bode", {"num": [1], "den": [1, 1, 0]})["samples"][0]["phase_deg"], -90.57, delta=0.05)

    def test_bode_pole_on_axis_is_undefined(self):
        r = ok("ee", "bode", {"num": [1], "den": [1, 0, 1]})  # the default grid hits w = 1
        self.assertIn(1.0, r["undefined_at"])
        self.assertEqual(len(r["samples"]) + len(r["undefined_at"]), 121)
        self.assertTrue(all(s["w"] != 1.0 for s in r["samples"]))
        self.assertTrue(all(s["mag_db"] < 100 for s in r["samples"] if abs(s["w"] - 1) > 0.1))
        json.dumps(r, allow_nan=False)

    def test_bode_edges(self):
        r = ok("ee", "bode", {"num": [1, 0], "den": [1, 0, 1], "w_min": 0.5, "w_max": 2, "points": 11})
        self.assertIsInstance(r["undefined_at"], list)  # a pole on the axis may land on the grid
        r = ok("ee", "bode", {"num": [0], "den": [1, 1]})
        self.assertEqual(r["samples"][0]["mag_db"], -400.0)
        json.dumps(r, allow_nan=False)
        self.assertEqual(err("ee", "bode", {"num": [1], "den": [0, 0]})["at"], "den")
        self.assertEqual(err("ee", "bode", {"num": [1] * 8, "den": [1]})["code"], "too_large")
        self.assertEqual(err("ee", "bode", {"num": [1], "den": [1, 1], "w_min": 5, "w_max": 1})["code"], "bad_args")
        self.assertEqual(err("ee", "bode", {"num": [1], "den": [1, 1], "points": 5})["at"], "points")
        self.assertEqual(err("ee", "bode", {"num": [1e10], "den": [1]})["code"], "bad_args")


class Ai(unittest.TestCase):
    M = [[40, 20], [10, 30]]

    def test_matrix_textbook(self):
        r = ok("ai", "metrics", {"matrix": self.M})
        c0 = r["per_class"][0]
        self.assertEqual((c0["precision"], c0["recall"], c0["f1"], c0["specificity"], c0["support"]),
                         (0.8, 0.6667, 0.7273, 0.75, 60))  # the contract's 0.6857 is a slip: 2*.8*.6667/1.4667
        self.assertEqual(r["accuracy"], 0.7)
        self.assertEqual(r["mcc"], 0.4082)
        self.assertEqual(r["matrix"], self.M)
        self.assertEqual(r["micro_f1"], 0.7)
        # kappa: po 0.7, pe (60*50 + 40*50) / 100^2 = 0.5
        self.assertEqual(r["kappa"], 0.4)
        self.assertEqual(set(r), {"accuracy", "per_class", "macro_f1", "weighted_f1", "micro_f1", "kappa", "mcc", "matrix"})
        self.assertEqual(set(c0), {"label", "precision", "recall", "f1", "specificity", "support"})

    def test_matches_practice_ai(self):
        item = practice_ai._np_confusion_matrix_metrics({"TP": 40, "FP": 10, "FN": 20, "TN": 30}, {})
        r = ok("ai", "metrics", {"matrix": self.M})["per_class"][0]
        for k, v in item["metrics"].items():
            self.assertEqual(r[k], v)
        rnd = random.Random(3)
        for _ in range(20):
            tp, fn, fp, tn = (rnd.randint(1, 50) for _ in range(4))  # practice_ai reads a 0 count as missing
            item = practice_ai._np_confusion_matrix_metrics({"TP": tp, "FP": fp, "FN": fn, "TN": tn}, {})
            r = ok("ai", "metrics", {"matrix": [[tp, fn], [fp, tn]]})["per_class"][0]
            for k, v in item["metrics"].items():
                self.assertEqual(r[k], v)

    def test_multiclass_and_zero(self):
        r = ok("ai", "metrics", {"matrix": [[5, 1, 0], [2, 3, 1], [0, 0, 4]]})
        self.assertIsNone(r["mcc"])
        self.assertEqual(r["accuracy"], round(12 / 16, 4))
        self.assertEqual([c["support"] for c in r["per_class"]], [6, 6, 4])
        self.assertAlmostEqual(r["weighted_f1"], sum(c["f1"] * c["support"] for c in r["per_class"]) / 16, places=3)
        r = ok("ai", "metrics", {"matrix": [[0, 0], [0, 0]]})
        self.assertEqual((r["accuracy"], r["kappa"], r["mcc"], r["macro_f1"]), (0.0, 0.0, 0.0, 0.0))
        r = ok("ai", "metrics", {"matrix": [[0, 0], [5, 0]]})  # no positive predictions: precision 0, not a crash
        self.assertEqual(r["per_class"][0]["precision"], 0.0)

    def test_auc(self):
        self.assertEqual(ok("ai", "metrics", {"labels": [1, 1, 0, 0], "scores": [.9, .8, .7, .1]})["auc"], 1.0)
        self.assertEqual(ok("ai", "metrics", {"labels": [1, 0, 1, 0], "scores": [.9, .8, .7, .6]})["auc"], 0.75)
        r = ok("ai", "metrics", {"labels": [1, 0, 1, 0], "scores": [.5, .5, .5, .5]})
        self.assertEqual(r["auc"], 0.5)
        self.assertEqual(r["roc"], [{"fpr": 0.0, "tpr": 0.0, "threshold": None}, {"fpr": 1.0, "tpr": 1.0, "threshold": 0.5}])
        r = ok("ai", "metrics", {"labels": [1, 1, 0, 0], "scores": [.9, .8, .7, .1], "threshold": 0.75})
        self.assertEqual(r["matrix"], [[2, 0], [0, 2]])
        self.assertEqual(r["per_class"][0]["label"], 1)
        self.assertIsNone(ok("ai", "metrics", {"labels": [1, 1], "scores": [.1, .2]})["auc"])
        # a threshold exactly on a score predicts positive
        self.assertEqual(ok("ai", "metrics", {"labels": [1, 0], "scores": [.5, .2]})["matrix"], [[1, 0], [0, 1]])

    def test_metrics_errors(self):
        self.assertEqual(err("ai", "metrics", {"matrix": [[1, 2], [3]]})["code"], "bad_args")
        self.assertEqual(err("ai", "metrics", {"matrix": [[1, 2, 3], [1, 2, 3]]})["code"], "bad_args")
        self.assertEqual(err("ai", "metrics", {"matrix": [[1, -2], [3, 4]]})["at"], "matrix.0.1")
        self.assertEqual(err("ai", "metrics", {"matrix": [[1] * 11] * 11})["code"], "too_large")
        self.assertEqual(err("ai", "metrics", {"labels": [1, 2], "scores": [1, 2]})["at"], "labels.1")
        self.assertEqual(err("ai", "metrics", {"labels": [1, 0], "scores": [1]})["code"], "bad_args")
        self.assertEqual(err("ai", "metrics", {"labels": [1, 0] * 1001, "scores": [1, 0] * 1001})["code"], "too_large")
        self.assertEqual(err("ai", "metrics", {})["code"], "bad_args")

    def test_descent_first_step(self):
        r = ok("ai", "descent", {"model": "linear", "X": [[1], [2], [3]], "y": [2, 4, 6], "lr": 0.1, "steps": 1})
        h0, h1 = r["history"]
        self.assertEqual((h0["step"], h0["loss"], h0["grad_w"], h0["grad_b"]), (0, 9.3333, [-9.3333], -4.0))
        self.assertEqual((h1["step"], h1["w"], h1["b"]), (1, [0.9333], 0.4))
        self.assertEqual(r["final"]["w"], [0.9333])
        self.assertEqual(len(r["final"]["predictions"]), 3)
        self.assertFalse(r["diverged"])
        self.assertEqual(set(h0), {"step", "loss", "w", "b", "grad_w", "grad_b"})
        self.assertEqual(set(r["final"]), {"w", "b", "loss", "predictions"})

    def test_descent_logistic_and_convergence(self):
        r = ok("ai", "descent", {"model": "logistic", "X": [[0], [1], [2], [3]], "y": [0, 0, 1, 1], "steps": 1})
        self.assertEqual(r["history"][0]["loss"], 0.6931)
        self.assertEqual(r["history"][0]["grad_b"], 0.0)
        r = ok("ai", "descent", {"model": "logistic", "X": [[0], [1], [2], [3]], "y": [0, 0, 1, 1], "lr": 1, "steps": 200})
        self.assertLess(r["final"]["loss"], r["history"][0]["loss"])
        self.assertTrue(all(0 <= p <= 1 for p in r["final"]["predictions"]))
        r = ok("ai", "descent", {"model": "linear", "X": [[0], [1], [2], [3], [4]], "y": [1, 3, 5, 7, 9], "lr": 0.1, "steps": 500})
        self.assertAlmostEqual(r["final"]["w"][0], 2, delta=0.05)
        self.assertAlmostEqual(r["final"]["b"], 1, delta=0.05)

    def test_descent_diverges_and_thins(self):
        r = ok("ai", "descent", {"model": "linear", "X": [[1], [2], [3]], "y": [2, 4, 6], "lr": 10, "steps": 500})
        self.assertTrue(r["diverged"])
        self.assertGreater(r["history"][-1]["loss"], 1e12)
        json.dumps(r, allow_nan=False)
        r = ok("ai", "descent", {"model": "linear", "X": [[1, 2], [2, 1], [3, 5]], "y": [1, 2, 3], "lr": 0.01, "steps": 500})
        self.assertEqual(len(r["history"]), 200)
        self.assertEqual((r["history"][0]["step"], r["history"][-1]["step"]), (0, 500))
        steps = [h["step"] for h in r["history"]]
        self.assertEqual(steps, sorted(set(steps)))

    def test_descent_errors(self):
        base = {"model": "linear", "X": [[1], [2]], "y": [1, 2]}
        self.assertEqual(err("ai", "descent", {**base, "model": "tree"})["at"], "model")
        self.assertEqual(err("ai", "descent", {**base, "y": [1]})["at"], "y")
        self.assertEqual(err("ai", "descent", {**base, "X": [[1], [2, 3]]})["at"], "X")
        self.assertEqual(err("ai", "descent", {**base, "lr": 0})["at"], "lr")
        self.assertEqual(err("ai", "descent", {**base, "lr": 11})["at"], "lr")
        self.assertEqual(err("ai", "descent", {**base, "steps": 501})["at"], "steps")
        self.assertEqual(err("ai", "descent", {**base, "w": [1, 2]})["at"], "w")
        self.assertEqual(err("ai", "descent", {**base, "model": "logistic"})["at"], "y")
        self.assertEqual(err("ai", "descent", {**base, "X": [[1]] * 101, "y": [1] * 101})["code"], "too_large")
        self.assertEqual(err("ai", "descent", {**base, "X": [[1] * 9] * 2})["code"], "too_large")
        self.assertEqual(err("ai", "descent", {**base, "X": [[2e6], [1]]})["code"], "bad_args")


class Systems(unittest.TestCase):
    def test_cache_bits(self):
        r = ok("systems", "cache", {"addresses": ["0x0"]})
        self.assertEqual(r["bits"], {"tag": 19, "index": 7, "offset": 6})
        self.assertEqual(r["sets"], 128)
        exp = practice_systems._np_cache_tag_index_offset({}, {})["expected_bits"]
        self.assertEqual(r["bits"], exp)
        for bits, size, blk, ways in ((32, 1024, 16, 2), (16, 256, 8, 1), (24, 4096, 32, 8), (32, 64, 64, 1)):
            item = practice_systems._np_cache_tag_index_offset(
                {"address_bits": bits, "cache_size_bytes": size, "block_size_bytes": blk, "associativity_ways": ways}, {})
            r = ok("systems", "cache", {"address_bits": bits, "cache_size_bytes": size, "block_size_bytes": blk,
                                        "ways": ways, "addresses": [0]})
            self.assertEqual(r["bits"], item["expected_bits"])

    def test_cache_conflict_misses(self):
        r = ok("systems", "cache", {"address_bits": 16, "cache_size_bytes": 64, "block_size_bytes": 16, "ways": 1,
                                    "addresses": [0, 64, 0, 64]})
        self.assertEqual([s["miss_kind"] for s in r["steps"]], ["compulsory", "compulsory", "conflict", "conflict"])
        self.assertEqual((r["hits"], r["misses"], r["hit_rate"]), (0, 4, 0.0))
        self.assertEqual(r["steps"][1]["evicted_tag"], 0)
        self.assertEqual(r["steps"][2]["evicted_tag"], 1)
        self.assertEqual(set(r["steps"][0]), {"address", "tag", "index", "offset", "hit", "miss_kind", "evicted_tag"})
        r = ok("systems", "cache", {"address_bits": 16, "cache_size_bytes": 64, "block_size_bytes": 16, "ways": 2,
                                    "addresses": ["0x0", "0x40", "0x0", "0x40"]})
        self.assertEqual((r["hits"], r["misses"]), (2, 2))
        self.assertEqual(r["touched_sets"], {"0": [0, 2]})

    def test_cache_capacity_and_policies(self):
        # fully associative, 4 blocks, cycling through 5 blocks: LRU misses every time, after the first pass capacity misses
        addrs = [64 * i for i in range(5)] * 2
        r = ok("systems", "cache", {"cache_size_bytes": 256, "block_size_bytes": 64, "ways": "full", "addresses": addrs})
        self.assertEqual(r["sets"], 1)
        self.assertEqual(r["bits"]["index"], 0)
        self.assertEqual([s["miss_kind"] for s in r["steps"]], ["compulsory"] * 5 + ["capacity"] * 5)
        arg = {"cache_size_bytes": 256, "block_size_bytes": 64, "ways": 2, "addresses": [0, 128, 0, 256, 0]}
        # sets = 2: blocks 0, 2, 0, 4 all in set 0; with LRU block 0 survives block 4, with FIFO it is evicted
        self.assertEqual([s["hit"] for s in ok("systems", "cache", {**arg, "policy": "lru"})["steps"]],
                         [False, False, True, False, True])
        fifo = ok("systems", "cache", {**arg, "policy": "fifo"})["steps"]
        self.assertEqual([s["hit"] for s in fifo], [False, False, True, False, False])
        self.assertEqual(fifo[3]["evicted_tag"], 0)

    def test_cache_errors(self):
        base = {"addresses": [0]}
        for bad, at in (({"cache_size_bytes": 1000}, "cache_size_bytes"), ({"block_size_bytes": 48}, "block_size_bytes"),
                        ({"block_size_bytes": 65536}, "block_size_bytes"), ({"ways": 3}, "ways"),
                        ({"ways": "many"}, "ways"), ({"ways": 1024}, "ways"), ({"policy": "random"}, "policy"),
                        ({"address_bits": 7}, "address_bits"), ({"address_bits": 10}, "address_bits"),
                        ({"addresses": ["0xZZ"]}, "addresses.0"), ({"addresses": [2 ** 32]}, "addresses.0"),
                        ({"addresses": [-1]}, "addresses.0"), ({"addresses": [1.5]}, "addresses.0"),
                        ({"addresses": [True]}, "addresses.0")):
            self.assertEqual(err("systems", "cache", {**base, **bad})["at"], at, bad)
        self.assertEqual(err("systems", "cache", {"addresses": [0] * 257})["code"], "too_large")
        self.assertEqual(err("systems", "cache", {"addresses": []})["code"], "bad_args")
        self.assertEqual(err("systems", "cache", {"cache_size_bytes": 2 ** 31, "addresses": [0]})["code"], "bad_args")

    BANK = {"allocation": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
            "max_claim": [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]], "available": [3, 3, 2]}

    def test_bankers_textbook(self):
        r = ok("systems", "bankers", self.BANK)
        self.assertTrue(r["safe"])
        self.assertEqual(r["sequence"], [1, 3, 0, 2, 4])
        self.assertEqual(r["sequence"], practice_systems._bankers_safe_sequence(
            self.BANK["allocation"], self.BANK["max_claim"], self.BANK["available"]))
        self.assertEqual(r["need"], [[7, 4, 3], [1, 2, 2], [6, 0, 0], [0, 1, 1], [4, 3, 1]])
        self.assertEqual(r["steps"][0], {"process": 1, "need": [1, 2, 2], "work_before": [3, 3, 2], "work_after": [5, 3, 2]})
        self.assertEqual(r["steps"][-1]["work_after"], [10, 5, 7])
        self.assertNotIn("request_result", r)

    def test_bankers_requests_chain(self):
        r = ok("systems", "bankers", {**self.BANK, "request": {"process": 1, "vector": [1, 0, 2]}})
        rr = r["request_result"]
        self.assertEqual((rr["granted"], rr["reason"]), (True, "ok"))
        self.assertEqual(rr["state_after"]["available"], [2, 3, 0])
        self.assertEqual(rr["state_after"]["allocation"][1], [3, 0, 2])
        st = rr["state_after"]
        nxt = {"allocation": st["allocation"], "max_claim": self.BANK["max_claim"], "available": st["available"]}
        r = ok("systems", "bankers", {**nxt, "request": {"process": 4, "vector": [3, 3, 0]}})
        self.assertEqual(r["request_result"], {"granted": False, "reason": "must_wait"})
        r = ok("systems", "bankers", {**nxt, "request": {"process": 0, "vector": [0, 2, 0]}})
        self.assertEqual(r["request_result"], {"granted": False, "reason": "unsafe"})
        r = ok("systems", "bankers", {**nxt, "request": {"process": 3, "vector": [1, 0, 0]}})
        self.assertEqual(r["request_result"]["reason"], "exceeds_need")

    def test_bankers_unsafe_and_errors(self):
        r = ok("systems", "bankers", {"allocation": [[1], [1]], "max_claim": [[3], [3]], "available": [0]})
        self.assertEqual((r["safe"], r["sequence"], r["steps"]), (False, [], []))
        self.assertEqual(r["sequence"], practice_systems._bankers_safe_sequence([[1], [1]], [[3], [3]], [0]))
        self.assertEqual(err("systems", "bankers", {**self.BANK, "available": [3, 3]})["at"], "allocation")
        self.assertEqual(err("systems", "bankers", {**self.BANK, "available": "x"})["at"], "available")
        self.assertEqual(err("systems", "bankers", {**self.BANK, "max_claim": [[0, 0, 0]] * 5})["at"], "max_claim")
        self.assertEqual(err("systems", "bankers", {**self.BANK, "max_claim": [[7, 5, 3]]})["at"], "max_claim")
        self.assertEqual(err("systems", "bankers", {**self.BANK, "request": {"process": 9, "vector": [0, 0, 0]}})["at"], "request.process")
        self.assertEqual(err("systems", "bankers", {**self.BANK, "request": {"process": 1, "vector": [0]}})["at"], "request.vector")
        self.assertEqual(err("systems", "bankers", {**self.BANK, "allocation": [[0, 0, 0]] * 13, "max_claim": [[0, 0, 0]] * 13})["code"], "bad_args")


class Stats(unittest.TestCase):
    Z = {"mean1": 52, "sd1": 8, "n1": 40, "mean2": 48, "sd2": 6, "n2": 50}

    def test_z_matches_practice(self):
        r = ok("stats", "two_sample", {**self.Z, "test": "z"})
        item = practice_stats._np_hypothesis_test_two_sample(
            {"mean1": 52, "std1": 8, "n1": 40, "mean2": 48, "std2": 6, "n2": 50}, {})
        self.assertEqual(r["statistic"], 2.6261)
        self.assertEqual(r["statistic"], item["statistic_expected"])
        self.assertEqual(r["reject"], item["reject_null_expected"])
        self.assertAlmostEqual(r["p_value"], 0.0086, places=4)
        self.assertAlmostEqual(r["critical"], 1.96, places=3)
        self.assertIsNone(r["df"])
        self.assertAlmostEqual(r["ci"][0], 4 - 1.96 * 1.5232, places=2)
        self.assertEqual(len(r["curve"]), 101)
        self.assertEqual((r["curve"][0]["x"], r["curve"][100]["x"], r["curve"][50]["y"]), (-4.5, 4.5, 0.3989))
        self.assertEqual(set(r), {"statistic", "df", "p_value", "critical", "reject", "ci", "se", "curve"})

    def test_welch(self):
        r = ok("stats", "two_sample", {**self.Z, "test": "welch"})
        self.assertAlmostEqual(r["df"], 70.62, places=2)
        self.assertAlmostEqual(r["p_value"], 0.0106, places=4)
        self.assertTrue(r["reject"])
        self.assertAlmostEqual(r["critical"], 1.994, places=3)

    def test_t_textbook_p_values(self):
        for df, t, p, n in ((10, 2.228, 0.05, 6), (20, 2.845, 0.01, 11)):
            se = math.sqrt(2 / n)
            r = ok("stats", "two_sample", {"test": "pooled", "mean1": t * se, "sd1": 1, "n1": n, "mean2": 0, "sd2": 1, "n2": n})
            self.assertEqual(r["df"], df)
            self.assertAlmostEqual(r["statistic"], t, places=3)
            self.assertAlmostEqual(r["p_value"], p, delta=p * 0.01)
        # critical values: t(.975, 10) = 2.2281, t(.975, 1) = 12.7062
        r = ok("stats", "two_sample", {"test": "pooled", "mean1": 1, "sd1": 1, "n1": 6, "mean2": 0, "sd2": 1, "n2": 6})
        self.assertAlmostEqual(r["critical"], 2.2281, places=3)
        r = ok("stats", "two_sample", {"test": "pooled", "mean1": 1, "sd1": 1, "n1": 2, "mean2": 0, "sd2": 1, "n2": 2, "alpha": 0.05})
        self.assertAlmostEqual(r["critical"], 4.3027, places=3)  # df 2

    def test_alternatives_and_samples(self):
        base = {**self.Z, "test": "z"}
        two = ok("stats", "two_sample", base)["p_value"]
        gr = ok("stats", "two_sample", {**base, "alternative": "greater"})
        le = ok("stats", "two_sample", {**base, "alternative": "less"})
        self.assertAlmostEqual(gr["p_value"], two / 2, places=5)
        self.assertAlmostEqual(le["p_value"], 1 - two / 2, places=5)
        self.assertFalse(le["reject"])
        self.assertAlmostEqual(gr["critical"], 1.6449, places=3)
        self.assertAlmostEqual(le["critical"], -1.6449, places=3)
        x, y = [5.1, 4.9, 6.2, 5.8, 6.0], [4.1, 4.4, 5.0, 3.9, 4.6, 4.2]
        r = ok("stats", "two_sample", {"test": "welch", "x": x, "y": y})
        mean = lambda v: sum(v) / len(v)
        sd = lambda v: math.sqrt(sum((a - mean(v)) ** 2 for a in v) / (len(v) - 1))
        r2 = ok("stats", "two_sample", {"test": "welch", "mean1": mean(x), "sd1": sd(x), "n1": 5, "mean2": mean(y), "sd2": sd(y), "n2": 6})
        self.assertEqual(r, r2)

    def test_far_tails_keep_precision(self):
        z = {"test": "z", "mean1": 30, "sd1": 1, "n1": 2, "mean2": 0, "sd2": 0, "n2": 2}
        se = math.sqrt(0.5)
        z.update(mean1=30 * se)  # z = 30; at 38.7 the tail (1e-326) is below the smallest double and reads 0
        gr = ok("stats", "two_sample", {**z, "alternative": "greater"})
        self.assertAlmostEqual(gr["statistic"], 30, places=3)
        self.assertGreater(gr["p_value"], 0)
        self.assertLess(gr["p_value"], 1e-100)
        lo = ok("stats", "two_sample", {**z, "mean1": -z["mean1"], "alternative": "less"})
        self.assertEqual(lo["p_value"], gr["p_value"])  # symmetric: P(Z < -30) = P(Z > 30)
        self.assertTrue(lo["reject"])
        self.assertEqual(ok("stats", "two_sample", {**z, "alternative": "less"})["p_value"], 1.0)
        self.assertEqual(ok("stats", "two_sample", {**z, "mean1": -z["mean1"], "alternative": "greater"})["p_value"], 1.0)
        far = ok("stats", "two_sample", {**z, "mean1": 38.7 * se, "alternative": "less"})
        self.assertEqual(far["p_value"], 1.0)
        two = ok("stats", "two_sample", z)
        self.assertAlmostEqual(two["p_value"] / gr["p_value"], 2, places=4)
        t = ok("stats", "two_sample", {**z, "test": "pooled", "mean1": -50, "alternative": "less"})
        self.assertGreater(t["p_value"], 0)
        self.assertLess(t["p_value"], 0.01)

    def test_t_helpers(self):
        self.assertAlmostEqual(kit_tools._t_sf(0, 7), 0.5, places=12)
        self.assertAlmostEqual(kit_tools._t_sf(1, 1), 0.25, places=10)  # Cauchy: 1/2 - atan(1)/pi
        self.assertAlmostEqual(kit_tools._t_sf(-1, 1), 0.75, places=10)
        self.assertAlmostEqual(kit_tools._t_sf(1.96, 1e7), kit_tools._norm_sf(1.96))
        self.assertAlmostEqual(kit_tools._t_sf(2, 5e5), kit_tools._norm_sf(2), places=5)

    def test_two_sample_errors(self):
        for bad, at in (({"test": "f"}, "test"), ({"alternative": "x"}, "alternative"), ({"alpha": 0.6}, "alpha"),
                        ({"alpha": 0}, "alpha"), ({"n1": 1}, "n1"), ({"sd2": -1}, "sd2"), ({"mean1": "a"}, "mean1")):
            self.assertEqual(err("stats", "two_sample", {**self.Z, **bad})["at"], at, bad)
        self.assertEqual(err("stats", "two_sample", {**self.Z, "sd1": 0, "sd2": 0})["code"], "bad_args")
        self.assertEqual(err("stats", "two_sample", {"x": [1, 1], "y": [2, 2]})["code"], "bad_args")
        self.assertEqual(err("stats", "two_sample", {"x": [1], "y": [2, 3]})["code"], "bad_args")
        self.assertEqual(err("stats", "two_sample", {"x": [1.0] * 1001, "y": [2, 3]})["code"], "too_large")

    def test_markov_textbook(self):
        r = ok("stats", "markov", {"P": [[0.7, 0.3], [0.1, 0.9]]})
        self.assertEqual([s["value"] for s in r["stationary"]], [0.25, 0.75])
        item = practice_stats._np_markov_steady_state({"alpha": 0.3, "beta": 0.1}, {})
        self.assertEqual([s["value"] for s in r["stationary"]], item["steady_state_expected"])
        self.assertEqual([s["exact"] for s in r["stationary"]], ["1/4", "3/4"])
        self.assertTrue(r["unique"] and r["irreducible"] and r["aperiodic"])
        self.assertEqual((r["classes"], r["recurrent"], r["period"], r["absorbing"]), ([[0, 1]], [True], [1], []))
        self.assertEqual(len(r["distribution"]), 21)
        self.assertEqual(r["distribution"][0], [1.0, 0.0])
        self.assertEqual(r["distribution"][1], [0.7, 0.3])
        self.assertAlmostEqual(r["distribution"][20][0], 0.25, delta=0.001)
        self.assertEqual(set(r), {"stationary", "unique", "classes", "recurrent", "absorbing", "period", "irreducible",
                                  "aperiodic", "distribution"})

    def test_markov_cases(self):
        r = ok("stats", "markov", {"P": [[.5, .5, 0], [.25, .5, .25], [0, .5, .5]]})
        self.assertEqual([s["exact"] for s in r["stationary"]], ["1/4", "1/2", "1/4"])
        r = ok("stats", "markov", {"P": [[0, 1], [1, 0]], "steps": 3, "start": [0.5, 0.5]})
        self.assertEqual((r["period"], r["unique"], r["aperiodic"], r["irreducible"]), ([2], True, False, True))
        self.assertEqual([s["exact"] for s in r["stationary"]], ["1/2", "1/2"])
        self.assertEqual(len(r["distribution"]), 4)
        r = ok("stats", "markov", {"P": [[1, 0], [0, 1]]})
        self.assertEqual((r["unique"], r["stationary"], r["absorbing"], r["classes"], r["recurrent"]),
                         (False, None, [0, 1], [[0], [1]], [True, True]))
        self.assertFalse(r["irreducible"])
        # transient state feeding an absorbing one: unique stationary distribution on the absorbing state
        r = ok("stats", "markov", {"P": [[0.5, 0.5], [0, 1]]})
        self.assertEqual([s["exact"] for s in r["stationary"]], ["0", "1"])
        self.assertEqual((r["recurrent"], r["absorbing"], r["period"]), ([False, True], [1], [1, 1]))
        r = ok("stats", "markov", {"P": [[0, 1, 0], [0, 0, 1], [1, 0, 0]]})
        self.assertEqual(r["period"], [3])
        # a row that sums to 1 only within the tolerance is rescaled exactly
        r = ok("stats", "markov", {"P": [[0.3333333333, 0.3333333333, 0.3333333333], [0.5, 0.5, 0], [0, 0.5, 0.5]]})
        self.assertEqual(sum(Fraction(s["exact"]) for s in r["stationary"]), 1)

    def test_markov_errors(self):
        self.assertEqual(err("stats", "markov", {"P": [[0.5, 0.4], [0.5, 0.5]]})["at"], "P.0")
        self.assertEqual(err("stats", "markov", {"P": [[0.5, 0.5], [0.5, 0.6]]})["at"], "P.1")
        self.assertEqual(err("stats", "markov", {"P": [[1.5, -0.5], [0.5, 0.5]]})["at"], "P.0.0")
        self.assertEqual(err("stats", "markov", {"P": [[1, 0, 0], [0, 1]]})["at"], "P.0")
        self.assertEqual(err("stats", "markov", {"P": [[1, 0], [0, 1]], "steps": 101})["at"], "steps")
        self.assertEqual(err("stats", "markov", {"P": [[1, 0], [0, 1]], "start": [1]})["at"], "start")
        self.assertEqual(err("stats", "markov", {"P": [[1, 0], [0, 1]], "start": [0.5, 0.6]})["at"], "start")
        self.assertEqual(err("stats", "markov", {"P": [[1]] * 11})["code"], "too_large")


class Bio(unittest.TestCase):
    def test_local_textbook(self):
        r = ok("bio", "align", {"seq1": "TGTTACGG", "seq2": "GGTTGACTA", "mode": "local", "match": 3, "mismatch": -3, "gap": -2})
        self.assertEqual((r["score"], r["aligned1"], r["aligned2"]), (13, "GTT-AC", "GTTGAC"))
        self.assertEqual(r["midline"], "||| ||")
        self.assertEqual((r["gaps"], r["identity"]), (1, round(5 / 6, 4)))
        self.assertEqual((r["start"], r["end"]), ([2, 2], [6, 7]))
        self.assertEqual(r["path"][0], [1, 1])
        self.assertEqual(r["path"][-1], [6, 7])
        self.assertEqual(len(r["path"]), len(r["aligned1"]) + 1)
        self.assertEqual(len(r["matrix"]), 9)
        self.assertEqual(max(max(row) for row in r["matrix"]), 13)
        self.assertEqual(set(r), {"score", "aligned1", "aligned2", "midline", "identity", "gaps", "start", "end", "matrix", "path"})

    def test_global_textbook(self):
        r = ok("bio", "align", {"seq1": "GCATGCG", "seq2": "GATTACA", "mode": "global", "match": 1, "mismatch": -1, "gap": -1})
        self.assertEqual((r["score"], r["aligned1"], r["aligned2"]), (0, "GCA-TGCG", "G-ATTACA"))
        self.assertEqual(len(r["midline"]), len(r["aligned1"]))
        self.assertEqual((r["start"], r["end"]), ([1, 1], [7, 7]))
        self.assertEqual(r["path"][0], [0, 0])
        self.assertEqual(r["path"][-1], [7, 7])
        self.assertEqual(r["matrix"][7][7], 0)
        # no gaps in the alignment strings other than "-", the strings drop back to the inputs
        self.assertEqual(r["aligned1"].replace("-", ""), "GCATGCG")
        self.assertEqual(r["aligned2"].replace("-", ""), "GATTACA")

    def test_local_matches_practice_bio(self):
        rnd = random.Random(7)
        for _ in range(50):
            s1 = "".join(rnd.choice("ACGT") for _ in range(rnd.randint(1, 20)))
            s2 = "".join(rnd.choice("ACGT") for _ in range(rnd.randint(1, 20)))
            mt, mm, gp = rnd.randint(1, 5), rnd.randint(1, 5), rnd.randint(1, 5)
            item = practice_bio._np_smith_waterman_align(
                {"seq1": s1, "seq2": s2, "match_score": mt, "mismatch_penalty": mm, "gap_penalty": gp}, {})
            r = ok("bio", "align", {"seq1": s1, "seq2": s2, "mode": "local", "match": mt, "mismatch": -mm, "gap": -gp})
            self.assertEqual(r["score"], item["max_score"], (s1, s2, mt, mm, gp))
            # the alignment reproduces its own score
            sc = sum(-gp if "-" in (p, q) else (mt if p == q else -mm) for p, q in zip(r["aligned1"], r["aligned2"]))
            self.assertEqual(sc, r["score"])

    def test_align_edges(self):
        r = ok("bio", "align", {"seq1": "AAA", "seq2": "CCC", "mode": "local"})
        self.assertEqual((r["score"], r["aligned1"], r["aligned2"], r["midline"], r["path"], r["start"], r["end"], r["identity"]),
                         (0, "", "", "", [], None, None, 0.0))
        r = ok("bio", "align", {"seq1": " a c g t ", "seq2": "acgt"})
        self.assertEqual((r["score"], r["aligned1"], r["identity"]), (8, "ACGT", 1.0))
        r = ok("bio", "align", {"seq1": "A", "seq2": "AAAA", "mode": "global"})
        self.assertEqual((r["aligned1"].replace("-", ""), len(r["aligned2"])), ("A", 4))
        big = ok("bio", "align", {"seq1": "A" * 13, "seq2": "A"})
        self.assertIsNone(big["matrix"])
        self.assertEqual(err("bio", "align", {"seq1": "AC1", "seq2": "AC"})["at"], "seq1")
        self.assertEqual(err("bio", "align", {"seq1": "AC", "seq2": "ÄC"})["at"], "seq2")
        self.assertEqual(err("bio", "align", {"seq1": "", "seq2": "AC"})["at"], "seq1")
        self.assertEqual(err("bio", "align", {"seq1": "A" * 301, "seq2": "A"})["code"], "too_large")
        self.assertEqual(err("bio", "align", {"seq1": "A", "seq2": "A", "mode": "semi"})["at"], "mode")
        self.assertEqual(err("bio", "align", {"seq1": "A", "seq2": "A", "gap": -101})["at"], "gap")
        self.assertEqual(err("bio", "align", {"seq1": "A", "seq2": "A", "match": 1.5})["at"], "match")

    def test_orf_forward_and_reverse(self):
        r = ok("bio", "orf", {"dna": "ATGGCCTAA", "min_codons": 1})
        self.assertEqual(r["orfs"], [{"frame": "+1", "start": 1, "end": 9, "length_nt": 9, "protein": "MA"}])
        self.assertEqual(r["frames"][0], {"frame": "+1", "protein": "MA*"})
        self.assertEqual([f["frame"] for f in r["frames"]], ["+1", "+2", "+3", "-1", "-2", "-3"])
        self.assertFalse(r["truncated"])
        r = ok("bio", "orf", {"dna": "CTATTTCAT", "min_codons": 1})
        self.assertEqual(r["orfs"], [{"frame": "-1", "start": 9, "end": 1, "length_nt": 9, "protein": "MK"}])
        self.assertEqual(ok("bio", "orf", {"dna": "CTATTTCAT", "min_codons": 1, "strands": "forward"})["orfs"], [])
        self.assertEqual(len(ok("bio", "orf", {"dna": "CTATTTCAT", "strands": "forward"})["frames"]), 3)
        self.assertEqual(ok("bio", "orf", {"dna": "ATGGCCTAA"})["orfs"], [])  # default min is 10 amino acids

    def test_orf_six_frames_and_rules(self):
        dna = "GATGAAATGCCCTGAATGTAGCC"
        r = ok("bio", "orf", {"dna": dna, "min_codons": 1})
        # frame +2: ATG AAA TGC CCT GAA TGT AGC C -> no stop; frame +3 (offset 2): TGA AAT GCC CTG AAT GTA GCC
        by = {f["frame"]: f["protein"] for f in r["frames"]}
        self.assertEqual(by["+2"], "MKCPECS")
        self.assertEqual(len(r["frames"]), 6)
        # only the first ATG after a stop starts the ORF: ATG ATG AAA TAA -> MMK
        r = ok("bio", "orf", {"dna": "atg atg aaa taa", "min_codons": 1, "strands": "forward"})
        self.assertEqual(r["orfs"][0]["protein"], "MMK")
        self.assertEqual(ok("bio", "orf", {"dna": "AUGAAAUAA", "min_codons": 1})["orfs"][0]["protein"], "MK")
        # no stop: no ORF
        self.assertEqual(ok("bio", "orf", {"dna": "ATGAAAAAA", "min_codons": 1})["orfs"], [])
        # sorting: longest first
        r = ok("bio", "orf", {"dna": "ATGTAA" + "CC" + "ATGAAAGGGTAA", "min_codons": 1, "strands": "forward"})
        self.assertEqual([o["protein"] for o in r["orfs"]], ["MKG", "M"])

    def test_orf_matches_practice_bio(self):
        rnd = random.Random(11)
        checked = 0
        for _ in range(200):
            dna = "".join(rnd.choice("ACGT") for _ in range(rnd.randint(9, 120)))
            item = practice_bio._np_orf_finder_translate({"dna_sequence": dna}, {})
            r = ok("bio", "orf", {"dna": dna, "min_codons": 1, "strands": "forward"})
            if item is None:
                self.assertEqual(r["orfs"], [], dna)
                continue
            checked += 1
            top = r["orfs"][0]
            self.assertEqual(top["protein"], item["protein_sequence"], dna)
            self.assertEqual(top["start"] - 1, item["start_index"], dna)
        self.assertGreater(checked, 20)

    def test_orf_errors(self):
        self.assertEqual(err("bio", "orf", {"dna": "ATGX"})["at"], "dna")
        self.assertEqual(err("bio", "orf", {"dna": "AT"})["at"], "dna")
        self.assertEqual(err("bio", "orf", {"dna": 5})["at"], "dna")
        self.assertEqual(err("bio", "orf", {"dna": "A" * 20001})["code"], "too_large")
        self.assertEqual(err("bio", "orf", {"dna": "A" * 300_000})["code"], "too_large")
        self.assertEqual(err("bio", "orf", {"dna": "ATG", "min_codons": 0})["at"], "min_codons")
        self.assertEqual(err("bio", "orf", {"dna": "ATG", "strands": "minus"})["at"], "strands")


class Hardening(unittest.TestCase):
    def test_all_present(self):
        for kind, ops in STEM.items():
            self.assertEqual(tuple(kit_tools.TOOLS[kind]), ops)
        g = kit_tools.guide()
        for kind, ops in STEM.items():
            for op in ops:
                self.assertGreater(len(g[kind][op]), 200, (kind, op))
        self.assertEqual(len(kit_tools.TOOLS), 10)

    def test_junk_never_raises(self):
        junk = [None, [], [1], "x", 5, 1.5, True, {}, {"a": None}, {"elements": "x"}, {"elements": [None]},
                {"elements": [{"type": "R"}]}, {"num": [], "den": []}, {"num": "x", "den": [1]}, {"matrix": 5},
                {"matrix": [[1e30, 1], [1, 1]]}, {"labels": [1], "scores": [1]}, {"model": "linear", "X": [[]], "y": [1]},
                {"addresses": ["zz"]}, {"addresses": [[]]}, {"allocation": [[1e400]]}, {"allocation": [["a"]], "available": [1]},
                {"P": [[1, 0], [0, 1, 5]]}, {"P": [[float("nan"), 1], [1, 0]]}, {"P": "x"}, {"mean1": 1e308, "sd1": 1e308, "n1": 5,
                "mean2": -1e308, "sd2": 1, "n2": 5}, {"seq1": None, "seq2": 5}, {"seq1": "A" * 100000, "seq2": "A"},
                {"dna": ["A"]}, {"dna": "ATG" * 100000}, {"x": [1e308, -1e308], "y": [1, 2]},
                {"elements": [{"type": "R", "a": "a", "b": "0", "value": 10 ** 500}]},
                {"model": "linear", "X": [[1e6] * 8] * 100, "y": [1e6] * 100, "lr": 10, "steps": 500},
                {"ways": 10 ** 40, "addresses": [0]}, {"address_bits": 10 ** 40}]
        rnd = random.Random(5)
        for kind, ops in STEM.items():
            for op in ops:
                for j in junk + [{"x": rnd.random(), "y": [rnd.random()], "n1": rnd.random()} for _ in range(5)]:
                    r = run(kind, op, j)
                    self.assertEqual(r["ok"], "result" in r, (kind, op, j))
                    if r["ok"]:
                        json.dumps(r, allow_nan=False)

    def test_random_valid_inputs_are_finite(self):
        rnd = random.Random(9)
        for _ in range(30):
            r = run("ee", "bode", {"num": [rnd.uniform(-5, 5) for _ in range(rnd.randint(1, 4))],
                                   "den": [rnd.choice([0, 1, 2.5, -3]) for _ in range(rnd.randint(1, 5))]})
            self.assertIn("ok", r)
            if r["ok"]:
                json.dumps(r, allow_nan=False)
            P = []
            for _ in range(3):
                v = [rnd.randint(0, 5) for _ in range(3)]
                v = v if sum(v) else [1, 0, 0]
                P.append([Fraction(x, sum(v)) for x in v])
            P = [[float(x) for x in row] for row in P]
            r = run("stats", "markov", {"P": P})
            if r["ok"] and r["result"]["stationary"]:
                self.assertEqual(sum(Fraction(s["exact"]) for s in r["result"]["stationary"]), 1)


class WorstCase(unittest.TestCase):
    def under_a_second(self, kind, op, args):
        t = time.perf_counter()
        r = run(kind, op, args)
        dt = time.perf_counter() - t
        self.assertTrue(r["ok"], r)
        self.assertLess(dt, 1.0, f"{kind}.{op} took {dt:.2f}s")
        return r["result"]

    def test_align_300(self):
        rnd = random.Random(1)
        for mode in ("global", "local"):
            s1 = "".join(rnd.choice("ACGT") for _ in range(300))
            s2 = "".join(rnd.choice("ACGT") for _ in range(300))
            self.under_a_second("bio", "align", {"seq1": s1, "seq2": s2, "mode": mode})
        self.under_a_second("bio", "align", {"seq1": "A" * 300, "seq2": "A" * 300, "mode": "local"})

    def test_orf_20000(self):
        rnd = random.Random(2)
        dna = "".join(rnd.choice("ACGT") for _ in range(20000))
        r = self.under_a_second("bio", "orf", {"dna": dna, "min_codons": 1})
        self.assertEqual(r["frames"], [])
        self.assertLessEqual(len(r["orfs"]), 100)
        self.assertTrue(r["truncated"])
        self.under_a_second("bio", "orf", {"dna": "ATG" * 6666, "min_codons": 1})

    def test_dc_12_nodes(self):
        els = [{"type": "V", "a": "1", "b": "0", "value": 5}]
        for i in range(1, 12):
            els.append(R(str(i), str((i + 1) % 12), 1000 + i))
            els.append(R(str(i), "0", 2000 + 7 * i))
        els = els[:30]
        r = self.under_a_second("ee", "dc_solve", {"elements": els})
        self.assertTrue(r["solvable"])
        self.assertEqual(sum(Fraction(e["power_exact"]) for e in r["elements"]), 0)
        vs = [{"type": "V", "a": str(i + 1), "b": "0", "value": 1.1 * (i + 1)} for i in range(10)]
        vs += [R(str(i + 1), "x", 1.5 + i) for i in range(10)] + [R("x", "0", 0.001)]
        self.under_a_second("ee", "dc_solve", {"elements": vs})

    def test_descent_max(self):
        rnd = random.Random(3)
        X = [[rnd.uniform(-1, 1) for _ in range(8)] for _ in range(100)]
        y = [rnd.uniform(-1, 1) for _ in range(100)]
        self.under_a_second("ai", "descent", {"model": "linear", "X": X, "y": y, "lr": 0.05, "steps": 500})
        self.under_a_second("ai", "descent", {"model": "logistic", "X": X, "y": [float(v > 0) for v in y], "lr": 0.5, "steps": 500})

    def test_markov_10_states(self):
        rnd = random.Random(4)
        P = []
        for _ in range(10):
            v = [rnd.randint(1, 9) for _ in range(10)]
            P.append([x / sum(v) for x in v])
        r = self.under_a_second("stats", "markov", {"P": P, "steps": 100})
        self.assertTrue(r["unique"])
        self.under_a_second("stats", "markov", {"P": [[1 / 10] * 10] * 10, "steps": 100})

    def test_others_max(self):
        rnd = random.Random(5)
        self.under_a_second("ee", "bode", {"num": [1] * 7, "den": [1] * 7, "points": 401, "w_max": 1e9})
        self.under_a_second("ai", "metrics", {"matrix": [[rnd.randint(0, 10 ** 9) for _ in range(10)] for _ in range(10)]})
        self.under_a_second("ai", "metrics", {"labels": [rnd.randint(0, 1) for _ in range(2000)], "scores": [rnd.random() for _ in range(2000)]})
        self.under_a_second("systems", "cache", {"addresses": [rnd.randrange(2 ** 32) for _ in range(256)], "ways": "full",
                                                 "cache_size_bytes": 2 ** 30, "block_size_bytes": 1})
        self.under_a_second("systems", "cache", {"addresses": [rnd.randrange(2 ** 20) for _ in range(256)], "address_bits": 64})
        big = [[rnd.randint(0, 9) for _ in range(8)] for _ in range(12)]
        self.under_a_second("systems", "bankers", {"allocation": big, "max_claim": [[v + 5 for v in r] for r in big],
                                                   "available": [20] * 8, "request": {"process": 0, "vector": [1] * 8}})
        self.under_a_second("stats", "two_sample", {"test": "welch", "x": [rnd.random() for _ in range(1000)], "y": [rnd.random() for _ in range(1000)]})
        self.under_a_second("stats", "two_sample", {"test": "welch", "mean1": 1, "sd1": 1e-9, "n1": 2, "mean2": 0, "sd2": 1e9, "n2": 10 ** 9,
                                                    "alpha": 1e-300})
        self.under_a_second("stats", "two_sample", {"test": "pooled", "mean1": 1, "sd1": 3, "n1": 2, "mean2": 0, "sd2": 3, "n2": 2, "alpha": 1e-12})


class Route(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(server.app, base_url=LOCAL)
        server._rate_hits.clear()

    def test_stem_kinds_over_http(self):
        r = self.c.post("/api/kits/stats/tool", json={"op": "markov", "args": {"P": [[0.7, 0.3], [0.1, 0.9]]}})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual([s["exact"] for s in body["result"]["stationary"]], ["1/4", "3/4"])
        for kind, ops in STEM.items():
            r = self.c.post(f"/api/kits/{kind}/tool", json={"op": "nope"})
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (200, "bad_op"))
        r = self.c.post("/api/kits/bio/tool", json={"op": "orf", "args": {"dna": "ATGGCCTAA", "min_codons": 1}})
        self.assertEqual(r.json()["result"]["orfs"][0]["protein"], "MA")

    def test_unknown_kinds_still_404_and_guide(self):
        for kind in ("alchemy", "art_history", "physics", "math"):
            self.assertEqual(self.c.post(f"/api/kits/{kind}/tool", json={"op": "x"}).status_code, 404)
        g = self.c.get("/api/kits/tools").json()
        for kind, ops in STEM.items():
            self.assertEqual(tuple(g[kind]), ops)

    def test_mcp_enum(self):
        import mcp_tools_kits
        seen = {}
        def S(**kw):
            return kw
        def STR(desc, enum=None, optional=False):
            return {"enum": enum}
        out = mcp_tools_kits.tools(lambda *a, **k: {}, str, S, STR, lambda *a, **k: None, lambda *a, **k: None)
        spec = [t for t in out if t[0] == "kit_tool"][0][2]
        self.assertEqual(spec["kind"]["enum"], list(kit_tools.TOOLS))
        self.assertTrue(set(STEM) <= set(spec["kind"]["enum"]))


if __name__ == "__main__":
    unittest.main()
