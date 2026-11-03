"""
&.edu LAB regression tests. Standard library only:  python -m unittest discover -s tests -v
Runs against a temporary data folder (SCIEDU_CONTENT_DIR) and never calls Gemini.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.TemporaryDirectory(prefix="andedu-test-")
os.environ["SCIEDU_CONTENT_DIR"] = TMP.name
os.environ.pop("SCIEDU_AUTH", None)
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import server  # noqa: E402
from simspec import validate_spec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

LOCAL = "http://localhost"


def topic(tid="test-topic", **extra):
    return {"id": tid, "title": "Test", "category": "Physics", "markdownContent": "# Test", **extra}


class AnswerKeys(unittest.TestCase):
    def test_numeric_answer_is_not_read_as_an_index(self):
        self.assertEqual(server.resolve_answer_alias("2", ["1", "2", "3", "4"]), "2")
        self.assertEqual(server.resolve_answer_alias("2", ["a", "b", "c", "d"]), "c")
        self.assertEqual(server.resolve_answer_alias("B", ["w", "x", "y", "z"]), "x")

    def test_choices_always_contain_the_answer(self):
        choices = server.finalize_choices(["a", "b", "c", "d", "e", "f"], "f")
        self.assertEqual(len(choices), 4)
        self.assertIn("f", choices)

    def test_quiz_item_accepts_old_correct_key(self):
        q = server.normalize_quiz_item({"question": "?", "options": ["x", "y"], "correct": 1}, 0)
        self.assertEqual(q["correctAnswer"], 1)
        self.assertNotIn("correct", q)
        self.assertIsNone(server.normalize_quiz_item({"question": "?", "options": ["x", "y"], "correctAnswer": 5}, 0))

    def test_block_pool_is_shuffled(self):
        p = server.normalize_single_problem({"type": "block_builder", "id": 7, "correct_blocks": list("abcdef")}, 1, "c", 0)
        self.assertNotEqual(p["blocks_pool"][:6], list("abcdef"))

    def test_practice_keeps_only_gradable_items(self):
        items = server.normalize_practice([
            {"type": "fill_blank", "prompt": "p", "options": ["a", "b"], "answer": "b"},
            {"type": "fill_blank", "prompt": "p", "options": ["a", "b"], "answer": "zzz"},
            {"type": "numeric", "prompt": "p", "answer": "4.2"},
            {"type": "true_false", "prompt": "p", "answer": "yes"},
        ])
        self.assertEqual([i["type"] for i in items], ["fill_blank", "numeric"])


class LatexJson(unittest.TestCase):
    def parse(self, raw):
        return json.loads(server.repair_json_escapes(raw))["a"]

    def test_latex_commands_survive(self):
        self.assertEqual(self.parse(r'{"a": "\theta + \frac{1}{2} \alpha"}'), r"\theta + \frac{1}{2} \alpha")
        self.assertEqual(self.parse(r'{"a": "\nu \rho \text{m} \beta"}'), r"\nu \rho \text{m} \beta")

    def test_real_escapes_are_untouched(self):
        self.assertEqual(self.parse('{"a": "line\\nnext \\"q\\" \\u00e9"}'), 'line\nnext "q" é')
        self.assertEqual(self.parse(r'{"a": "already \\theta"}'), r"already \theta")


class SimSpec(unittest.TestCase):
    def test_valid_graph(self):
        spec, errors = validate_spec({"kind": "graph", "params": [{"name": "A", "min": 0, "max": 2, "value": 1}],
                                      "x": {"min": 0, "max": 10}, "curves": [{"expr": "A*sin(x - t)"}]})
        self.assertEqual(errors, [])
        self.assertEqual(spec["curves"][0]["expr"], "A*sin(x - t)")

    def test_rejects_code_and_unknown_names(self):
        _, errors = validate_spec({"kind": "graph", "x": {"min": 0, "max": 1},
                                   "curves": [{"expr": "__import__(1)"}, {"expr": "mystery * 2"}]})
        self.assertEqual(len(errors), 2)

    def test_particles_with_rod_and_if(self):
        _, errors = validate_spec({
            "kind": "particles", "params": [{"name": "L", "min": 0.5, "max": 3, "value": 2}],
            "world": {"width": 6, "height": 4, "gravity": "9.81"},
            "bodies": [{"id": "pivot", "x": "3", "y": "4", "fixed": True}, {"id": "bob", "x": "3+L", "y": "4"}],
            "links": [{"type": "rod", "a": "pivot", "b": "bob", "length": "L"}],
            "series": [{"label": "h", "expr": "if(bob.y > 1, bob.y, 0)"}]})
        self.assertEqual(errors, [])


class Accounts(unittest.TestCase):
    def test_password_hashing(self):
        stored = db.hash_password("correct horse")
        self.assertTrue(db.check_password("correct horse", stored))
        self.assertFalse(db.check_password("wrong", stored))
        self.assertFalse(db.check_password("x", None))


class SpendingGuards(unittest.TestCase):
    def test_daily_model_budget_stops_calls(self):
        saved = server.DAILY_MODEL_CALLS
        server.DAILY_MODEL_CALLS = 2
        server._budget.update(day="", used=0)
        try:
            server.spend_model_call()
            server.spend_model_call()
            with self.assertRaises(RuntimeError):
                server.spend_model_call()
        finally:
            server.DAILY_MODEL_CALLS = saved
            server._budget.update(day="", used=0)

    def test_agy_cli_never_runs_on_a_server_with_accounts(self):
        os.environ["AGY_CLI"] = "1"
        try:
            server.AUTH_REQUIRED = True
            self.assertFalse(server.agy_cli_allowed())
        finally:
            server.AUTH_REQUIRED = False
            os.environ.pop("AGY_CLI", None)


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(server.app, base_url=LOCAL)
        cls.c = cls.ctx.__enter__()  # runs startup: database + migrations

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def tearDown(self):
        server.AUTH_REQUIRED = False

    def test_foreign_host_is_rejected(self):
        self.assertEqual(self.c.get("/api/status", headers={"Host": "evil.example"}).status_code, 403)

    def test_topic_ids_cannot_escape_the_folder(self):
        self.assertEqual(self.c.post("/api/topics", json=topic("../../escape")).status_code, 422)
        self.assertFalse((Path(TMP.name).parent / "escape.json").exists())

    def test_topic_roundtrip_and_migration(self):
        r = self.c.post("/api/topics", json=topic(quiz=[{"question": "q", "options": ["a", "b"], "correct": 1}],
                                                  cheatSheet=[{"name": "Law", "formula": "F=ma"}]))
        self.assertEqual(r.status_code, 200)
        saved = self.c.get("/api/topics/test-topic").json()
        self.assertEqual(saved["quiz"][0]["correctAnswer"], 1)
        self.assertEqual(saved["cheatSheet"][0]["label"], "Law")

    def test_events_do_not_replay_on_first_poll(self):
        self.c.post("/api/agy/events", json={"type": "SWITCH_TAB", "payload": {"tab": "quiz"}})
        first = self.c.get("/api/agy/events").json()
        self.assertEqual(first["events"], [])
        self.c.post("/api/agy/events", json={"type": "SWITCH_TAB", "payload": {"tab": "theory"}})
        later = self.c.get(f"/api/agy/events?since={first['cursor']}").json()
        self.assertEqual([e["payload"]["tab"] for e in later["events"]], ["theory"])

    def test_sandbox_hides_api_keys(self):
        os.environ["api_KEY"] = os.environ.get("api_KEY") or "test-secret"
        out = self.c.post("/api/execute-code", json={"code": "import os\nprint(os.environ.get('api_KEY'))"}).json()
        self.assertEqual(out["stdout"].strip(), "None")

    def test_class_adaptation_after_a_weak_quiz(self):
        user = db.get_or_create_user("Adapt Tester")
        course = db.create_course(user["id"], "Course", "goal", "", [])
        db.replace_classes(course["id"], [{"title": "One"}, {"title": "Two"}])
        k1, k2 = db.list_classes(course["id"])
        self.c.post("/api/topics", json=topic("adapt-one", quiz=[{"question": "q", "options": ["a", "b"], "correctAnswer": 0}],
                                              source={"courseId": course["id"]}))
        db.update_class(k1["id"], status="ready", topic_id="adapt-one")
        db.update_class(k2["id"], status="ready", topic_id="adapt-two")
        server.queue_course_generation = lambda cid: None  # no model calls in tests
        r = self.c.post("/api/quiz/submit", json={"userId": user["id"], "topicId": "adapt-one", "questionId": "q1",
                                                  "selected": 1, "isCorrect": False}).json()
        self.assertEqual(r["classProgress"]["adapted"], {"seq": 2, "direction": "easier"})
        k2 = db.list_classes(course["id"])[1]
        self.assertEqual(k2["status"], "pending")
        self.assertIn("Slow down", k2["instruction"])

    def test_adaptation_never_rewrites_an_opened_class(self):
        user = db.get_or_create_user("Open Tester")
        course = db.create_course(user["id"], "Course", "goal", "", [])
        db.replace_classes(course["id"], [{"title": "One"}, {"title": "Two"}])
        k1, k2 = db.list_classes(course["id"])
        self.c.post("/api/topics", json=topic("open-one", quiz=[{"question": "q", "options": ["a", "b"], "correctAnswer": 0}],
                                              source={"courseId": course["id"]}))
        self.c.post("/api/topics", json=topic("open-two", source={"courseId": course["id"]}))
        db.update_class(k1["id"], status="ready", topic_id="open-one")
        db.update_class(k2["id"], status="ready", topic_id="open-two")
        self.assertEqual(self.c.post("/api/topics/open-two/opened").status_code, 200)  # student peeks at class 2
        server.queue_course_generation = lambda cid: None
        r = self.c.post("/api/quiz/submit", json={"userId": user["id"], "topicId": "open-one", "questionId": "q1",
                                                  "selected": 1, "isCorrect": False}).json()
        self.assertIsNone(r["classProgress"]["adapted"])
        self.assertEqual(db.list_classes(course["id"])[1]["status"], "ready")

    def test_generation_is_rate_limited(self):
        server.RATE_SCALE = 0.1  # simulation limit 20 -> 2 per hour
        try:
            codes = [self.c.post("/api/simulations/generate", json={"topicId": "no-such-topic"}).status_code for _ in range(3)]
        finally:
            server.RATE_SCALE = 1.0
            server._rate_hits.clear()
        self.assertEqual(codes, [404, 404, 429])

    def test_interrupted_planning_is_found_for_resume(self):
        user = db.get_or_create_user("Planner Tester")
        course = db.create_course(user["id"], "Interrupted", "goal", "materials", [])
        self.assertIn(course["id"], [c["id"] for c in db.interrupted_planning()])

    def test_accounts_keep_courses_private(self):
        server.AUTH_REQUIRED = True
        self.assertEqual(self.c.get("/api/topics").status_code, 401)
        no_age = self.c.post("/api/auth/register", json={"name": "Kid Test", "password": "correct horse"})
        self.assertEqual(no_age.status_code, 422)  # Gemini API terms: users must be 18+
        a = self.c.post("/api/auth/register", json={"name": "Ana Test", "password": "correct horse", "adult": True}).json()
        b = self.c.post("/api/auth/register", json={"name": "Ben Test", "password": "battery staple", "adult": True}).json()
        ha, hb = {"Authorization": f"Bearer {a['token']}"}, {"Authorization": f"Bearer {b['token']}"}
        course = self.c.post("/api/courses", headers=ha, json={"userId": b["user"]["id"],
                             "goal": "A goal long enough to be accepted by the server"}).json()["course"]
        self.assertEqual(course["user_id"], a["user"]["id"])  # forged owner id is ignored
        self.assertEqual(self.c.get(f"/api/courses/{course['id']}", headers=ha).status_code, 200)
        self.assertEqual(self.c.get(f"/api/courses/{course['id']}", headers=hb).status_code, 404)
        self.assertEqual(self.c.get(f"/api/users/{a['user']['id']}/courses", headers=hb).status_code, 403)
        self.assertEqual(self.c.post("/api/auth/login", json={"name": "Ana Test", "password": "nope"}).status_code, 401)
        self.c.post("/api/auth/logout", headers=hb)
        self.assertEqual(self.c.get("/api/topics", headers=hb).status_code, 401)


if __name__ == "__main__":
    unittest.main()
