"""Review fixes from 2026-11-16/17: the user export redacts kit answer keys, the Banker's grader demands a real
permutation, the instant-runoff count is deterministic, and no kit grader crashes or leaks its key on junk input."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import LOCAL, TestClient, server  # noqa: E402
import db  # noqa: E402
import practice_polity  # noqa: E402
import practice_systems  # noqa: E402
from test_kits_backend import seed_kits  # noqa: E402

BANKER_SAFE = {"type": "deadlock_bankers", "prompt": "Safe?",
               "allocation": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
               "max_claim": [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]],
               "available": [3, 3, 2]}


def _norm(raw):
    return practice_systems.NORMALIZERS[raw["type"]](raw, {"id": "p1", "type": raw["type"], "prompt": raw["prompt"]})


class BankersTest(unittest.TestCase):
    def test_classic_state_is_safe(self):
        item = _norm(BANKER_SAFE)
        self.assertTrue(item["is_safe"])
        self.assertEqual(sorted(item["safe_sequence"]), [0, 1, 2, 3, 4])

    def test_repeating_a_process_is_not_a_sequence(self):
        item = _norm(BANKER_SAFE)
        r = practice_systems.GRADERS["deadlock_bankers"](item, {"is_safe": True, "sequence": [1, 1, 1, 1, 1]})
        self.assertFalse(r["ok"])
        self.assertNotIn(json.dumps(item["safe_sequence"]), json.dumps(r))

    def test_any_valid_order_counts(self):
        item = _norm(BANKER_SAFE)
        for seq in ([1, 3, 4, 0, 2], [1, 3, 0, 2, 4], [3, 1, 4, 2, 0]):
            self.assertTrue(practice_systems.GRADERS["deadlock_bankers"](item, {"is_safe": True, "sequence": seq})["ok"], seq)

    def test_stalling_order_is_wrong(self):
        item = _norm(BANKER_SAFE)
        r = practice_systems.GRADERS["deadlock_bankers"](item, {"is_safe": True, "sequence": [0, 1, 2, 3, 4]})
        self.assertFalse(r["ok"])
        self.assertEqual(r["score"], 0.5)

    def test_bad_shapes_are_dropped(self):
        for bad in ({"allocation": [[1, 0]], "max_claim": [[1, 0, 0]], "available": [1, 1]},  # ragged
                    {"allocation": [[2]], "max_claim": [[1]], "available": [1]},  # max below allocation
                    {"allocation": [["x"]], "max_claim": [[1]], "available": [1]},
                    {"allocation": [[-1]], "max_claim": [[1]], "available": [1]},
                    {"allocation": [[0]] * 13, "max_claim": [[1]] * 13, "available": [1]}):
            self.assertIsNone(_norm({"type": "deadlock_bankers", "prompt": "?", **bad}), bad)


class InstantRunoffTest(unittest.TestCase):
    def test_tie_for_last_drops_alphabetically_first_whatever_the_order(self):
        ballots = [["Cy"], ["Cy"], ["Cy"], ["Bo"], ["Bo"], ["Al", "Bo"], ["Dee", "Al"]]
        runs = [practice_polity._calc_irv(cands, ballots)
                for cands in (["Al", "Bo", "Cy", "Dee"], ["Dee", "Cy", "Bo", "Al"], ["Bo", "Dee", "Al", "Cy"])]
        orders = {tuple(elim) for _, elim, _ in runs}
        self.assertEqual(orders, {("Al", "Dee", "Bo")} if runs[0][2] == "Cy" else orders)
        self.assertEqual(len(orders), 1)
        self.assertEqual(runs[0][1][0], "Al")  # Al and Dee tie on 1 first preference: Al goes first

    def test_final_two_tie_goes_to_alphabetically_first(self):
        _, _, winner = practice_polity._calc_irv(["Zed", "Amy"], [["Zed"], ["Amy"]])
        self.assertEqual(winner, "Amy")

    def test_junk_elimination_order_does_not_crash(self):
        item = practice_polity.NORMALIZERS["instant_runoff_tally"](
            {"ballots": [["A", "B"], ["B"], ["A"]]}, {"id": "p1", "type": "instant_runoff_tally", "prompt": "?"})
        r = practice_polity.GRADERS["instant_runoff_tally"](item, {"winner": 5, "elimination_order": 7})
        self.assertFalse(r["ok"])


class GraderFuzzTest(unittest.TestCase):
    JUNK = [None, "", 1.5, -1, 1e308, "x" * 5000, [], [None], [[]], {}, {"a": 1}, {"is_safe": True, "sequence": "abc"},
            {"answer": None}, {"winner": 5, "elimination_order": 7}, [1, "a", None], {"labels": {"x": 1}}, [{"id": None}]]

    def test_no_grader_crashes_or_echoes_its_key_on_junk(self):
        for t in seed_kits.build_topics():
            for item in server.normalize_practice(t.get("practice", [])):
                grader = server.PRACTICE_GRADERS.get(item["type"])
                if not grader:
                    continue
                keys = [json.dumps(item[k]) for k in server.secret_fields_for(item["type"])
                        if k in item and item[k] not in (None, "", [], {}, True, False, 0, 1)]
                for junk in self.JUNK:
                    with self.subTest(type=item["type"], junk=repr(junk)[:30]):
                        r = grader(item, junk)
                        self.assertEqual(set(r), {"ok", "score", "feedback", "details"})
                        if not r["ok"]:
                            out = json.dumps(r)
                            for k in keys:
                                if len(k) > 3:
                                    self.assertNotIn(k, out)


class RegisterTraceLimitsTest(unittest.TestCase):
    BASE = {"id": "p1", "type": "assembly_reg_trace", "prompt": "?"}

    def norm(self, **raw):
        return practice_systems.NORMALIZERS["assembly_reg_trace"](raw, dict(self.BASE))

    def test_normal_trace_still_works(self):
        item = self.norm(instructions=["addi x1 x0 5", "slli x2 x1 31"], initial_registers={"x0": 0})
        self.assertEqual(item["final_registers"]["x2"], (5 << 31) & 0xFFFFFFFF)

    def test_huge_or_negative_shift_is_dropped_not_a_crash(self):
        for sh in ("10000000000", "32", "-1"):
            with self.subTest(sh=sh):
                try:
                    out = self.norm(instructions=[f"slli x1 x1 {sh}"], initial_registers={"x1": 1})
                except ValueError:
                    out = None  # normalize_practice catches ValueError and drops the item
                self.assertIsNone(out)

    def test_too_many_instructions_or_registers_dropped(self):
        self.assertIsNone(self.norm(instructions=["add x1 x1 x1"] * 65, initial_registers={"x1": 1}))
        self.assertIsNone(self.norm(instructions=["add x1 x1 x1"], initial_registers={"x1": 2 ** 40}))


class ConfusionMatrixZeroCountTest(unittest.TestCase):
    def test_zero_false_positives_is_a_valid_matrix(self):
        import practice_ai
        item = practice_ai.NORMALIZERS["confusion_matrix_metrics"](
            {"TP": 10, "FP": 0, "FN": 5, "TN": 20}, {"id": "p1", "type": "confusion_matrix_metrics", "prompt": "?"})
        self.assertIsNotNone(item)
        self.assertEqual(item["metrics"]["precision"], 1.0)


class ExportRedactionTest(unittest.TestCase):
    def test_export_strips_kit_answer_keys(self):
        item = _norm(BANKER_SAFE)
        stored = {"id": "kit-export-test", "title": "Export", "practice": [item]}
        fake_path = Path("/nonexistent/kit-export-test.json")
        with TestClient(server.app, base_url=LOCAL) as c, \
                mock.patch.object(server, "course_topic_files", return_value={fake_path: "kit-export-test"}), \
                mock.patch.dict(server._TOPIC_CACHE, {fake_path: (0, stored)}):
            uid = db.get_or_create_user("Export Tester")["id"]
            r = c.get(f"/api/users/{uid}/export")
        self.assertEqual(r.status_code, 200, r.text)
        got = r.json()["topics"]["kit-export-test"]["practice"][0]
        self.assertNotIn("is_safe", got)
        self.assertNotIn("safe_sequence", got)
        self.assertEqual(got["allocation"], item["allocation"])


    def test_export_strips_kit_answer_keys_from_lesson_snapshots(self):
        item = _norm(BANKER_SAFE)
        fake = {"user": {"id": "u"}, "courses": [], "tables": {}, "consent": None,
                "lessons": [{"topic_id": "kit-export-test", "body": {"id": "kit-export-test", "practice": [item]}}]}
        with TestClient(server.app, base_url=LOCAL) as c, mock.patch.object(server.db, "export_user", return_value=fake):
            uid = db.get_or_create_user("Export Tester 2")["id"]
            r = c.get(f"/api/users/{uid}/export")
        self.assertEqual(r.status_code, 200, r.text)
        got = r.json()["lessons"][0]["body"]["practice"][0]
        self.assertNotIn("is_safe", got)
        self.assertNotIn("safe_sequence", got)


if __name__ == "__main__":
    unittest.main()
