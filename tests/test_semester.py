"""Semester courses (mode "semester"): the whole term is outlined up front, class 1 is written, the rest stay
"planned" and are released one at a time as the student gets close. Models are stubbed; nothing calls Gemini."""
from test_lab import LOCAL, TestClient, server, db, engage, topic  # noqa: F401  (sets up the temp content dir first)

import asyncio
import json
import threading
import time
import unittest
import uuid
from unittest import mock

import advisor

REAL_QUEUE = server.queue_course_generation  # some test_lab tests replace it for good; captured at import


def setUpModule():
    # test_lab's tearDownModule removes the shared temp dir; recreate what these tests need
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    server.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()
    advisor.init()


def statuses(course_id):
    return [k["status"] for k in db.list_classes(course_id)]


def wait_for(job_id, timeout=5.0):
    deadline = time.time() + timeout
    while server.JOBS[job_id]["status"] in ("queued", "running") and time.time() < deadline:
        time.sleep(0.02)
    return server.JOBS[job_id]


class Semester(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(server.app, base_url=LOCAL)
        cls.c = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)
        db.close_all()

    def setUp(self):
        self.scale, server.RATE_SCALE = server.RATE_SCALE, 0  # rate limits are tested elsewhere
        self.queued = []
        self.patches = [mock.patch.object(server, "queue_course_generation", lambda cid: self.queued.append(cid))]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        server.RATE_SCALE = self.scale
        server.AUTH_REQUIRED = False

    def course(self, layout, mode="semester", **fields):
        """layout: one status per class, e.g. "rpp" = ready, planned, planned ("c" = ready and completed)."""
        user = db.get_or_create_user(f"Sem {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Semester", "goal", "", [], mode)
        db.update_course(course["id"], status="ready", concepts=[{"id": "c1", "name": "One", "summary": ""}],
                         diagnostic=[{"id": "q1"}], **fields)
        names = {"r": "ready", "c": "ready", "p": "planned", "n": "pending", "g": "generating", "e": "error"}
        db.replace_classes(course["id"], [{"title": f"Class {i + 1}", "status": names[s],
                                           "meta": {"week": i // 2 + 1, "unit": "Unit A", "kind": "lesson"}}
                                          for i, s in enumerate(layout)])
        for k, s in zip(db.list_classes(course["id"]), layout):
            if s == "c":
                db.update_class(k["id"], completed=1)
        return db.get_course(course["id"]), user

    # ---- planning ----
    def plan(self, syllabus):
        user = db.get_or_create_user(f"Planner {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Physics 101", "PHYS 101 this fall", "kinematics notes", [], "semester")
        db.update_course(course["id"], plan_classes=30, weeks=15)
        prompts = []

        async def fake_json(prompt, temperature=0.4, role=None):
            prompts.append(prompt)
            if "DIAGNOSTIC quiz" in prompt:
                return {"title": "Physics 101", "subject": "Physics", "workspace": "lab",
                        "concepts": [{"id": "kin", "name": "Kinematics"}, {"id": "dyn", "name": "Dynamics"}],
                        "questions": [{"question": f"Q{i}?", "options": ["a", "b", "c", "d"], "correctAnswer": i % 4,
                                       "concept": "kin"} for i in range(4)]}
            return syllabus()

        async def same(questions, *a, **k):
            return questions

        with mock.patch.object(server, "gemini_json", fake_json), mock.patch.object(server, "verify_questions", same):
            asyncio.run(server.plan_course(course["id"], {"id": "job-semester-test"}, 4, 30))
        return course["id"], prompts

    def test_plan_stores_every_class_first_pending_rest_planned(self):
        def syllabus():
            items = [{"title": f"Class {i + 1}", "concepts": ["kin"], "objectives": ["o1", "o2"], "week": i // 2 + 1,
                      "unit": "Motion" * 20, "kind": "lesson"} for i in range(35)]
            items[3].update(week=99, kind="bogus")  # out of range week, unknown kind
            items[-1]["kind"] = "final"
            return {"classes": items}

        cid, prompts = self.plan(syllabus)
        self.assertIn("SEMESTER course over 15 weeks", prompts[-1])
        classes = db.list_classes(cid)
        self.assertEqual(len(classes), 32)  # semester outline cap
        self.assertEqual(statuses(cid), ["pending"] + ["planned"] * 31)
        self.assertEqual(classes[3]["meta"]["kind"], "lesson")
        self.assertLessEqual(classes[3]["meta"]["week"], 15)
        self.assertEqual(len(classes[0]["meta"]["unit"]), 60)
        weeks = [k["meta"]["week"] for k in classes]
        self.assertEqual(weeks, sorted(weeks))  # never decreasing
        body = self.c.get(f"/api/courses/{cid}").json()
        self.assertEqual(body["plannedCount"], 31)

    def test_truncated_or_invalid_outline_falls_back_to_concepts(self):
        def truncated():
            raise json.JSONDecodeError("Unterminated string", '{"classes": [{"title": "Cla', 26)
        for reply in (truncated, lambda: ["not", "an", "object"], lambda: {"classes": "nope"}):
            cid, _ = self.plan(reply)
            classes = db.list_classes(cid)
            self.assertEqual([k["title"] for k in classes], ["Kinematics", "Dynamics"])
            self.assertEqual(statuses(cid), ["pending", "planned"])
            self.assertTrue(all(1 <= k["meta"]["week"] <= 15 for k in classes))

    # ---- writing and releasing ----
    def test_loop_writes_only_class_one(self):
        course, _ = self.course("nppp")
        built = []

        async def fake_build(course_row, klass, classes, on_step=None):
            built.append(klass["seq"])
            tid = f"sem-{uuid.uuid4().hex[:6]}"
            saved, _ = server.save_topic({"id": tid, "title": klass["title"], "category": "Physics", "markdownContent": "# x",
                                          "source": {"kind": "course", "courseId": course_row["id"]}}, course_id=course_row["id"])
            return saved

        with mock.patch.object(server, "build_class", fake_build), mock.patch.object(server, "queue_course_generation", REAL_QUEUE):
            job = server.queue_course_generation(course["id"])
            self.assertEqual(wait_for(job["id"])["status"], "done")
        self.assertEqual(built, [1])
        self.assertEqual(statuses(course["id"]), ["ready", "planned", "planned", "planned"])
        self.assertEqual(db.get_course(course["id"])["status"], "ready")  # "ready" = nothing waiting to be written

    def test_quiz_completion_releases_exactly_one_class(self):
        course, user = self.course("rppp")
        tid = f"semq-{uuid.uuid4().hex[:6]}"
        self.c.post("/api/topics", json=topic(tid, quiz=[{"question": "q", "options": ["a", "b"], "correctAnswer": 0}],
                                              source={"courseId": course["id"]}))
        db.update_class(db.list_classes(course["id"])[0]["id"], topic_id=tid)
        r = self.c.post("/api/quiz/submit", json={"userId": user["id"], "topicId": tid, "questionId": "q1",
                                                  "selected": 0, "isCorrect": True}).json()
        self.assertTrue(r["classProgress"]["released"])
        self.assertEqual(r["classProgress"]["adapted"], {"seq": 2, "direction": "harder"})
        self.assertEqual(statuses(course["id"]), ["ready", "pending", "planned", "planned"])
        k2 = db.list_classes(course["id"])[1]
        self.assertIn("move faster", k2["instruction"])  # adapted before release, so the written class gets it
        self.assertEqual(self.queued, [course["id"]])
        # answering again (already completed) releases nothing more
        self.c.post("/api/quiz/submit", json={"userId": user["id"], "topicId": tid, "questionId": "q1",
                                              "selected": 0, "isCorrect": True})
        self.assertEqual(statuses(course["id"]).count("pending"), 1)

    def test_opening_a_class_releases_the_next(self):
        course, _ = self.course("rpp")
        tid = f"semo-{uuid.uuid4().hex[:6]}"
        self.c.post("/api/topics", json=topic(tid, source={"courseId": course["id"]}))
        db.update_class(db.list_classes(course["id"])[0]["id"], topic_id=tid)
        self.assertEqual(self.c.post(f"/api/topics/{tid}/opened").status_code, 200)
        self.assertEqual(statuses(course["id"]), ["ready", "pending", "planned"])

    def test_release_gate_and_concurrent_release(self):
        ahead, _ = self.course("rrpp")  # two written, unfinished classes ahead: wait
        self.assertFalse(db.release_next_planned(ahead["id"]))
        busy, _ = self.course("cnpp")  # one already waiting to be written
        self.assertFalse(db.release_next_planned(busy["id"]))
        failed, _ = self.course("cepp")
        self.assertFalse(db.release_next_planned(failed["id"]))

        course, _ = self.course("cpppp")
        barrier, results = threading.Barrier(6), []

        def release():
            barrier.wait()
            try:
                results.append(db.release_next_planned(course["id"]))
            finally:
                db.close_conn()
        threads = [threading.Thread(target=release) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(True), 1)
        self.assertEqual(statuses(course["id"]), ["ready", "pending", "planned", "planned", "planned"])
        self.assertFalse(server.release_next_class(course["id"]))  # double release: nothing more
        self.assertEqual(self.queued, [])

    def test_adapt_on_a_planned_class_stores_the_instruction_only(self):
        course, _ = self.course("cpp")
        out = server.adapt_next_class({"courseId": course["id"], "seq": 1, "score": 0.2})
        self.assertEqual(out, {"seq": 2, "direction": "easier"})
        k2 = db.list_classes(course["id"])[1]
        self.assertEqual((k2["status"], k2["adapted_from"]), ("planned", 0.2))
        self.assertIn("Slow down", k2["instruction"])
        self.assertEqual(self.queued, [])

    def test_regenerate_on_a_planned_class_keeps_it_planned(self):
        course, _ = self.course("rpp")
        r = self.c.post(f"/api/courses/{course['id']}/classes/3/regenerate", json={"instruction": "more vectors"})
        self.assertEqual(r.status_code, 200)
        k3 = db.list_classes(course["id"])[2]
        self.assertEqual((k3["status"], k3["instruction"]), ("planned", "more vectors"))
        self.assertEqual(self.queued, [])

    def test_write_it_now_endpoint(self):
        course, _ = self.course("rrpp")  # the release gate would wait; "write it now" doesn't
        base = f"/api/courses/{course['id']}/classes"
        self.assertEqual(self.c.post(f"{base}/99/generate").status_code, 404)
        self.assertEqual(self.c.post(f"{base}/1/generate").status_code, 409)  # already written
        self.assertEqual(self.c.post(f"{base}/4/generate").status_code, 400)  # out of order
        r = self.c.post(f"{base}/3/generate")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["plannedCount"], 1)
        self.assertEqual(statuses(course["id"]), ["ready", "ready", "pending", "planned"])
        self.assertEqual(self.queued, [course["id"]])
        self.assertEqual(self.c.post(f"{base}/3/generate").status_code, 409)  # double click
        self.assertEqual(self.c.post(f"{base}/4/generate").status_code, 409)  # class 3 is still being written
        self.assertEqual(self.queued, [course["id"]])

    def test_extend_appends_planned_classes(self):
        course, _ = self.course("cc")

        async def fake_plan(prompt, temperature=0.4, role=None):
            self.assertIn("SEMESTER course", prompt)
            return {"concepts": [], "classes": [{"title": "New A", "week": 9}, {"title": "New B", "kind": "review"}]}

        with mock.patch.object(server, "gemini_json", fake_plan):
            r = self.c.post(f"/api/courses/{course['id']}/extend", json={"materials_text": "a new unit on rotational motion"})
            self.assertEqual(r.status_code, 200)
            wait_for(r.json()["job"]["id"])
        classes = db.list_classes(course["id"])
        self.assertEqual([k["status"] for k in classes], ["ready", "ready", "pending", "planned"])
        self.assertEqual([k["meta"]["week"] for k in classes[2:]], [9, 2])  # given week kept, else after the last week
        self.assertEqual(classes[3]["meta"]["kind"], "review")
        self.assertEqual(self.queued, [course["id"]])

    # ---- modes, prompts and schema ----
    def test_class_count_caps_per_mode(self):
        user = db.get_or_create_user(f"Caps {uuid.uuid4().hex[:6]}")
        goal = "Physics 101 mechanics for the whole fall term"
        cases = [({"mode": "learn", "class_count": 50}, ("learn", 12, None)),
                 ({"mode": "nonsense", "class_count": 5}, ("learn", 5, None)),
                 ({"mode": "semester", "class_count": 50}, ("semester", 30, 15)),
                 ({"mode": "semester", "weeks": 10}, ("semester", 20, 10)),
                 ({"mode": "semester", "weeks": 40}, ("semester", 30, 20)),
                 ({"mode": "semester"}, ("semester", 24, 12))]
        with mock.patch.object(server, "start_plan_job", lambda *a: {"id": "job-x"}):
            for body, want in cases:
                r = self.c.post("/api/courses", json={"userId": user["id"], "goal": goal, **body})
                self.assertEqual(r.status_code, 200, body)
                c = db.get_course(r.json()["course"]["id"])
                self.assertEqual((c["mode"], c["plan_classes"], c["weeks"]), want, body)

    def test_review_kinds_reach_the_class_prompt(self):
        course = {"mode": "semester", "weeks": 15, "plan_classes": 30}
        self.assertIn("FINAL REVIEW", server.mode_adjustment(course, {"title": "Wrap-up", "meta": {"kind": "final"}}))
        self.assertIn("MIDTERM", server.mode_adjustment(course, {"title": "Mid", "meta": {"kind": "midterm"}}))
        self.assertIn('UNIT REVIEW (unit "Motion")', server.mode_adjustment(course, {"title": "R", "meta": {"kind": "review", "unit": "Motion"}}))
        self.assertIn("week 3 of 15", server.mode_adjustment(course, {"title": "L", "meta": {"kind": "lesson", "week": 3}}))
        self.assertIn("about 2 classes a week", server.mode_rules(course))
        self.assertEqual(server.mode_adjustment({"mode": "learn"}, {"title": "x", "meta": {}}), "")

    def test_init_db_is_idempotent_and_meta_defaults_to_an_object(self):
        db.init_db()
        db.init_db()
        cols = {r["name"] for r in db.conn().execute("PRAGMA table_info(classes)")}
        self.assertIn("meta", cols)
        self.assertIn("weeks", {r["name"] for r in db.conn().execute("PRAGMA table_info(courses)")})
        course, _ = self.course("r", mode="learn")
        k = db.list_classes(course["id"])[0]
        db.conn().execute("UPDATE classes SET meta = '' WHERE id = ?", (k["id"],))
        db.conn().commit()
        self.assertEqual(db.list_classes(course["id"])[0]["meta"], {})
        db.append_classes(course["id"], [{"title": "Plain"}])
        self.assertEqual((db.list_classes(course["id"])[1]["status"], db.list_classes(course["id"])[1]["meta"]), ("pending", {}))


if __name__ == "__main__":
    unittest.main()
