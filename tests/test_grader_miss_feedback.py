"""A kit grader must not act as an answer oracle on a miss: no counts, flags or 'expected' fields derived from the
answer key in the feedback or details. Offline; calls each module's grader directly on every seed item."""
import copy
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
import test_lab  # noqa: E402,F401  (sets up the offline test environment)
import server  # noqa: E402
from test_kits_backend import correct_submission  # noqa: E402

_spec = importlib.util.spec_from_file_location("seed_kits", ROOT / "scripts" / "seed_kits.py")
seed_kits = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_kits)

FRACTION = re.compile(r"\d+\s*/\s*\d+")
BAD_DETAIL = re.compile(r"^(expected|decision_match|stat_match|matches|matched|correct_count|loss_match|grad_match|total|passed)")


def perturb(v):
    """Wrong variants of a correct submission: one element changed, reversed, or scaled."""
    if isinstance(v, bool):
        yield not v
    elif isinstance(v, (int, float)):
        yield v + 7
        yield v * 3 + 1
    elif isinstance(v, str):
        yield v + "x"
        yield v[::-1] if v[::-1] != v else v + "z"
        yield "zzz"
    elif isinstance(v, list):
        if len(v) > 1:
            yield list(reversed(v))
            yield v[1:] + v[:1]
        if v:
            yield v[:-1]
            for i in range(len(v)):
                for alt in perturb(v[i]):
                    w = copy.deepcopy(v)
                    w[i] = alt
                    yield w
    elif isinstance(v, dict):
        for k in v:
            for alt in perturb(v[k]):
                w = copy.deepcopy(v)
                w[k] = alt
                yield w
    yield None


class MissFeedbackIsKeyFree(unittest.TestCase):
    def test_no_seed_item_leaks_key_derived_counts_on_a_miss(self):
        misses = {}
        for t in seed_kits.build_topics():
            clean, _ = server.normalize_topic(t)
            for item in clean["practice"]:
                grader = server.PRACTICE_GRADERS.get(item["type"])
                if grader is None:
                    continue
                for sub in perturb(correct_submission(item)):
                    try:
                        res = grader(item, sub)
                    except Exception:
                        continue
                    if res.get("ok"):
                        continue
                    misses[item["type"]] = misses.get(item["type"], 0) + 1
                    self.assertEqual(set(res), {"ok", "score", "feedback", "details"})
                    fb = str(res["feedback"])
                    self.assertIsNone(FRACTION.search(fb), (item["type"], fb))
                    self.assertNotIn("expected", fb.lower(), (item["type"], fb))
                    self.assertNotIn("decision_match", fb)
                    for name in res["details"]:
                        self.assertIsNone(BAD_DETAIL.match(name), (item["type"], name, res["details"]))
        graded_types = {p["type"] for t in seed_kits.build_topics() for p in t["practice"]
                        if p["type"] in server.PRACTICE_GRADERS}
        self.assertEqual(graded_types - set(misses), set(), "a seed type produced no miss to check")


if __name__ == "__main__":
    unittest.main()
