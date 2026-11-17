"""The 24 sample classes of the six liberal-arts kits (scripts/seed_kit_syllabi.py): every lesson normalizes with no
warnings, no practice item or quiz question is dropped, the answer keys the server computes are the ones the lessons
teach, and each practice type belongs to its own kit. Offline: only build_topics() and in-process normalization run."""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import server  # noqa: E402
import practice_art_history  # noqa: E402
import practice_classics  # noqa: E402
import practice_literature  # noqa: E402
import practice_music  # noqa: E402
import practice_polity  # noqa: E402
import practice_rhetoric  # noqa: E402

_spec = importlib.util.spec_from_file_location("seed_kit_syllabi", ROOT / "scripts" / "seed_kit_syllabi.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)

KIT_MODULES = {
    "literature": practice_literature, "art_history": practice_art_history, "music": practice_music,
    "classics": practice_classics, "rhetoric": practice_rhetoric, "polity": practice_polity,
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def correct_submission(item):
    """The right answer for a normalized (unredacted) item, read from its stored keys."""
    t = item["type"]
    table = {
        "scansion": lambda: item["stress_pattern"], "volta_spot": lambda: item["target_index"],
        "rhyme_scheme_audit": lambda: item["rhyme_scheme"], "chronology_unravel": lambda: item["canonical_order"],
        "lint_satb_progression": lambda: item["expected_errors"], "roman_numeral_analysis": lambda: item["expected"],
        "ear_interval_id": lambda: item["semitones"], "figured_bass_realize": lambda: item["solution"],
        "label_architecture": lambda: item["solution"], "iconography_decode": lambda: item["solution"],
        "stylistic_taxonomy": lambda: item["period"], "epigraphy_transcribe": lambda: item["transcription"],
        "harris_matrix_build": lambda: item["solution"], "cursus_honorum_order": lambda: item["solution"],
        "athenian_sortition_sim": lambda: {k: v[:item["quotas"][k]] for k, v in item["candidates"].items()},
        "stasis_classify": lambda: item["correct_stasis"], "trope_hunter": lambda: item["target_trope"],
        "dispositio_sort": lambda: item["solution"], "enthymeme_excavator": lambda: item["solution"],
        "compute_dhondt": lambda: item["solution"], "compute_shapley_shubik_pivotal": lambda: item["shapley_shubik_index"],
        "veto_pipeline": lambda: {"will_pass": item["will_pass"], "blocking_actor": item["blocking_actor"]},
        "instant_runoff_tally": lambda: {"winner": item["winner"], "elimination_order": item["elimination_order"]},
    }
    return table[t]()


class SeedKitSyllabi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.topics = seed.build_topics()
        cls.clean = {}
        for t in cls.topics:
            cls.clean[t["id"]], warnings = server.normalize_topic(t)
            cls.warnings = getattr(cls, "warnings", {})
            cls.warnings[t["id"]] = warnings

    def kit_of(self, topic):
        return next(k for k in KIT_MODULES if topic["id"].startswith("kit-" + k.replace("_", "-") + "-class-"))

    def test_24_lessons_four_per_kit_with_unique_valid_ids(self):
        self.assertEqual(len(self.topics), 24)
        ids = [t["id"] for t in self.topics]
        self.assertEqual(len(set(ids)), 24)
        for t in self.topics:
            self.assertRegex(t["id"], ID_RE)
        for kit in KIT_MODULES:
            want = [f"kit-{kit.replace('_', '-')}-class-{n}" for n in (1, 2, 3, 4)]
            self.assertEqual([i for i in ids if i in want], want, kit)
            self.assertEqual(sum(1 for i in ids if i.startswith(f"kit-{kit.replace('_', '-')}-class-")), 4, kit)

    def test_workspace_is_the_kit_mode_id_and_category_is_set(self):
        for t in self.topics:
            self.assertEqual(t["source"]["workspace"], self.kit_of(t), t["id"])
            self.assertTrue(t["category"].strip(), t["id"])
            self.assertTrue(t["title"].strip() and t["summary"].strip(), t["id"])
        for kit in KIT_MODULES:  # the mode ids must match what the server knows
            self.assertIn(kit, server.WORKSPACES)

    def test_every_lesson_normalizes_with_zero_warnings_and_nothing_dropped(self):
        for t in self.topics:
            clean = self.clean[t["id"]]
            self.assertEqual(self.warnings[t["id"]], [], t["id"])
            self.assertEqual(len(clean["practice"]), len(t["practice"]), t["id"])
            self.assertEqual(len(clean["quiz"]), len(t["quiz"]), t["id"])
            self.assertEqual(len(clean["cheatSheet"]), len(t["cheatSheet"]), t["id"])

    def test_lesson_shape(self):
        for t in self.topics:
            words = len(t["markdownContent"].split())
            self.assertTrue(300 <= words <= 600, f"{t['id']}: {words} words")
            self.assertTrue(2 <= len(t["cheatSheet"]) <= 4, t["id"])
            self.assertEqual(len(t["quiz"]), 3, t["id"])
            self.assertEqual(len(t["practice"]), 2, t["id"])
            for qz in t["quiz"]:
                self.assertIn(qz["correctAnswer"], range(len(qz["options"])), t["id"])
                self.assertEqual(len(set(qz["options"])), len(qz["options"]), t["id"])
                self.assertTrue(qz["hint"] and qz["explanation"], t["id"])
            for c in t["cheatSheet"]:
                self.assertNotIn("$", c["formula"], t["id"])

    def test_difficulty_rises_through_each_kit(self):
        order = ["Introductory", "Introductory", "Intermediate", "Advanced"]
        for kit in KIT_MODULES:
            got = [t["difficulty"] for t in self.topics if t["id"].startswith(f"kit-{kit.replace('_', '-')}-class-")]
            self.assertEqual(got, order, kit)

    def test_every_practice_type_belongs_to_its_own_kit(self):
        for t in self.topics:
            kit = self.kit_of(t)
            for item in t["practice"]:
                self.assertIn(item["type"], KIT_MODULES[kit].NORMALIZERS, f"{t['id']}: {item['type']}")
                self.assertIn(item["type"], server.PRACTICE_GRADERS)

    def test_every_item_is_graded_correct_by_its_own_stored_key(self):
        for t in self.topics:
            kit = self.kit_of(t)
            for item in self.clean[t["id"]]["practice"]:
                res = KIT_MODULES[kit].GRADERS[item["type"]](item, correct_submission(item))
                self.assertTrue(res["ok"], f"{t['id']}: {item['type']} {res}")

    def test_computed_keys_are_the_ones_the_lessons_teach(self):
        def items(tid):
            return self.clean[tid]["practice"]
        d1, d2 = items("kit-polity-class-2")
        self.assertEqual(d1["solution"], {"Alder": 3, "Birch": 3, "Cedar": 1, "Dogwood": 0})
        self.assertEqual(d2["solution"], {"Left": 3, "Centre": 2, "Right": 1, "Green": 0})
        r1, r2 = items("kit-polity-class-3")
        self.assertEqual((r1["winner"], r1["elimination_order"]), ("Cy", ["Dee", "Ben"]))
        self.assertEqual((r2["winner"], r2["elimination_order"]), ("Noel", ["Omar"]))
        s1, s2 = items("kit-polity-class-4")
        self.assertEqual(s1["shapley_shubik_index"], {"A": 0.3333, "B": 0.3333, "C": 0.3333})
        self.assertEqual(s2["shapley_shubik_index"], {"A": 0.4167, "B": 0.25, "C": 0.25, "D": 0.0833})
        l1, l2 = items("kit-music-class-4")
        self.assertEqual(l1["expected_errors"], ["parallel_octave:S_B:chord_1_to_2"])
        self.assertEqual(l2["expected_errors"], [])
        e1, e2 = items("kit-music-class-1")
        self.assertEqual((e1["semitones"], e2["semitones"]), (7, 8))
        self.assertEqual((e1["interval_name"], e2["interval_name"]), ("perfect fifth", "minor sixth"))
        # the exercises that count syllables carry one mark per syllable
        self.assertEqual(len(items("kit-literature-class-1")[0]["stress_pattern"].split()), 10)
        self.assertEqual(items("kit-literature-class-4")[0]["stress_pattern"], "1 0 1 0 1 0 1")
        self.assertEqual(items("kit-literature-class-2")[0]["target_index"], 8)

    def test_building_the_lessons_does_not_touch_the_network(self):
        # build_topics is pure data; only _post (never called here) opens a connection
        self.assertTrue(callable(seed._post))
        self.assertEqual(len(seed.build_topics()), 24)


if __name__ == "__main__":
    unittest.main()
