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
os.environ["api_KEY"] = ""          # set before import: load_dotenv() does not override existing variables
os.environ["GEMINI_API_KEY"] = ""
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import engage  # noqa: E402
import server  # noqa: E402


def _offline(*args, **kwargs):
    raise RuntimeError("Gemini API key is not configured in .env (tests run offline)")


server.call_gemini = _offline  # no test may spend real model quota
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

    def test_code_exercises_need_real_tests(self):
        items = server.normalize_practice([
            {"type": "code", "prompt": "p", "starter": "def f(x):\n    pass", "tests": "assert f(1) == 2", "solution": "def f(x):\n    return 2 * x"},
            {"type": "code", "prompt": "p", "starter": "", "tests": "print('no asserts')"},
        ])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["language"], "python")
        self.assertIn("assert", items[0]["tests"])


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
        os.environ["api_KEY"] = "test-secret"  # only to prove the sandbox can't see it
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

    def test_test_prep_mode_reaches_the_prompts(self):
        user = db.get_or_create_user("Prep Tester")
        server.start_plan_job, real = (lambda *a: {"id": "job-x"}), server.start_plan_job
        try:
            r = self.c.post("/api/courses", json={"userId": user["id"], "goal": "Chem 121 final on stoichiometry and gases",
                                                  "mode": "test_prep", "exam_date": "2026-12-10"}).json()
        finally:
            server.start_plan_job = real
        course = db.get_course(r["course"]["id"])
        self.assertEqual((course["mode"], course["exam_date"]), ("test_prep", "2026-12-10"))
        self.assertIn("Mock exam", server.mode_rules(course))
        self.assertIn("MOCK EXAM", server.mode_adjustment(course, {"title": "Mock exam: Chemistry"}))
        self.assertEqual(server.mode_rules({"mode": "learn"}), "")

    def test_continue_course_appends_classes(self):
        user = db.get_or_create_user("Extend Tester")
        course = db.create_course(user["id"], "Course", "goal", "old notes", [])
        db.update_course(course["id"], status="ready", concepts=[{"id": "c1", "name": "One", "summary": ""}])
        db.replace_classes(course["id"], [{"title": "One"}, {"title": "Two"}])

        async def fake_plan(prompt, role=None):
            self.assertIn("1. One", prompt)
            return {"concepts": [{"id": "c2", "name": "Two b"}], "classes": [{"title": "Three", "concepts": ["c2", "zz"]}]}
        server.gemini_json, real = fake_plan, server.gemini_json
        server.queue_course_generation, real_q = (lambda cid: None), server.queue_course_generation
        try:
            r = self.c.post(f"/api/courses/{course['id']}/extend", json={"materials_text": "new chapter on angular momentum"})
            self.assertEqual(r.status_code, 200)
            for _ in range(50):
                if server.JOBS[r.json()["job"]["id"]]["status"] in ("done", "error"):
                    break
                import time; time.sleep(0.05)
        finally:
            server.gemini_json, server.queue_course_generation = real, real_q
        classes = db.list_classes(course["id"])
        self.assertEqual([(k["seq"], k["title"]) for k in classes][-1], (3, "Three"))
        self.assertEqual(classes[-1]["concepts"], ["c2"])
        updated = db.get_course(course["id"])
        self.assertTrue(updated["materials_text"].startswith("--- Added"))
        self.assertEqual([c["id"] for c in updated["concepts"]], ["c1", "c2"])

    def test_math_answers_are_recomputed(self):
        async def fake(prompt, role=None):
            return {"title": "t", "practice": [
                {"type": "numeric", "prompt": "right", "answer": 4.24, "compute": "3*sqrt(2)", "explanation": ""},
                {"type": "numeric", "prompt": "wrong key", "answer": 5, "compute": "2+2", "explanation": ""},
                {"type": "numeric", "prompt": "sneaky", "answer": 1, "compute": "__import__('os')", "explanation": ""}]}
        server.gemini_json, real = fake, server.gemini_json
        try:
            r = self.c.post("/api/math/practice", json={"topic": "radicals"}).json()
        finally:
            server.gemini_json = real
        self.assertEqual([i["prompt"] for i in r["items"]], ["right"])
        self.assertAlmostEqual(r["items"][0]["answer"], 4.242641, places=5)
        self.assertEqual(r["dropped"], 2)

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


class Engagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(server.app, base_url=LOCAL)
        cls.c = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)

    def user(self, name):
        return db.get_or_create_user(name)["id"]

    def test_xp_pays_once_and_amounts_are_server_side(self):
        u = self.user("Xp Tester")
        first = engage.award(u, "2026-11-01", "practice_correct", "t:p1")
        again = engage.award(u, "2026-11-01", "practice_correct", "t:p1")
        self.assertEqual((first["xp"], again["xp"]), (8, 0))
        self.assertTrue(first["streakExtended"])
        self.assertEqual(engage.award(u, "2026-11-02", "practice_correct", "t:p1")["xp"], 8)  # new day
        self.assertEqual(engage.award(u, "2026-11-03", "ide_solved", "p")["xp"], 15)
        self.assertEqual(engage.award(u, "2026-11-04", "ide_solved", "p")["xp"], 0)       # once ever
        r = self.c.post(f"/api/engage/{u}/xp", json={"source": "quests_bonus", "ref": "x"})
        self.assertEqual(r.status_code, 422)                                                   # not client-reportable

    def test_streak_freeze_covers_one_missed_day(self):
        u = self.user("Streak Tester")
        for d in ("2026-10-01", "2026-10-02", "2026-10-03"):
            engage.award(u, d, "lesson_read", d)
        self.assertEqual(engage.streak_info(u, "2026-10-03")["streak"], 3)
        self.assertEqual(engage.streak_info(u, "2026-10-04")["streak"], 3)    # not done today yet: still alive
        engage.award(u, "2026-10-05", "lesson_read", "x")                    # missed the 4th, one freeze spent
        self.assertEqual(engage.streak_info(u, "2026-10-05")["streak"], 5)
        self.assertEqual(engage.prefs(u)["freezes"], 0)
        engage.award(u, "2026-10-08", "lesson_read", "y")                    # two missed days, no freeze left
        self.assertEqual(engage.streak_info(u, "2026-10-08")["streak"], 1)
        self.assertEqual(engage.streak_info(u, "2026-10-08")["longest"], 5)

    def test_goal_and_badges(self):
        u = self.user("Goal Tester")
        engage.set_prefs(u, daily_goal=10)
        r1 = engage.award(u, "2026-09-01", "practice_correct", "a")
        r2 = engage.award(u, "2026-09-01", "practice_correct", "b")
        self.assertFalse(r1["goalReached"])
        self.assertTrue(r2["goalReached"])
        self.assertIn("first_steps", [b["id"] for b in r1["newBadges"]])

    def test_missed_quiz_question_comes_back_spaced(self):
        u = self.user("Review Tester")
        self.c.post("/api/topics", json=topic("review-topic", quiz=[{"id": "q1", "question": "2+2?", "options": ["3", "4"], "correctAnswer": 1}]))
        r = self.c.post("/api/quiz/submit", json={"userId": u, "topicId": "review-topic", "questionId": "q1", "selected": 0, "isCorrect": False},
                        headers={"X-Local-Day": engage.utc_day()}).json()
        self.assertEqual(r["rewards"]["xp"], 2)
        tomorrow = engage._shift(engage.utc_day(), 1)
        self.assertEqual(self.c.get(f"/api/review/{u}/session").json()["questions"], [])     # not due today
        s = self.c.get(f"/api/review/{u}/session", headers={"X-Local-Day": tomorrow}).json()["questions"]
        self.assertEqual([(q["questionId"], "correctAnswer" in q) for q in s], [("q1", False)])  # key not sent
        a = self.c.post(f"/api/review/{u}/answer", json={"topicId": "review-topic", "questionId": "q1", "selected": 1},
                        headers={"X-Local-Day": tomorrow}).json()
        self.assertTrue(a["correct"])
        self.assertEqual(a["nextReview"], engage._shift(tomorrow, 3))
        self.assertEqual(a["rewards"]["xp"], 6)

    def test_forged_day_is_ignored(self):
        self.assertEqual(engage.clean_day("1999-01-01"), engage.utc_day())
        self.assertEqual(engage.clean_day("nonsense"), engage.utc_day())

    def test_quests_are_stable_for_a_day(self):
        u = self.user("Quest Tester")
        q1 = [q["id"] for q in engage.quests(u, "2026-08-01")]
        q2 = [q["id"] for q in engage.quests(u, "2026-08-01")]
        self.assertEqual(q1, q2)
        self.assertEqual(len(q1), 3)
        self.assertEqual(q1[0], "xp")


class Workspaces(unittest.TestCase):
    def test_every_math_widget_validates(self):
        from simspec import MATH_WIDGETS
        minimal = {"epsilon_delta": {"f": "x^2", "a": 2, "L": 4}, "epsilon_n": {"term": "1/n", "L": 0},
                   "secant_tangent": {"f": "sin(x)", "a": 1}, "riemann": {"f": "x^2", "a": 0, "b": 2},
                   "series": {"term": "x^k / fact(k)", "target": "exp(x)"}, "unit_circle": {},
                   "parametric": {"x": "cos(t)", "y": "sin(t)"}, "vector_field": {"P": "-y", "Q": "x"}, "transform2d": {}}
        self.assertEqual(set(minimal), set(MATH_WIDGETS))
        for widget, fields in minimal.items():
            clean, errors = validate_spec({"kind": "math", "widget": widget, **fields})
            self.assertEqual(errors, [], widget)
            self.assertTrue(clean["params"] or widget == "vector_field", widget)  # the widget's sliders were added

    def test_math_specs_reject_unknown_names_and_widgets(self):
        self.assertTrue(validate_spec({"kind": "math", "widget": "epsilon_delta", "f": "x + y", "a": 0, "L": 0})[1])
        self.assertTrue(validate_spec({"kind": "math", "widget": "fourier_magic"})[1])

    def test_workspace_guess(self):
        self.assertEqual(server.guess_workspace("Calculus", "Precise Limit Definition"), "math")
        self.assertEqual(server.guess_workspace("Python", "Loops"), "code")
        self.assertEqual(server.guess_workspace("Python for statistics"), "code")
        self.assertEqual(server.guess_workspace("Physics", "Motion in Two Dimensions"), "lab")

    def test_course_topics_carry_their_workspace(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            user = db.get_or_create_user("Workspace Tester")
            course = db.create_course(user["id"], "Limits", "epsilon delta proofs", "", [])
            db.update_course(course["id"], subject="Calculus")
            c.post("/api/topics", json=topic("ws-class", source={"courseId": course["id"], "courseTitle": "Limits"}))
            self.assertEqual(c.get("/api/topics/ws-class").json()["source"]["workspace"], "math")
            db.update_course(course["id"], workspace="lab")  # an explicit choice wins over the guess
            self.assertEqual(c.get("/api/topics/ws-class").json()["source"]["workspace"], "lab")
