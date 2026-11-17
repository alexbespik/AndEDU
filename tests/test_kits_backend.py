"""Backend of the eleven kits: seed lessons normalize, answer keys never reach the browser, the grade route answers
exactly {ok, score, feedback, details}, secrets survive round trips, and graders only read fields that are declared
secret or public. Offline; the server runs against test_lab's temporary data folder."""
import ast
import importlib.util
import inspect
import json
import sys
import textwrap
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import LOCAL, TestClient, server, topic  # noqa: E402
import db  # noqa: E402
import mcp_tools_kits  # noqa: E402
import practice_music  # noqa: E402

_spec = importlib.util.spec_from_file_location("seed_kits", ROOT / "scripts" / "seed_kits.py")
seed_kits = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_kits)

BASE_FIELDS = {"id", "type", "prompt", "explanation", "concept"}
SHAPE = {"ok", "score", "feedback", "details"}


def correct_submission(item):
    """The right answer for a stored (unredacted) seed item, read from its secret fields."""
    t = item["type"]
    table = {
        "scansion": lambda: item["stress_pattern"], "volta_spot": lambda: item["target_index"],
        "rhyme_scheme_audit": lambda: item["rhyme_scheme"], "chronology_unravel": lambda: item["canonical_order"],
        "lint_satb_progression": lambda: item["expected_errors"], "roman_numeral_analysis": lambda: item["expected"],
        "ear_interval_id": lambda: "perfect fifth", "figured_bass_realize": lambda: item["solution"],
        "composition_vector": lambda: item["focal_point"], "label_architecture": lambda: item["solution"],
        "iconography_decode": lambda: item["solution"], "stylistic_taxonomy": lambda: item["period"],
        "epigraphy_transcribe": lambda: item["transcription"], "harris_matrix_build": lambda: item["solution"],
        "cursus_honorum_order": lambda: item["solution"],
        "athenian_sortition_sim": lambda: {k: v[:item["quotas"][k]] for k, v in item["candidates"].items()},
        "stasis_classify": lambda: item["correct_stasis"], "trope_hunter": lambda: item["target_trope"],
        "dispositio_sort": lambda: item["solution"], "enthymeme_excavator": lambda: item["solution"],
        "compute_dhondt": lambda: item["solution"], "compute_shapley_shubik_pivotal": lambda: item["shapley_shubik_index"],
        "veto_pipeline": lambda: {"will_pass": item["will_pass"], "blocking_actor": item["blocking_actor"]},
        "instant_runoff_tally": lambda: {"winner": item["winner"], "elimination_order": item["elimination_order"]},
        "circuit_kcl_kvl": lambda: {"value": item["solution"]},
        "bode_plot_analyzer": lambda: {k: item[k] for k in item["ask"]},
        "boolean_gate_minimization": lambda: "BA' + B'A",  # same product terms as A'B + AB', written another way
        "opamp_gain_calc": lambda: {"vout": item["vout_expected"]},
        "backprop_layer_step": lambda: {"grad_W": item["grad_W"], "grad_b": item["grad_b"]},
        "attention_score_matrix": lambda: item["attention_weights"], "confusion_matrix_metrics": lambda: item["metrics"],
        "loss_gradient_verify": lambda: {"loss": item["loss_expected"], "grad": item["grad_expected"]},
        "page_table_walk": lambda: item["physical_address"], "cache_tag_index_offset": lambda: item["expected_bits"],
        "assembly_reg_trace": lambda: item["final_registers"],
        "deadlock_bankers": lambda: {"is_safe": item["is_safe"], "sequence": item["safe_sequence"]},
        "hypothesis_test_two_sample": lambda: {"test_statistic": item["statistic_expected"], "reject_null": item["reject_null_expected"]},
        "bayes_posterior_update": lambda: item["posterior_expected"], "mle_parameter_derivation": lambda: item["mle_expected"],
        "markov_steady_state": lambda: item["steady_state_expected"],
        "smith_waterman_align": lambda: item["max_score"], "orf_finder_translate": lambda: item["protein_sequence"],
        "restriction_digest_mapper": lambda: item["fragment_sizes"], "phylogenetic_upgma_step": lambda: item["merged_pair"],
    }
    return table[t]()


