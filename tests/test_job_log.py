"""The live job log the loading screens show: the last JOB_LOG_MAX steps per job, in JOB_UPDATE, GET /api/jobs/{id}
and course.job. Entries are fixed labels and counts, never materials or answers."""
from test_lab import LOCAL, TestClient, server, db, engage  # noqa: F401  (sets up the temp content dir first)

import json
import time
import unittest
import uuid
from unittest import mock

import advisor
from test_sprint import PROBLEM, SprintBase, lesson_reply


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    server.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()
    advisor.init()


class JobLog(unittest.TestCase):
    def setUp(self):
        self.events = []
        p = mock.patch.object(server, "emit_event", lambda kind, payload, **kw: self.events.append((kind, payload)))
        p.start()
        self.addCleanup(p.stop)

    def job(self, **extra):
        return {"id": f"job-log-{uuid.uuid4().hex[:6]}", "kind": "course", "status": "running", "step": "Starting",
                "created": time.time(), **extra}

    def test_appends_only_when_the_step_changes_and_caps(self):
        job = self.job()  # no "log" key, like jobs made before this change
        server._job_update(job, step="Starting")
        self.assertEqual(job.get("log", []), [])
        server._job_update(job, progress=0.5)
        self.assertEqual(job.get("log", []), [])
        for n in range(server.JOB_LOG_MAX + 5):
            server._job_update(job, step=f"Step {n}")
        self.assertEqual(len(job["log"]), server.JOB_LOG_MAX)
        self.assertEqual(job["log"][-1]["step"], f"Step {server.JOB_LOG_MAX + 4}")
        self.assertEqual(job["log"][0]["step"], "Step 5")

    def test_event_payload_is_a_snapshot(self):
        job = self.job()
        server._job_update(job, step="One")
        sent = self.events[-1][1]
        server._job_update(job, step="Two")
        self.assertEqual([e["step"] for e in sent["log"]], ["One"])
        self.assertEqual([e["step"] for e in self.events[-1][1]["log"]], ["One", "Two"])

    def test_note_keeps_the_headline(self):
        job = self.job(step="Writing class 1 of 3: Forces")
        server._job_note(job, "Lesson written")
        self.assertEqual(job["step"], "Writing class 1 of 3: Forces")
        self.assertEqual(self.events[-1][0], "JOB_UPDATE")
        self.assertEqual([e["step"] for e in self.events[-1][1]["log"]], ["Lesson written"])

    def test_new_jobs_start_with_queued(self):
        async def work(job):
            return None

        def schedule(coro, loop):
            coro.close()  # never run: only the job record matters here
            return mock.Mock()
        with mock.patch.object(server.asyncio, "get_running_loop", side_effect=RuntimeError), \
             mock.patch.object(server, "MAIN_LOOP", object()), \
             mock.patch.object(server.asyncio, "run_coroutine_threadsafe", schedule):
            job = server.start_job("test", "Test", work)
        self.addCleanup(server.JOBS.pop, job["id"], None)
        self.assertEqual([e["step"] for e in job["log"]], ["Queued"])


class BuildClassSteps(SprintBase):
    def test_build_reports_fixed_labels_only(self):
        user_id = db.get_or_create_user(f"Logger {uuid.uuid4().hex[:6]}")["id"]
        course = db.create_course(user_id, "Kinematics sprint", "explain my homework", "Problem 1. A cart...", [], "problem_sprint")
        db.update_course(course["id"], status="ready", concepts=[{"id": "kin", "name": "Kinematics", "summary": ""}])
        db.replace_classes(course["id"], [{"title": "Problem 1", "meta": server.sprint.sprint_meta("problem", 1, "A cart")}])
        course = db.get_course(course["id"])
        klass = db.list_classes(course["id"])[0]
        steps = []

        async def fake_json(prompt, temperature=0.4, role=None):
            return lesson_reply()
        with mock.patch.object(server, "gemini_json", fake_json):
            server.asyncio.run(server.build_class(course, klass, [klass], on_step=steps.append))
        self.assertEqual(steps, ["Lesson written", "Quiz answers checked"])
        secrets = [s for p in PROBLEM["parts"] for s in p["steps"]] + [str(p["answer"]) for p in PROBLEM["parts"]]
        self.assertFalse([s for s in secrets if s in json.dumps(steps)])

    def test_course_job_and_jobs_endpoint_carry_the_log(self):
        user = self.c.post("/api/users", json={"name": f"Log {uuid.uuid4().hex[:6]}"}).json()["user"]
        course = db.create_course(user["id"], "Logged", "learn", "notes", [], "learn")
        job = {"id": f"job-log-{uuid.uuid4().hex[:6]}", "kind": "course", "status": "running", "step": "Writing",
               "progress": 0.3, "created": time.time(), "log": [{"at": 1.0, "step": "Lesson written"}]}
        server.JOBS[job["id"]] = job
        self.addCleanup(server.JOBS.pop, job["id"], None)
        db.update_course(course["id"], job_id=job["id"])
        out = server.public_course(db.get_course(course["id"]))
        self.assertEqual(out["job"]["log"], [{"at": 1.0, "step": "Lesson written"}])
        self.assertIsNot(out["job"]["log"], job["log"])
        r = self.c.get(f"/api/jobs/{job['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["log"], job["log"])


if __name__ == "__main__":
    unittest.main()
