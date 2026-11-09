"""Problem sprints (mode "problem_sprint") and reference-only courses (mode "thematic_reference"). Models are stubbed;
nothing calls Gemini. The sprint's steps and answers live only in classes.meta.sprint and come out one step at a time."""
from test_lab import LOCAL, TestClient, server, db, engage, topic  # noqa: F401  (sets up the temp content dir first)

import asyncio
import json
import time
import unittest
import uuid
from unittest import mock

import advisor
import mcp_server
import sprint

PROBLEM = {
    "given": [{"symbol": "$v_0$", "value": "2 m/s"}],
    "parts": [
        {"id": "a", "prompt": "Find the speed after 5 s.", "steps": ["SECRET-STEP-A1", "SECRET-STEP-A2", "SECRET-STEP-A3"],
         "answer": 12.0, "unit": "m/s", "tolerance": 0.02, "compute": "2 + 2*5"},
        {"id": "b", "prompt": "Find the distance.", "steps": ["SECRET-STEP-B1", "SECRET-STEP-B2"],
         "answer": 99.0, "unit": "m", "compute": "3*3"},  # stated answer disagrees with compute: no auto-check
    ],
    "pitfalls": ["Forgetting the initial speed"],
}


def lesson_reply(problem=PROBLEM, practice=None):
    return {"title": "Problem 1", "category": "Physics", "summary": "s", "markdownContent": "# Problem 1\n\nWhat you need.",
            "quiz": [{"id": "q1", "question": "Which is a rate?", "options": ["speed", "mass", "time", "length"], "correctAnswer": 0}],
            "practice": practice if practice is not None else [
                {"type": "numeric", "prompt": "A cart starts at 4 m/s and gains 8 m/s. Final speed?", "answer": 12.0, "unit": "m/s"},
                {"type": "numeric", "prompt": "A cart moves 3 m/s for 2 s. Distance?", "answer": 6.0, "unit": "m"},
                {"type": "true_false", "prompt": "Speed can be negative.", "answer": False}],
            **({"problem": problem} if problem is not None else {})}


async def same(questions, *a, **k):
    return questions


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    server.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()
    advisor.init()


class SprintBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(server.app, base_url=LOCAL)
        cls.c = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)
        db.close_all()

    def setUp(self):
        self.scale, server.RATE_SCALE = server.RATE_SCALE, 0
        self.queued = []
        self.patches = [mock.patch.object(server, "queue_course_generation", lambda cid: self.queued.append(cid)),
                        mock.patch.object(server, "verify_questions", same),
                        mock.patch.object(server, "AUTHOR_SIMS", False)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        server.RATE_SCALE = self.scale
        server.AUTH_REQUIRED = False

    def build(self, klass, course, reply):
        async def fake_json(prompt, temperature=0.4, role=None):
            self.prompts.append(prompt)
            return reply
        self.prompts = []
        with mock.patch.object(server, "gemini_json", fake_json):
            saved = asyncio.run(server.build_class(course, klass, db.list_classes(course["id"])))
        db.update_class(klass["id"], status="ready", topic_id=saved["id"])
        return saved

    def sprint_course(self, user_id=None, keep=False, problems=1, reply=None):
        """A sprint with a primer and `problems` problem classes, every class written with the stub lesson."""
        user_id = user_id or db.get_or_create_user(f"Sprinter {uuid.uuid4().hex[:6]}")["id"]
        course = db.create_course(user_id, "Kinematics sprint", "explain my homework", "Problem 1. A cart...", [], "problem_sprint")
        db.update_course(course["id"], status="ready", auto_cleanup=0 if keep else 1,
                         concepts=[{"id": "kin", "name": "Kinematics", "summary": ""}])
        db.replace_classes(course["id"], [{"title": "What you need", "meta": sprint.sprint_meta("primer"), "status": "ready"}]
                           + [{"title": f"Problem {i}", "meta": sprint.sprint_meta("problem", i, f"A cart starts at 2 m/s ({i})")}
                              for i in range(1, problems + 1)])
        course = db.get_course(course["id"])
        for k in db.list_classes(course["id"])[1:]:
            self.build(k, course, reply or lesson_reply())
        return db.get_course(course["id"]), user_id

    def problem(self, cid, seq=2):
        return next(k for k in db.list_classes(cid) if k["seq"] == seq)

    def public_parts(self, cid, seq=2, headers=None):
        body = self.c.get(f"/api/courses/{cid}", headers=headers or {}).json()
        return {p["id"]: p for p in next(k for k in body["classes"] if k["seq"] == seq)["meta"]["sprint"]["parts"]}


class CreateAndPlan(SprintBase):
    def test_mode_whitelist_and_keep_flag(self):
        user = db.get_or_create_user(f"Modes {uuid.uuid4().hex[:6]}")
        with mock.patch.object(server, "start_plan_job", lambda *a: {"id": "job-x"}):
            def make(**extra):
                body = {"userId": user["id"], "goal": "Explain my kinematics homework please", **extra}
                return self.c.post("/api/courses", json=body).json()["course"]
            sprint_default = make(mode="problem_sprint")
            kept = make(mode="problem_sprint", keep=True)
            ref = make(mode="thematic_reference", keep=True)
            bogus = make(mode="delete_everything")
        self.assertEqual((sprint_default["mode"], sprint_default["auto_cleanup"]), ("problem_sprint", 1))
        self.assertEqual((kept["mode"], kept["auto_cleanup"]), ("problem_sprint", 0))
        self.assertEqual((ref["mode"], ref["auto_cleanup"]), ("thematic_reference", 0))  # keep only applies to sprints
        self.assertEqual(bogus["mode"], "learn")
        self.assertIsNone(db.get_course(sprint_default["id"])["plan_classes"])

    def plan(self, reply):
        """Runs the real plan job (start_plan_job), which queues class writing once it is done."""
        user = db.get_or_create_user(f"Planner {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Sprint", "explain these", "Problem 1 ... Problem 2 ...", [], "problem_sprint")
        prompts = []

        async def fake_json(prompt, temperature=0.4, role=None):
            prompts.append(prompt)
            return reply

        with mock.patch.object(server, "gemini_json", fake_json):
            job = server.start_plan_job(course["id"], 8, None)
            deadline = time.time() + 5
            while server.JOBS[job["id"]]["status"] in ("queued", "running") and time.time() < deadline:
                time.sleep(0.02)
            time.sleep(0.05)  # the job's then() callback runs right after it is marked done
        return course["id"], prompts, server.JOBS[job["id"]]

    def test_sprint_is_primer_plus_one_class_per_problem_without_diagnostic(self):
        reply = {"title": "Kinematics homework", "subject": "Physics", "workspace": "lab",
                 "concepts": [{"id": "kin", "name": "Kinematics"}, {"id": "dyn", "name": "Dynamics"}],
                 "primer": {"title": "What you need", "concepts": ["kin"], "objectives": ["Use v = v0 + at"]},
                 "problems": [{"title": f"Problem {i}", "statement": f"Statement {i}", "concepts": ["kin", "nope"]} for i in range(1, 15)]}
        cid, prompts, job = self.plan(reply)
        self.assertEqual(job["status"], "done")
        self.assertEqual(len(prompts), 1)
        self.assertNotIn("DIAGNOSTIC quiz", prompts[0])
        self.assertIn("PROBLEM SPRINT", prompts[0])
        classes = db.list_classes(cid)
        self.assertEqual(len(classes), 12)  # primer + at most 11 problems
        self.assertEqual(classes[0]["meta"], {"kind": "primer"})
        self.assertEqual([k["meta"]["problemIndex"] for k in classes[1:]], list(range(1, 12)))
        self.assertEqual(classes[1]["meta"]["statement"], "Statement 1")
        self.assertEqual(classes[1]["concepts"], ["kin"])
        course = db.get_course(cid)
        self.assertEqual(course["diagnostic"], [])
        self.assertEqual((course["plan_classes"], course["status"]), (12, "generating"))
        self.assertEqual(self.queued, [cid])  # straight to writing classes, once the plan job is done

    def test_no_problems_found_is_an_error(self):
        cid, _, job = self.plan({"title": "x", "concepts": [], "problems": []})
        self.assertEqual(job["status"], "error")
        self.assertEqual(db.get_course(cid)["status"], "error")
        self.assertEqual(self.queued, [])

    def test_extend_is_blocked_and_resume_does_not_replan(self):
        course, _ = self.sprint_course()
        r = self.c.post(f"/api/courses/{course['id']}/extend", json={"goal": "Add more problems to this sprint please"})
        self.assertEqual(r.status_code, 409)
        with mock.patch.object(server, "start_plan_job", side_effect=AssertionError("replanned")):
            self.assertEqual(self.c.post(f"/api/courses/{course['id']}/resume").status_code, 200)

    def test_adaptation_is_skipped(self):
        course, _ = self.sprint_course(problems=2)
        self.assertIsNone(server.adapt_next_class({"courseId": course["id"], "seq": 1, "score": 0.1}))
        self.assertIsNone(self.problem(course["id"], 3)["instruction"])


class ProblemClass(SprintBase):
    def test_parts_go_to_class_meta_and_compute_is_rechecked(self):
        course, _ = self.sprint_course()
        self.assertIn("A cart starts at 2 m/s (1)", self.prompts[0])  # the statement reaches the class prompt
        meta = self.problem(course["id"])["meta"]
        parts = {p["id"]: p for p in meta["sprint"]["parts"]}
        self.assertEqual((parts["a"]["checked"], parts["a"]["answer"]), (True, 12.0))
        self.assertEqual((parts["b"]["checked"], parts["b"]["answer"]), (False, None))  # failed the recheck: no auto-check
        self.assertEqual(parts["b"]["steps"], ["SECRET-STEP-B1", "SECRET-STEP-B2"])  # but keeps its steps
        self.assertTrue(all("compute" not in p for p in parts.values()))
        self.assertEqual(meta["sprint"]["pitfalls"], ["Forgetting the initial speed"])

    def test_topic_json_has_no_steps_answers_or_echoing_practice(self):
        course, _ = self.sprint_course()
        tid = self.problem(course["id"])["topic_id"]
        for body in (self.c.get(f"/api/topics/{tid}").json(), json.loads(server.topic_path(tid).read_text()), db.get_lesson(tid)):
            text = json.dumps(body)
            self.assertNotIn("SECRET-STEP", text)
            self.assertNotIn("compute", text)
            self.assertEqual(body["sprintProblem"]["parts"], [{"id": "a", "prompt": "Find the speed after 5 s."},
                                                              {"id": "b", "prompt": "Find the distance."}])
            self.assertEqual(body["sprintProblem"]["pitfalls"], ["Forgetting the initial speed"])
            numeric = [p for p in body["practice"] if p["type"] == "numeric"]
            self.assertEqual([p["answer"] for p in numeric], [6.0])  # the item whose answer was 12 is gone
        listed = next(t for t in self.c.get("/api/topics").json() if t["id"] == tid)
        self.assertNotIn("SECRET-STEP", json.dumps(listed))

    def test_rewrite_without_parts_keeps_the_earlier_ones(self):
        course, _ = self.sprint_course()
        klass = self.problem(course["id"])
        self.build(klass, course, lesson_reply(problem=None))
        self.assertEqual(len(self.problem(course["id"])["meta"]["sprint"]["parts"]), 2)


class Unlocking(SprintBase):
    def test_answers_hidden_until_an_attempt_then_shown(self):
        course, _ = self.sprint_course()
        cid = course["id"]
        parts = self.public_parts(cid)
        self.assertEqual((parts["a"]["steps"], parts["a"]["stepCount"], parts["a"]["autoCheck"]), ([], 3, True))
        for p in parts.values():
            self.assertFalse({"answer", "unit", "tolerance", "compute"} & p.keys())
        text = self.c.get(f"/api/courses/{cid}").text
        self.assertNotIn("SECRET-STEP", text)
        self.assertNotIn("compute", text)

        # MCP get_course goes through the same API
        orig = mcp_server.call
        mcp_server.call = lambda method, path, body=None: self.c.request(method, path, json=body).json()
        try:
            via_mcp = mcp_server.BY_NAME["get_course"][2]({"course_id": cid})
        finally:
            mcp_server.call = orig
        self.assertNotIn("SECRET-STEP", json.dumps(via_mcp))
        self.assertNotIn('"answer"', json.dumps(via_mcp["classes"]))

        r = self.c.post(f"/api/courses/{cid}/classes/2/check", json={"part": "a", "value": 7, "unit": "m/s"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["result"]["verdict"], "wrong")
        self.assertNotIn("12", r.json()["result"]["message"])
        a = self.public_parts(cid)["a"]
        self.assertEqual((a["answer"], a["unit"], a["attempts"], a["solved"]), (12.0, "m/s", 1, False))
        self.assertEqual(a["steps"], [])  # an attempt shows the answer, not the steps

    def test_steps_open_one_at_a_time_in_order(self):
        course, _ = self.sprint_course()
        cid = course["id"]
        url = f"/api/courses/{cid}/classes/2/reveal"
        self.assertEqual(self.c.post(url, json={"part": "a", "step": 2}).status_code, 409)
        self.assertEqual(self.c.post(url, json={"part": "a", "step": 4}).status_code, 422)
        self.assertEqual(self.c.post(url, json={"part": "z", "step": 1}).status_code, 404)
        self.assertEqual(self.c.post(f"/api/courses/{cid}/classes/1/reveal", json={"part": "a", "step": 1}).status_code, 404)
        body = self.c.post(url, json={"part": "a", "step": 1}).json()
        a = next(k for k in body["course"]["classes"] if k["seq"] == 2)["meta"]["sprint"]["parts"][0]
        self.assertEqual((a["steps"], a["revealed"]), (["SECRET-STEP-A1"], 1))
        self.assertNotIn("answer", a)
        self.assertNotIn("SECRET-STEP-A2", json.dumps(body))
        self.c.post(url, json={"part": "a", "step": 1})  # repeating a step changes nothing
        self.c.post(url, json={"part": "a", "step": 2})
        self.assertNotIn("answer", self.public_parts(cid)["a"])
        self.c.post(url, json={"part": "a", "step": 3})
        a = self.public_parts(cid)["a"]
        self.assertEqual((len(a["steps"]), a["answer"], a["solved"]), (3, 12.0, False))  # all steps: answer shown, not solved

    def test_check_verdicts(self):
        course, _ = self.sprint_course()
        url = f"/api/courses/{course['id']}/classes/2/check"
        verdict = lambda v, u="m/s": self.c.post(url, json={"part": "a", "value": v, "unit": u}).json()["result"]["verdict"]  # noqa: E731
        self.assertEqual(verdict(1200), "magnitude")
        self.assertEqual(verdict(-12), "sign")
        self.assertEqual(verdict(12, "km"), "unit")
        self.assertEqual(verdict(12.1, " m / s "), "correct")  # within 2%, spaces ignored
        self.assertTrue(self.public_parts(course["id"])["a"]["solved"])
        r = self.c.post(url, json={"part": "b", "value": 9, "unit": "m"})
        self.assertEqual(r.status_code, 409)  # no automatic check for the part that failed the recheck

    def test_tutor_context_has_only_revealed_steps(self):
        course, _ = self.sprint_course()
        self.c.post(f"/api/courses/{course['id']}/classes/2/reveal", json={"part": "a", "step": 1})
        text = sprint.tutor_context(self.problem(course["id"]))
        self.assertIn("SECRET-STEP-A1", text)
        self.assertNotIn("SECRET-STEP-A2", text)
        self.assertNotIn("12.0", text)
        self.assertEqual(sprint.tutor_context(None), "")


class Finishing(SprintBase):
    def solve(self, cid, seq=2):
        self.c.post(f"/api/courses/{cid}/classes/{seq}/check", json={"part": "a", "value": 12, "unit": "m/s"})
        url = f"/api/courses/{cid}/classes/{seq}/reveal"
        self.c.post(url, json={"part": "b", "step": 1})
        return self.c.post(url, json={"part": "b", "step": 2}).json()  # no auto-check: the last step finishes it

    def test_last_part_clears_the_course(self):
        course, user_id = self.sprint_course(problems=2)
        cid = course["id"]
        tid = self.problem(cid)["topic_id"]
        engage.remember_miss(user_id, tid, "q1", "2020-01-01")
        first = self.solve(cid, 2)
        self.assertEqual(first["finished"], {"complete": False, "cleared": False, "undoUntil": None})
        self.assertEqual(first["course"]["sprint"]["done"], 1)
        body = self.solve(cid, 3)
        self.assertTrue(body["finished"]["cleared"])
        self.assertAlmostEqual(body["finished"]["undoUntil"], time.time() + 7 * 86400, delta=60)
        self.assertEqual(body["course"]["sprint"]["done"], 2)
        self.assertEqual(db.get_course(cid)["status"], "cleared")
        listing = self.c.get(f"/api/users/{user_id}/courses").json()
        self.assertNotIn(cid, [c["id"] for c in listing["courses"]])
        self.assertEqual([c["id"] for c in listing["cleared"]], [cid])
        self.assertEqual(self.c.get(f"/api/topics/{tid}").status_code, 404)
        self.assertNotIn(tid, [t["id"] for t in self.c.get("/api/topics").json()])
        self.assertEqual(self.c.get(f"/api/review/{user_id}/session").json()["questions"], [])
        self.assertEqual(len(engage.due_items(user_id, "2030-01-01")), 1)  # waiting, not dropped: it can be restored
        export = self.c.get(f"/api/users/{user_id}/export").json()
        exported = next(c for c in export["courses"] if c["id"] == cid)
        self.assertEqual(exported["status"], "cleared")
        self.assertNotIn("compute", json.dumps(exported))
        self.assertTrue(all("steps" in p for k in exported["classes"][1:] for p in k["meta"]["sprint"]["parts"]))

    def test_restore_and_keep(self):
        course, user_id = self.sprint_course()
        cid = course["id"]
        self.solve(cid)
        self.assertEqual(self.c.post(f"/api/courses/{cid}/restore").json()["course"]["status"], "ready")
        self.assertEqual(db.get_course(cid)["auto_cleanup"], 0)  # Undo == keep: it is not cleared again
        self.assertEqual(self.c.post(f"/api/courses/{cid}/restore").status_code, 409)
        db.update_course(cid, auto_cleanup=1)
        self.assertIsNotNone(db.clear_course(cid))
        kept = self.c.post(f"/api/courses/{cid}/keep").json()["course"]
        self.assertEqual((kept["status"], kept["auto_cleanup"], kept["cleared_at"]), ("ready", 0, None))
        self.assertIn(cid, [c["id"] for c in self.c.get(f"/api/users/{user_id}/courses").json()["courses"]])

    def test_undo_sticks_after_more_reveals_and_checks(self):
        course, _ = self.sprint_course()
        cid = course["id"]
        self.assertTrue(self.solve(cid)["finished"]["cleared"])
        self.assertEqual(self.c.post(f"/api/courses/{cid}/restore").status_code, 200)
        url = f"/api/courses/{cid}/classes/2"
        again = self.c.post(f"{url}/reveal", json={"part": "a", "step": 1}).json()
        self.assertEqual(again["finished"], {"complete": True, "cleared": False, "undoUntil": None})
        self.c.post(f"{url}/check", json={"part": "a", "value": 12, "unit": "m/s"})
        self.assertEqual(db.get_course(cid)["status"], "ready")

    def test_no_new_solve_does_not_clear(self):
        """Even with auto-clean still on, a request that solves nothing new never clears (finish_if_done is told)."""
        course, _ = self.sprint_course()
        cid = course["id"]
        with mock.patch.object(sprint, "finish_if_done", wraps=sprint.finish_if_done) as spy:
            self.solve(cid)
            self.assertEqual([c.args[1] for c in spy.call_args_list], [True, False, True])
        db.restore_course(cid)
        db.update_course(cid, auto_cleanup=1)
        self.c.post(f"/api/courses/{cid}/classes/2/check", json={"part": "a", "value": 12, "unit": "m/s"})  # already solved
        self.assertEqual(db.get_course(cid)["status"], "ready")

    def test_keep_or_restore_landing_first_wins_the_race(self):
        """finish_if_done read the course (auto-clean on), then /keep ran before its write: the clear is a no-op."""
        for action in ("keep", "restore"):
            course, _ = self.sprint_course(keep=True)
            cid = course["id"]
            self.solve(cid)  # every part done (kept, so not cleared yet)
            db.update_course(cid, auto_cleanup=1)
            if action == "restore":
                db.clear_course(cid)
            stale = {**db.get_course(cid), "auto_cleanup": 1, "status": "ready"}  # what finish_if_done read first
            self.assertEqual(self.c.post(f"/api/courses/{cid}/{action}").status_code, 200)  # lands before its write
            with mock.patch.object(db, "get_course", side_effect=[stale, db.get_course(cid)]):
                out = sprint.finish_if_done(cid, True)
            self.assertEqual((db.get_course(cid)["status"], db.get_course(cid)["auto_cleanup"]), ("ready", 0), action)
            self.assertFalse(out["cleared"], action)
            self.assertIsNone(db.clear_course(cid))  # kept: a later clear does nothing either

    def test_double_restore_runs_once(self):
        course, _ = self.sprint_course()
        cid = course["id"]
        db.clear_course(cid)
        self.assertTrue(db.restore_course(cid, only_cleared=True))
        self.assertFalse(db.restore_course(cid, only_cleared=True))

    def test_topic_listing_reads_no_full_course_rows(self):
        course, _ = self.sprint_course()
        tid = self.problem(course["id"])["topic_id"]
        # the visibility filter of /api/topics (with_workspace may still read a course for older files without a workspace)
        listed = lambda: [t["id"] for t in server.read_topics_cached() if server.topic_visible(t, {})]  # noqa: E731
        with mock.patch.object(db, "get_course", side_effect=AssertionError("SELECT * per topic")):
            self.assertIn(tid, listed())
            self.assertEqual(self.c.get(f"/api/topics/{tid}").status_code, 200)
            db.clear_course(course["id"])  # invalidates the cleared-ids cache at once
            self.assertNotIn(tid, listed())
            self.assertEqual(self.c.get(f"/api/topics/{tid}").status_code, 404)
            server.AUTH_REQUIRED = True  # the owner check uses the owner column only
            self.assertFalse(server.topic_visible({"source": {"courseId": "x"}}))

    def test_clear_keep_and_restore_tell_the_library(self):
        course, _ = self.sprint_course()
        cid = course["id"]
        version = self.c.get("/api/topics/version").json()["version"]

        def topic_events(fn):
            cursor = self.c.get("/api/agy/events").json()["cursor"]
            fn()
            events = self.c.get(f"/api/agy/events?since={cursor}").json()["events"]
            return [e for e in events if e["type"] == "TOPIC_UPDATED"]
        self.assertTrue(topic_events(lambda: self.solve(cid)))
        cleared_version = self.c.get("/api/topics/version").json()["version"]
        self.assertNotEqual(cleared_version, version)  # pollers refetch even though no file changed
        self.assertTrue(topic_events(lambda: self.c.post(f"/api/courses/{cid}/restore")))
        self.assertEqual(self.c.get("/api/topics/version").json()["version"], version)
        db.update_course(cid, auto_cleanup=1)
        db.clear_course(cid)
        self.assertTrue(topic_events(lambda: self.c.post(f"/api/courses/{cid}/keep")))

    def test_cleared_course_cannot_be_rewritten(self):
        course, _ = self.sprint_course()
        cid = course["id"]
        self.solve(cid)
        for path in (f"/api/courses/{cid}/resume", f"/api/courses/{cid}/classes/2/regenerate"):
            r = self.c.post(path, json={})
            self.assertEqual(r.status_code, 409, path)
            self.assertIn("Restore the course first", r.json()["detail"])
        self.assertEqual(self.queued, [])
        self.c.post(f"/api/courses/{cid}/restore")
        self.assertEqual(self.c.post(f"/api/courses/{cid}/classes/2/regenerate", json={}).status_code, 200)

    def test_rewrite_with_same_parts_keeps_progress(self):
        course, _ = self.sprint_course(problems=2)
        cid = course["id"]
        self.c.post(f"/api/courses/{cid}/classes/2/reveal", json={"part": "b", "step": 1})
        self.c.post(f"/api/courses/{cid}/classes/2/check", json={"part": "a", "value": 12, "unit": "m/s"})
        stale = self.problem(cid)
        stale = {**stale, "meta": {**stale["meta"], "sprint": {**stale["meta"]["sprint"], "revealed": {}, "attempts": {}}, "solved": {}}}
        self.build(stale, db.get_course(cid), lesson_reply())  # meta read before a slow generation
        state = self.problem(cid)["meta"]
        self.assertEqual((state["sprint"]["revealed"], state["sprint"]["attempts"], state["solved"]),
                         ({"b": 1}, {"a": 1}, {"a": True}))
        changed = {**PROBLEM, "parts": [{**PROBLEM["parts"][0], "steps": ["NEW-1", "NEW-2"]}]}
        self.build(self.problem(cid), db.get_course(cid), lesson_reply(problem=changed))
        state = self.problem(cid)["meta"]
        self.assertEqual((state["sprint"]["revealed"], state["solved"]), ({}, {}))

    def test_kept_sprint_is_not_cleared(self):
        course, _ = self.sprint_course(keep=True)
        body = self.solve(course["id"])
        self.assertEqual(body["finished"], {"complete": True, "cleared": False, "undoUntil": None})
        self.assertEqual(db.get_course(course["id"])["status"], "ready")

    def test_purge_only_old_cleared_auto_clean_sprints(self):
        old = time.time() - 8 * 86400
        due, _ = self.sprint_course()
        recent, _ = self.sprint_course()
        kept, _ = self.sprint_course(keep=True)
        tid = self.problem(due["id"])["topic_id"]
        user = db.get_or_create_user(f"Learner {uuid.uuid4().hex[:6]}")
        learn = db.create_course(user["id"], "A learn course", "g", "", [], "learn")
        for cid in (due["id"], kept["id"], learn["id"]):
            db.update_course(cid, status="cleared", cleared_at=old, auto_cleanup=db.get_course(cid)["auto_cleanup"] or 0)
        db.update_course(learn["id"], auto_cleanup=1)  # a cleared non-sprint course must survive even flagged
        db.clear_course(recent["id"])
        gone = server.purge_cleared()
        self.assertEqual(gone, [due["id"]])
        self.assertIsNone(db.get_course(due["id"]))
        self.assertFalse(server.topic_path(tid).exists())
        self.assertIsNone(db.get_lesson(tid))
        for cid in (recent["id"], kept["id"], learn["id"]):
            self.assertIsNotNone(db.get_course(cid))


class Reference(SprintBase):
    MATERIALS = ("Problem 3. A block of mass 2 kg slides down a frictionless incline of angle 30 degrees. "
                 "Find its acceleration and the time to slide 4 m from rest.")

    def test_overlap_rule(self):
        grams = sprint.ngrams(self.MATERIALS)
        copied = {"type": "numeric", "prompt": "A block of mass 2 kg slides down a frictionless incline of angle 30 degrees. Find a."}
        fresh = {"type": "numeric", "prompt": "A sled of 5 kg is pulled up a rough ramp at 20 degrees by a rope; find the tension."}
        self.assertGreaterEqual(sprint.copied_share(copied, grams), 0.3)
        self.assertLess(sprint.copied_share(fresh, grams), 0.3)
        self.assertEqual(sprint.copied_share({"type": "true_false", "prompt": "Short one"}, grams), 0.0)
        kept, dropped = sprint.drop_copied([copied, fresh], self.MATERIALS)
        self.assertEqual((kept, dropped), ([fresh], 1))

    def test_reference_class_drops_copied_practice_and_says_original(self):
        user = db.get_or_create_user(f"Ref {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Inclines", "like my homework", self.MATERIALS, [], "thematic_reference")
        db.replace_classes(course["id"], [{"title": "Inclines"}])
        course = db.get_course(course["id"])
        practice = [{"type": "true_false", "prompt": "A block of mass 2 kg slides down a frictionless incline of angle 30 degrees.", "answer": True},
                    {"type": "true_false", "prompt": "On a steeper ramp a block speeds up faster.", "answer": True}]
        saved = self.build(db.list_classes(course["id"])[0], course, lesson_reply(problem=None, practice=practice))
        self.assertEqual([p["prompt"] for p in saved["practice"]], ["On a steeper ramp a block speeds up faster."])
        self.assertIn("ORIGINAL problems", self.prompts[0])
        self.assertIn("REFERENCE-ONLY", server.mode_rules(course))


class Rechecks(unittest.TestCase):
    def test_recheck_numeric(self):
        items = [{"answer": 4.0, "compute": "2**2"}, {"answer": 5, "compute": "2**2"}, {"answer": None, "compute": ""},
                 {"answer": 1.6e-19, "compute": "1.602e-19"}]
        self.assertEqual(server.recheck_numeric(items), [True, False, False, True])
        self.assertEqual(items[3]["answer"], 1.602e-19)  # tiny values are not rounded to zero


class AccountsMode(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = True
        server._rate_hits.pop(("auth", "testclient"), None)
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

        def acct(name):
            r = self.c.post("/api/auth/register", json={"name": name, "password": "correct horse battery", "adult": True, "privacy": True}).json()
            return {"Authorization": f"Bearer {r['token']}"}, r["user"]["id"]
        tag = uuid.uuid4().hex[:6]
        self.a, self.a_id = acct(f"Sprint Alice {tag}")
        self.b, self.b_id = acct(f"Sprint Bob {tag}")
        course = db.create_course(self.a_id, "Alice sprint", "g", "", [], "problem_sprint")
        db.update_course(course["id"], status="ready", auto_cleanup=1)
        db.replace_classes(course["id"], [{"title": "Problem 1", "status": "ready", "meta": {
            **sprint.sprint_meta("problem", 1, "x"),
            "sprint": {"parts": [{"id": "a", "prompt": "p", "steps": ["s1"], "answer": 1.0, "unit": "", "tolerance": 0.02,
                                  "checked": True}], "revealed": {}, "attempts": {}}, "solved": {}}}])
        self.cid = course["id"]

    def tearDown(self):
        server.AUTH_REQUIRED = False
        self.ctx.__exit__(None, None, None)
        db.close_all()

    def test_someone_elses_sprint_is_not_found(self):
        base = f"/api/courses/{self.cid}"
        for path, body in ((f"{base}/classes/1/reveal", {"part": "a", "step": 1}),
                           (f"{base}/classes/1/check", {"part": "a", "value": 1}), (f"{base}/keep", None), (f"{base}/restore", None)):
            self.assertEqual(self.c.post(path, json=body, headers=self.b).status_code, 404, path)
        self.assertEqual(self.c.get(base, headers=self.b).status_code, 404)
        self.assertEqual(self.c.post(f"{base}/classes/1/reveal", json={"part": "a", "step": 1}, headers=self.a).status_code, 200)
        db.clear_course(self.cid)
        self.assertEqual(self.c.post(f"{base}/restore", headers=self.b).status_code, 404)
        self.assertEqual(self.c.post(f"{base}/restore", headers=self.a).status_code, 200)  # cleared courses stay reachable


if __name__ == "__main__":
    unittest.main()