class SeedLessons(unittest.TestCase):
    def test_seed_has_a_lesson_per_kit_and_every_item_normalizes(self):
        topics = seed_kits.build_topics()
        self.assertEqual(len(topics), 12)
        seen = set()
        for t in topics:
            clean, warnings = server.normalize_topic(t)
            self.assertEqual(warnings, [], t["id"])
            self.assertEqual(len(clean["practice"]), len(t["practice"]), t["id"])
            seen |= {p["type"] for p in clean["practice"]}
        self.assertEqual(set(server.PRACTICE_GRADERS) - seen, set(), "a graded type has no seed example")

    def test_seed_items_are_rejected_when_a_required_field_is_removed(self):
        t = seed_kits.build_topics()[0]
        broken = dict(t, practice=[{k: v for k, v in t["practice"][0].items() if k != "stress_pattern"}])
        clean, warnings = server.normalize_topic(broken)
        self.assertEqual(clean["practice"], [])
        self.assertEqual(len(warnings), 1)


class OverTheApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.client = TestClient(server.app, base_url=LOCAL)
        cls.suffix = uuid.uuid4().hex[:6]
        cls.ids = {}
        for t in seed_kits.build_topics():
            tid = f"{t['id']}-{cls.suffix}"
            r = cls.client.post("/api/topics", json={**t, "id": tid})
            assert r.status_code == 200 and r.json()["warnings"] == [], (tid, r.text)
            cls.ids[t["id"]] = tid

    def stored(self, seed_id):
        return json.loads(server.topic_path(self.ids[seed_id]).read_text(encoding="utf-8"))

    def graded(self):
        for seed_id in self.ids:
            for item in self.stored(seed_id)["practice"]:
                if item["type"] in server.PRACTICE_GRADERS:
                    yield seed_id, item

    def grade(self, seed_id, item_id, submission):
        return self.client.post("/api/practice/grade", json={"topicId": self.ids[seed_id], "itemId": item_id, "submission": submission})

    def test_the_browser_never_sees_a_secret_field(self):
        for seed_id, item in self.graded():
            hidden = server.secret_fields_for(item["type"])
            self.assertTrue(hidden, item["type"])
            shown = [p for p in self.client.get(f"/api/topics/{self.ids[seed_id]}").json()["practice"] if p["id"] == item["id"]][0]
            self.assertEqual(set(shown) & hidden, set(), f"{item['type']} leaks {set(shown) & hidden}")
            listed = [t for t in self.client.get("/api/topics").json() if t["id"] == self.ids[seed_id]][0]
            self.assertEqual({k for p in listed["practice"] if p["id"] == item["id"] for k in p} & hidden, set())
            via_route = [p for p in self.client.get(f"/api/topics/{self.ids[seed_id]}/practice").json() if p["id"] == item["id"]][0]
            self.assertEqual(set(via_route) & hidden, set())

    def test_every_secret_field_is_really_stored(self):
        # a secret that no item carries would mean the redaction list drifted from the normalizer output
        carried = {}
        for _, item in self.graded():
            carried.setdefault(item["type"], set()).update(item)
        for t, fields in server.GRADERS_SECRET_BY_TYPE.items():
            if fields and t in carried:
                self.assertTrue(fields & carried[t], f"{t}: none of {fields} is in the stored item")

    def test_a_correct_answer_passes_with_exactly_the_contract_shape(self):
        for seed_id, item in self.graded():
            r = self.grade(seed_id, item["id"], correct_submission(item))
            self.assertEqual(r.status_code, 200, (item["type"], r.text))
            body = r.json()
            self.assertEqual(set(body), SHAPE, item["type"])
            self.assertTrue(body["ok"], (item["type"], body))
            self.assertEqual(body["score"], 1.0, item["type"])
            self.assertIsInstance(body["details"], dict)

    def test_a_wrong_answer_never_echoes_the_key(self):
        wrong = [None, "zzz", {}, [], 99, {"value": 123456.5}, ["x"], {"x": 1}]
        for seed_id, item in self.graded():
            key = json.dumps(correct_submission(item), sort_keys=True)
            for sub in wrong:
                r = self.grade(seed_id, item["id"], sub)
                self.assertIn(r.status_code, (200, 400), (item["type"], sub, r.text))
                if r.status_code == 400:
                    self.assertEqual(r.json()["detail"], "bad submission")
                    continue
                body = r.json()
                self.assertEqual(set(body), SHAPE)
                self.assertFalse(body["ok"], (item["type"], sub))
                self.assertTrue(0.0 <= body["score"] <= 1.0)
                for name in body["details"]:
                    self.assertFalse(name.startswith("expected") or name in ("true_errors", "errors", "solution"), (item["type"], name))
                text = json.dumps(body, sort_keys=True)
                if len(key) > 6:
                    self.assertNotIn(key, text, f"{item['type']} echoes its answer key")

    def test_grade_route_errors(self):
        sid = next(iter(self.ids))
        self.assertEqual(self.client.post("/api/practice/grade", json={"topicId": self.ids[sid], "itemId": "", "submission": 1}).status_code, 400)
        self.assertEqual(self.client.post("/api/practice/grade", json={"topicId": self.ids[sid], "itemId": "  ", "submission": 1}).status_code, 400)
        self.assertEqual(self.client.post("/api/practice/grade", json={"topicId": self.ids[sid], "itemId": "p99", "submission": 1}).status_code, 404)
        self.assertEqual(self.client.post("/api/practice/grade", json={"topicId": "no-such-topic", "itemId": "p1", "submission": 1}).status_code, 404)
        plain = f"plain-{self.suffix}"
        self.client.post("/api/topics", json=topic(plain, practice=[{"type": "true_false", "prompt": "x", "answer": True}]))
        r = self.client.post("/api/practice/grade", json={"topicId": plain, "itemId": "p1", "submission": True})
        self.assertEqual(r.status_code, 400, "client-graded types have no server grader")
        big = self.grade(sid, "p1", "x" * 30000)
        self.assertEqual(big.status_code, 400)

    def test_grade_route_is_rate_limited(self):
        sid = next(iter(self.ids))
        self.assertEqual(server.RATE_LIMITS["practice_grade"], 600)
        def clear():
            for key in [k for k in server._rate_hits if k[0] == "practice_grade"]:
                server._rate_hits.pop(key, None)
        clear()
        self.addCleanup(clear)
        with mock.patch.dict(server.RATE_LIMITS, {"practice_grade": 2}):
            codes = [self.grade(sid, "p1", "0 1").status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_grade_result_is_cleaned_whatever_a_grader_returns(self):
        clean = server.clean_grade_result({"ok": False, "score": 7, "feedback": "f", "details": {"expected_x": 1, "solution": 2, "keep": 3,
                                          "nested": {"expected": 1, "fine": 2}}, "extra": "dropped"}, "scansion")
        self.assertEqual(clean, {"ok": False, "score": 1.0, "feedback": "f", "details": {"keep": 3, "nested": {"fine": 2}}})
        self.assertEqual(server.clean_grade_result({"ok": True, "score": float("nan")}, "scansion")["score"], 0.0)
        self.assertEqual(server.clean_grade_result({"ok": False, "score": -3}, "scansion")["score"], 0.0)
        self.assertEqual(server.clean_grade_result({"ok": True, "details": {"errors": ["a"]}}, "scansion")["details"], {"errors": ["a"]})
        with self.assertRaises(ValueError):
            server.clean_grade_result("nope", "scansion")

    def test_saving_back_what_the_browser_read_keeps_the_answer_keys(self):
        sid = "kit-music-sample"
        read = self.client.get(f"/api/topics/{self.ids[sid]}").json()
        self.assertNotIn("expected_errors", read["practice"][0])
        r = self.client.post("/api/topics", json=read)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["warnings"], [], "the redacted items must survive the save")
        after = self.stored(sid)
        self.assertEqual(len(after["practice"]), 4)
        self.assertIn("expected_errors", after["practice"][0])
        item = after["practice"][2]
        self.assertTrue(self.grade(sid, item["id"], "perfect fifth").json()["ok"])

    def test_delete_and_put_answers_are_redacted(self):
        sid = "kit-rhetoric-sample"
        tid = self.ids[sid]
        put = self.client.put(f"/api/topics/{tid}/practice/p1", json={"prompt": "Which question does this case turn on, again?"})
        self.assertEqual(put.status_code, 200, put.text)
        for part in ("before", "after"):
            self.assertNotIn("correct_stasis", put.json()[part])
        self.assertEqual(self.stored(sid)["practice"][0]["correct_stasis"], "conjecture")
        gone = self.client.delete(f"/api/topics/{tid}/practice/p2")
        self.assertNotIn("target_trope", gone.json()["removed"])

    def test_copy_route_keeps_the_keys_and_checks_both_topics(self):
        src, dst = self.ids["kit-polity-sample"], f"copy-target-{self.suffix}"
        self.client.post("/api/topics", json=topic(dst, practice=[{"type": "true_false", "prompt": "keep", "answer": True}]))
        r = self.client.post(f"/api/topics/{dst}/practice/copy", json={"fromTopic": src, "kinds": ["practice"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["copied"], {"practice": 4})
        copied = json.loads(server.topic_path(dst).read_text(encoding="utf-8"))["practice"]
        self.assertEqual([p["id"] for p in copied], ["p1", "p2", "p3", "p4", "p5"])
        self.assertIn("solution", copied[1])
        self.assertTrue(self.client.post("/api/practice/grade", json={"topicId": dst, "itemId": "p2", "submission": copied[1]["solution"]}).json()["ok"])
        self.assertEqual(self.client.post(f"/api/topics/{dst}/practice/copy", json={"fromTopic": "missing-topic"}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/topics/missing-topic/practice/copy", json={"fromTopic": src}).status_code, 404)


class RedactionRules(unittest.TestCase):
    def test_base_and_per_type_fields_are_both_stripped(self):
        item = {"type": "ear_interval_id", "id": "p1", "prompt": "x", "notes": ["C4", "E4"], "semitones": 4, "interval_name": "major third",
                "solution": "extra"}
        shown = server.redact_practice_item(item)
        self.assertEqual(set(shown), {"type", "id", "prompt", "notes"})

    def test_client_graded_items_keep_their_answer(self):
        item = {"type": "true_false", "id": "p1", "prompt": "x", "answer": True}
        self.assertEqual(server.redact_practice_item(item), item)

    def test_public_givens_are_not_secret(self):
        # the student needs these to solve the item; an earlier flat list hid some of them
        self.assertNotIn("quotas", server.secret_fields_for("athenian_sortition_sim"))
        self.assertNotIn("minterms", server.secret_fields_for("boolean_gate_minimization"))
        for f in ("vpn", "ppn"):
            self.assertNotIn(f, server.secret_fields_for("page_table_walk"))
        for f in ("will_pass", "blocking_actor"):
            self.assertIn(f, server.secret_fields_for("veto_pipeline"))
        self.assertIn("relationships", server.secret_fields_for("harris_matrix_build"))
        self.assertIn("semitones", server.secret_fields_for("ear_interval_id"))


class GraderFieldScan(unittest.TestCase):
    """Every field a grader reads from its item is declared: secret (stripped before the browser) or public."""

    def fields_read(self, fn):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        func = tree.body[0]
        item = func.args.args[0].arg
        found = set()
        for node in ast.walk(func):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == item
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                found.add(node.args[0].value)
            elif (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == item
                  and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
                found.add(node.slice.value)
        return found

    def test_every_field_a_grader_reads_is_secret_or_declared_public(self):
        scanned = 0
        for ptype, grader in server.PRACTICE_GRADERS.items():
            read = self.fields_read(grader)
            declared = server.secret_fields_for(ptype) | server.GRADERS_PUBLIC_BY_TYPE.get(ptype, set()) | BASE_FIELDS
            self.assertEqual(read - declared, set(), f"{ptype}: grader reads undeclared fields {read - declared}")
            scanned += 1
        self.assertEqual(scanned, 44)

    def test_a_field_is_never_both_secret_and_public(self):
        for ptype, public in server.GRADERS_PUBLIC_BY_TYPE.items():
            self.assertEqual(public & server.secret_fields_for(ptype), set(), ptype)

    def test_every_kit_type_declares_secrets_and_a_docstring(self):
        for ptype in server.PRACTICE_GRADERS:
            self.assertTrue(server.GRADERS_SECRET_BY_TYPE.get(ptype) or server.GRADERS_PUBLIC_BY_TYPE.get(ptype) is not None, ptype)
            self.assertTrue(inspect.getdoc(server.PRACTICE_NORMALIZERS[ptype]), f"{ptype} has no docstring (GET /api/practice/guide)")


class MusicIntervals(unittest.TestCase):
    def setUp(self):
        self.norm = practice_music.NORMALIZERS["ear_interval_id"]
        self.grade = practice_music.GRADERS["ear_interval_id"]
        self.base = {"id": "p1", "type": "ear_interval_id"}

    def item(self, **raw):
        out = self.norm({"prompt": "x", **raw}, self.base)
        self.assertIsNotNone(out)
        return out

    def test_minor_and_major_second_are_different_answers(self):
        major, minor = self.item(notes=["C4", "D4"]), self.item(notes=["C4", "Db4"])
        for good in ("M2", "maj2", "Maj2", "major second", "2", 2):
            self.assertTrue(self.grade(major, good)["ok"], good)
            self.assertFalse(self.grade(minor, good)["ok"], good)
        for good in ("m2", "min2", "minor second", 1):
            self.assertTrue(self.grade(minor, good)["ok"], good)
            self.assertFalse(self.grade(major, good)["ok"], good)

    def test_all_m_and_M_pairs(self):
        for st, m, big in ((3, "m3", "M3"), (8, "m6", "M6"), (10, "m7", "M7")):
            minor = self.item(semitones=st)
            self.assertTrue(self.grade(minor, m)["ok"])
            self.assertFalse(self.grade(minor, big)["ok"])
        self.assertTrue(self.grade(self.item(semitones=4), "M3")["ok"])
        self.assertFalse(self.grade(self.item(semitones=4), "m3")["ok"])

    def test_octave_is_not_a_unison(self):
        octave = self.item(notes=["C4", "C5"])
        self.assertEqual(octave["semitones"], 12)
        self.assertTrue(self.grade(octave, "octave")["ok"])
        self.assertTrue(self.grade(octave, "P8")["ok"])
        self.assertFalse(self.grade(octave, "unison")["ok"])
        self.assertTrue(self.grade(self.item(semitones=0), "unison")["ok"])

    def test_item_exposes_the_two_pitches_and_hides_the_size(self):
        it = self.item(semitones=7, interval_name="perfect fifth")
        self.assertEqual(it["notes"], ["C4", "G4"])
        shown = server.redact_practice_item(it)
        self.assertEqual(shown["notes"], ["C4", "G4"])
        self.assertNotIn("semitones", shown)
        self.assertNotIn("interval_name", shown)

    def test_inconsistent_items_are_rejected(self):
        self.assertIsNone(self.norm({"prompt": "x", "notes": ["C4", "E4"], "semitones": 7}, self.base))
        self.assertIsNone(self.norm({"prompt": "x", "interval_name": "m2", "semitones": 2}, self.base))
        self.assertIsNone(self.norm({"prompt": "x", "interval_name": "banana"}, self.base))
        self.assertIsNone(self.norm({"prompt": "x", "notes": ["C4"]}, self.base))

    def test_figured_bass_accepts_enharmonic_spellings(self):
        norm = practice_music.NORMALIZERS["figured_bass_realize"]({"bass_note": "E3", "figures": "6", "solution": ["G#4", "C5"]}, {"id": "p1"})
        self.assertTrue(practice_music.GRADERS["figured_bass_realize"](norm, ["Ab4", "C5"])["ok"])
        self.assertFalse(practice_music.GRADERS["figured_bass_realize"](norm, ["G4", "C5"])["ok"])


class GraderLeaks(unittest.TestCase):
    def test_order_hiding_lists_never_equal_the_solution_order(self):
        import practice_classics
        import practice_rhetoric
        sol = ["exordium", "narratio", "partitio", "confirmatio", "refutatio", "peroratio"]
        it = practice_rhetoric.NORMALIZERS["dispositio_sort"]({"prompt": "x", "solution": sol, "parts": sol}, {"id": "p1"})
        self.assertNotEqual(it["parts"], sol)
        self.assertEqual(sorted(it["parts"]), sorted(sol))
        it2 = practice_classics.NORMALIZERS["cursus_honorum_order"]({"prompt": "x", "solution": ["Quaestor", "Aedile", "Praetor", "Consul"]}, {"id": "p1"})
        self.assertNotEqual(it2["offices"], ["Quaestor", "Aedile", "Praetor", "Consul"])

    def test_stasis_miss_does_not_name_the_stasis(self):
        import practice_rhetoric
        it = practice_rhetoric.NORMALIZERS["stasis_classify"]({"prompt": "x", "case": "c", "correct_stasis": "procedure"}, {"id": "p1"})
        self.assertIn("procedure", it["options"])
        res = practice_rhetoric.GRADERS["stasis_classify"](it, "policy")
        self.assertNotIn("procedure", json.dumps(res))

    def test_volta_accepts_only_the_zero_based_index(self):
        import practice_literature
        it = practice_literature.NORMALIZERS["volta_spot"]({"prompt": "x", "lines": ["a", "b", "c", "d"], "target_index": 2}, {"id": "p1"})
        grade = practice_literature.GRADERS["volta_spot"]
        self.assertTrue(grade(it, 2)["ok"])
        self.assertFalse(grade(it, 3)["ok"])

    def test_boolean_terms_are_compared_as_sets_of_literals(self):
        import practice_ee
        it = practice_ee.NORMALIZERS["boolean_gate_minimization"]({"prompt": "x", "variables": ["A", "B", "C"], "minterms": [1], "solution": "A'BC + AB'"}, {"id": "p1"})
        grade = practice_ee.GRADERS["boolean_gate_minimization"]
        self.assertTrue(grade(it, "B'A + CBA'")["ok"])
        self.assertTrue(grade(it, "AB' + A'BC")["ok"])
        self.assertFalse(grade(it, "AB' + A'B")["ok"])

    def test_bode_grades_only_the_asked_metrics(self):
        import practice_ee
        it = practice_ee.NORMALIZERS["bode_plot_analyzer"]({"prompt": "x", "transfer_function": "H", "cutoff_rad_s": 100}, {"id": "p1"})
        self.assertEqual(it["ask"], ["cutoff_rad_s"])
        self.assertTrue(practice_ee.GRADERS["bode_plot_analyzer"](it, {"cutoff_rad_s": 102, "gain_margin_db": 999})["ok"])
        self.assertNotIn("ask", server.secret_fields_for("bode_plot_analyzer"))

    def test_hypothesis_item_states_its_test(self):
        import practice_stats
        it = practice_stats.NORMALIZERS["hypothesis_test_two_sample"](
            {"prompt": "x", "mean1": 5, "std1": 1, "n1": 30, "mean2": 4, "std2": 1, "n2": 30, "alpha": 0.01}, {"id": "p1"})
        self.assertEqual((it["test"], it["critical_value"]), ("z", 2.576))
        self.assertNotIn("test", server.secret_fields_for("hypothesis_test_two_sample"))

    def test_bad_cache_and_assembly_submissions_do_not_crash(self):
        import practice_systems
        cache = practice_systems.NORMALIZERS["cache_tag_index_offset"]({"prompt": "x"}, {"id": "p1"})
        self.assertFalse(practice_systems.GRADERS["cache_tag_index_offset"](cache, {"tag": "many", "index": None})["ok"])
        asm = practice_systems.NORMALIZERS["assembly_reg_trace"]({"prompt": "x", "instructions": ["addi x1, x0, 1"], "initial_registers": {"x0": 0}}, {"id": "p1"})
        self.assertFalse(practice_systems.GRADERS["assembly_reg_trace"](asm, {"x1": "one"})["ok"])


class LatexFences(unittest.TestCase):
    def test_fenced_block_is_left_alone(self):
        fenced = '```fbd\n{"label": "\\\\theta", "m": "\\\\(x\\\\)", "t": "\\theta"}\n```'
        text = f"Text with \\(x\\) and \\[y\\].\n\n{fenced}\n\nThen \\(z\\)."
        out = server.repair_latex(text)
        self.assertIn(fenced, out)
        self.assertIn("$x$", out)
        self.assertIn("$$y$$", out)
        self.assertIn("$z$", out)

    def test_text_without_fences_is_repaired_as_before(self):
        self.assertEqual(server.repair_latex("see \\(a+b\\)"), "see $a+b$")
        self.assertEqual(server.repair_latex("\x0crac{1}{2}"), "\\frac{1}{2}")

    def test_geometry_json_survives_a_topic_save(self):
        spec = json.dumps({"kind": "fbd", "forces": [{"label": "m\\vec{g}"}]}, indent=2)
        clean, _ = server.normalize_topic(topic("fence-keep", markdownContent=f"# T\n\nUse \\(x\\).\n\n```fbd\n{spec}\n```\n"))
        self.assertIn(spec, clean["markdownContent"])
        self.assertIn("$x$", clean["markdownContent"])


class PlannerWorkspaces(unittest.TestCase):
    def test_diagnostic_prompt_names_every_workspace_the_server_has(self):
        prompt = next(v for k, v in vars(server).items() if isinstance(v, str) and '"workspace": "math | code' in v)
        for ws in server.WORKSPACES:
            self.assertIn(ws, prompt, f"the planner cannot choose {ws}")

    def test_guess_workspace_is_unchanged_for_plain_subjects(self):
        self.assertEqual(server.guess_workspace("Python programming"), "code")
        self.assertEqual(server.guess_workspace("Organic chemistry"), "lab")


class McpKits(unittest.TestCase):
    def test_kit_table_matches_the_server(self):
        flat = [t for types in mcp_tools_kits.KITS.values() for t in types]
        self.assertEqual(len(flat), 44)
        self.assertEqual(set(flat), set(server.PRACTICE_GRADERS))

    def test_kit_types_and_add_kit_practice(self):
        calls = []

        def fake(method, path, body=None):
            calls.append((method, path, body))
            if path == "/api/practice/guide":
                return {t: f"doc of {t}" for t in server.PRACTICE_NORMALIZERS}
            return {"added": 0 if body["items"][0].get("prompt") is None else 1, "rejected": 0, "total": 1}

        tools = {n: fn for n, _, _, fn in mcp_tools_kits.tools(fake, lambda s: s, lambda **k: k, lambda d, **k: {}, lambda d, **k: {}, lambda d, **k: {})}
        guide = tools["kit_types"]({"kit": "music"})
        self.assertEqual(list(guide), ["music"])
        self.assertEqual(set(guide["music"]), set(mcp_tools_kits.KITS["music"]))
        self.assertEqual(set(tools["kit_types"]({})), set(mcp_tools_kits.KITS))
        with self.assertRaises(ValueError):
            tools["kit_types"]({"kit": "alchemy"})
        res = tools["add_kit_practice"]({"topic_id": "t", "type": "scansion", "item": {"prompt": "p"}})
        self.assertEqual(res["kit"], "literature")
        self.assertEqual(calls[-1][2]["items"][0]["type"], "scansion")
        with self.assertRaises(RuntimeError):
            tools["add_kit_practice"]({"topic_id": "t", "type": "scansion", "item": {}})
        with self.assertRaises(ValueError):
            tools["add_kit_practice"]({"topic_id": "t", "type": "true_false", "item": {"prompt": "p"}})

    def test_tools_are_registered_in_the_server(self):
        import mcp_server
        names = {t[0] for t in mcp_server.TOOLS}
        for n in ("kit_types", "add_kit_practice", "add_fbd_drawing"):
            self.assertIn(n, names)


if __name__ == "__main__":
    unittest.main()
