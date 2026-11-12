"""Accounts on this computer, phase 1 (docs/plans/ACCOUNTS.md): SCIEDU_LOCAL_ACCOUNTS scopes every request to its
signed-in user like SCIEDU_AUTH, keeps the server-only rules off, never hands out password hashes, and loses to
SCIEDU_AUTH when both are set."""
from test_lab import LOCAL, TestClient, server, db, engage  # noqa: F401  (sets up the temp content dir first)

import ast
import json
import os
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import language_tts
from local_accounts import LocalAccountsCase, local_account

QUIZ = [{"id": "q1", "question": "2+2?", "options": ["4", "5"], "correctAnswer": 0}]
PASSWORD = "correct horse battery"


def setUpModule():
    # test_lab's tearDownModule removes the shared temp dir; recreate what these tests need
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()


def topic(tid, **extra):
    return {"id": tid, "title": "Local", "category": "Physics", "markdownContent": "# Local", **extra}


class Flags(unittest.TestCase):
    def setUp(self):
        self.old = (server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS)

    def tearDown(self):
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = self.old

    def test_scoped_and_local_mode_follow_both_flags_at_call_time(self):
        for auth, local, scoped, local_mode in ((False, False, False, False), (True, False, True, False),
                                                (False, True, True, True), (True, True, True, False)):
            with self.subTest(auth=auth, local=local):
                server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = auth, local
                self.assertIs(server.scoped(), scoped)
                self.assertIs(server.local_mode(), local_mode)

    def test_off_by_default(self):
        self.assertNotEqual(os.environ.get("SCIEDU_LOCAL_ACCOUNTS"), "1")
        self.assertIs(self.old[1], False)

    def test_public_paths(self):
        self.assertEqual(server.public_paths(), {"/api/status", "/api/auth/login", "/api/auth/register"})


class LocalScoping(LocalAccountsCase):
    """Every B row of the ACCOUNTS.md site table, with accounts on this computer."""
    def setUp(self):
        super().setUp()
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        tag = uuid.uuid4().hex[:6]
        self.a, self.a_id = local_account(f"Local Alice {tag}")
        self.b, self.b_id = local_account(f"Local Bob {tag}")
        self.tag = tag

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        db.close_all()
        super().tearDown()

    def alice_lesson(self, tid):
        course = db.create_course(self.a_id, "Alice course", "g", "", [])
        db.replace_classes(course["id"], [{"title": "C1", "objective": "o"}])
        server.save_topic(topic(tid, quiz=QUIZ, source={"courseId": course["id"]}))
        db.update_class(db.list_classes(course["id"])[0]["id"], topic_id=tid)
        return course

    def test_every_api_call_needs_a_session_except_public_paths(self):
        self.assertEqual(self.c.get("/api/topics").status_code, 401)
        self.assertEqual(self.c.get("/api/topics", headers={"Authorization": "Bearer nope"}).status_code, 401)
        self.assertEqual(self.c.get("/api/topics", headers=self.a).status_code, 200)
        self.assertEqual(self.c.get("/api/status").status_code, 200)

    def test_courses_and_profiles_are_private(self):
        course = db.create_course(self.a_id, "Alice private", "g", "", [])
        self.assertEqual(self.c.get(f"/api/users/{self.a_id}/courses", headers=self.b).status_code, 403)
        self.assertEqual(self.c.get(f"/api/users/{self.a_id}/courses", headers=self.a).status_code, 200)
        self.assertEqual(self.c.get(f"/api/courses/{course['id']}", headers=self.b).status_code, 404)
        self.assertEqual(self.c.get(f"/api/courses/{course['id']}", headers=self.a).status_code, 200)
        self.assertEqual(self.c.post(f"/api/users/{self.a_id}/consent", json={"kind": "privacy"}, headers=self.b).status_code, 403)

    def test_new_course_belongs_to_the_signed_in_user(self):
        with mock.patch.object(server, "start_plan_job", return_value={"id": "job-none"}):
            r = self.c.post("/api/courses", json={"userId": self.a_id, "goal": "Learn the basics of optics, please."}, headers=self.b)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(db.get_course(r.json()["course"]["id"])["user_id"], self.b_id)

    def test_lessons_are_visible_and_writable_only_by_their_owner(self):
        self.alice_lesson(f"local-{self.tag}-lesson")
        tid = f"local-{self.tag}-lesson"
        self.assertEqual(self.c.get(f"/api/topics/{tid}", headers=self.b).status_code, 404)
        self.assertEqual(self.c.get(f"/api/topics/{tid}", headers=self.a).status_code, 200)
        self.assertNotIn(tid, [t["id"] for t in self.c.get("/api/topics", headers=self.b).json()])
        evil = topic(tid, source={"courseId": "x"})
        self.assertEqual(self.c.post("/api/topics", json=evil, headers=self.b).status_code, 404)
        self.assertEqual(self.c.post(f"/api/topics/{tid}/flashcards", json={"items": []}, headers=self.a).status_code, 200)
        # the shared library: any signed-in local user may write it (is_admin stays server-only)
        self.assertEqual(self.c.post("/api/topics", json=topic(f"local-{self.tag}-lib"), headers=self.b).status_code, 200)

    def test_opening_someone_elses_lesson_does_not_write_their_next_class(self):
        tid = f"local-{self.tag}-open"
        self.alice_lesson(tid)
        with mock.patch.object(server, "release_next_class") as release, \
                mock.patch.object(server, "topic_visible", return_value=True):
            self.c.post(f"/api/topics/{tid}/opened", headers=self.b)
            release.assert_not_called()
            self.c.post(f"/api/topics/{tid}/opened", headers=self.a)
            release.assert_called_once()

    def test_quiz_answers_are_recorded_for_the_signed_in_user(self):
        lib = f"local-{self.tag}-quiz"
        server.save_topic(topic(lib, quiz=QUIZ))
        answer = {"topicId": lib, "questionId": "q1", "selected": 0, "isCorrect": False, "userId": self.a_id}
        self.assertEqual(self.c.post("/api/quiz/submit", json=answer, headers=self.b).status_code, 200)
        last = json.loads(server.RESULTS_FILE.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((last["userId"], last["isCorrect"]), (self.b_id, True))
        tid = f"local-{self.tag}-class"
        self.alice_lesson(tid)
        self.assertEqual(self.c.post("/api/quiz/submit", json={**answer, "topicId": tid}, headers=self.b).status_code, 404)

    def test_events_and_jobs_go_to_their_owner_only(self):
        cur = self.c.get("/api/agy/events", headers=self.b).json()["cursor"]
        self.c.post("/api/ui/graph", json={"functions": ["x^2"]}, headers=self.a)
        self.assertEqual(self.c.get(f"/api/agy/events?since={cur}", headers=self.b).json()["events"], [])
        self.assertEqual(len(self.c.get(f"/api/agy/events?since={cur}", headers=self.a).json()["events"]), 1)
        job = f"job-local-{self.tag}"
        server.JOBS[job] = {"id": job, "kind": "course", "created": time.time(), "owner": self.a_id, "status": "done"}
        try:
            self.assertEqual(self.c.get(f"/api/jobs/{job}", headers=self.b).status_code, 404)
            self.assertNotIn(job, [j["id"] for j in self.c.get("/api/jobs", headers=self.b).json()["jobs"]])
            self.assertEqual(self.c.get(f"/api/jobs/{job}", headers=self.a).status_code, 200)
        finally:
            server.JOBS.pop(job, None)

    def test_shared_assistant_history_is_off(self):
        server.MESSAGES_FILE.write_text(json.dumps([{"id": "m1", "content": "someone's chat"}]), encoding="utf-8")
        try:
            self.assertEqual(self.c.get("/api/agy/messages", headers=self.a).json(), [])
            server.append_messages({"id": "m2", "content": "new"})
            self.assertNotIn("new", server.MESSAGES_FILE.read_text(encoding="utf-8"))
        finally:
            server.MESSAGES_FILE.unlink()

    def test_tutor_and_companion_never_read_someone_elses_notes(self):
        db.save_student_notes(self.a_id, "Alice secret note")
        lib = f"local-{self.tag}-tutor"
        server.save_topic(topic(lib))
        seen = []

        async def fake(contents, role=None, **kw):
            seen.append(str(contents) + str(getattr(kw.get("config"), "system_instruction", "")))
            return SimpleNamespace(text="ok", function_calls=[])
        with mock.patch.object(server, "acall_gemini", side_effect=fake):
            r = self.c.post("/api/tutor/lesson", json={"topicId": lib, "message": "hi", "userId": self.a_id}, headers=self.b)
            self.assertEqual(r.status_code, 403)
            self.c.post("/api/agy/prompt", json={"prompt": "what do my notes say?", "userId": self.a_id}, headers=self.b)
        self.assertFalse([s for s in seen if "Alice secret note" in s])

    def test_agy_cli_is_off(self):
        with mock.patch.dict("os.environ", {"AGY_CLI": "1"}), mock.patch.object(server, "Path") as path:
            path.return_value.exists.return_value = True
            self.assertFalse(server.agy_cli_allowed())

    def test_routers_follow_scoping(self):
        digest = uuid.uuid4().hex * 2
        d = language_tts.cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        clip = d / f"{digest}.mp3"
        clip.write_bytes(b"ID3")
        try:
            self.assertEqual(self.c.get(f"/api/language/tts/{digest}.mp3").status_code, 401)
            got = self.c.get(f"/api/language/tts/{digest}.mp3", headers=self.a)
            self.assertEqual(got.status_code, 200)
            self.assertTrue(got.headers["cache-control"].startswith("private"))
        finally:
            clip.unlink()


class Profiles(unittest.TestCase):
    """GET/POST /api/users: off with either accounts mode; password hashes never leave the server in any mode."""
    def setUp(self):
        self.old = (server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS)
        server._rate_hits.pop(("auth", "testclient"), None)
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        self.name = f"Hashed {uuid.uuid4().hex[:6]}"
        self.user = db.create_account(self.name, PASSWORD)

    def tearDown(self):
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = self.old
        server._rate_hits.pop(("auth", "testclient"), None)
        self.ctx.__exit__(None, None, None)
        db.close_all()

    def test_db_helpers_project_explicit_columns(self):
        self.assertTrue(db.get_user_auth(self.user["id"])["password_hash"])
        for row in (db.get_user(self.user["id"]), db.get_or_create_user(self.name),
                    next(u for u in db.list_users() if u["id"] == self.user["id"])):
            self.assertNotIn("password_hash", row)
            self.assertTrue({"id", "name", "created_at", "last_seen"} <= set(row))
        self.assertIn("course_count", db.list_users()[0])

    def test_personal_mode_lists_profiles_without_hashes(self):
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, False
        r = self.c.get("/api/users")
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.user["id"], r.text)
        r2 = self.c.post("/api/users", json={"name": self.name})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["user"]["id"], self.user["id"])
        me = self.c.get("/api/auth/me")
        for resp in (r, r2, me):
            self.assertNotIn("password_hash", resp.text)
            self.assertNotIn("scrypt$", resp.text)

    def test_local_mode_refuses_the_profile_list(self):
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, True
        headers, _ = local_account(f"Local Lister {uuid.uuid4().hex[:6]}")
        for h in ({}, headers):
            self.assertIn(self.c.get("/api/users", headers=h).status_code, (401, 403))
            self.assertIn(self.c.post("/api/users", json={"name": self.name}, headers=h).status_code, (401, 403))
        self.assertEqual(self.c.get("/api/users", headers=headers).json()["detail"], "Sign in to your account on this computer.")
        me = self.c.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertNotIn("password_hash", me.text)

    def test_server_mode_wins_when_both_flags_are_set(self):
        for local in (False, True):
            with self.subTest(local=local):
                server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = True, local
                server._rate_hits.pop(("auth", "testclient"), None)
                login = self.c.post("/api/auth/login", json={"name": self.name, "password": PASSWORD})
                self.assertEqual(login.status_code, 200)
                headers = {"Authorization": f"Bearer {login.json()['token']}"}
                r = self.c.get("/api/users", headers=headers)
                self.assertEqual((r.status_code, r.json()["detail"]), (403, "Profiles are private on this server."))
                r = self.c.post("/api/users", json={"name": self.name}, headers=headers)
                self.assertEqual((r.status_code, r.json()["detail"]), (403, "Sign in with a password on this server."))
                for resp in (login, self.c.get("/api/auth/me", headers=headers)):
                    self.assertNotIn("password_hash", resp.text)
                    self.assertNotIn("scrypt$", resp.text)
                # server-only rules still apply
                self.assertEqual(self.c.post("/api/execute-code", json={"code": "print(1)"}, headers=headers).status_code, 403)


class FlagGuard(unittest.TestCase):
    """Every AUTH_REQUIRED / LOCAL_ACCOUNTS read in server.py sits in a function that is meant to tell the modes apart.
    Anything else should call scoped() (both accounts modes) or local_mode() (this computer only)."""
    ALLOWED = {
        "scoped", "local_mode",
        # S rows: server accounts only
        "execute_code", "is_admin", "submit_quiz_answer", "activity_result", "advisor_classify_catalog",
        "require_upload_consent", "resume_course_generation",
        # C rows, changed in later phases (sign-in, per-key budget and key state, status)
        "spend_model_call", "_key_rejected", "register", "login", "me", "delete_account", "get_status",
        "list_profiles", "sign_in",
    }

    def flag_reads(self):
        tree = ast.parse((Path(server.__file__)).read_text(encoding="utf-8"))
        found = []

        def walk(node, where):
            for child in ast.iter_child_nodes(node):
                inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else where
                if isinstance(child, ast.Name) and child.id in ("AUTH_REQUIRED", "LOCAL_ACCOUNTS"):
                    found.append((where, child.lineno, child.id))
                walk(child, inner)

        for stmt in tree.body:
            if (isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Compare)
                    and isinstance(stmt.test.left, ast.Name) and stmt.test.left.id == "__name__"):
                walk(stmt, "__main__")
            elif isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("AUTH_REQUIRED", "LOCAL_ACCOUNTS")
                                                      for t in stmt.targets):
                walk(stmt, "<flag>")
            elif isinstance(stmt, ast.If) and {n.id for n in ast.walk(stmt.test) if isinstance(n, ast.Name)} == {"AUTH_REQUIRED", "LOCAL_ACCOUNTS"}:
                walk(stmt, "<flag>")  # the both-flags startup warning
            else:
                walk(ast.Module(body=[stmt], type_ignores=[]), "<module>")
        return found

    def test_flags_are_read_only_in_allowlisted_places(self):
        found = self.flag_reads()
        stray = [(where, line, name) for where, line, name in found
                 if where not in self.ALLOWED | {"<flag>", "__main__"}]
        self.assertEqual(stray, [], "use scoped() or local_mode() here, or add the function to the S/C allowlist")
        self.assertEqual(self.ALLOWED - {where for where, _, _ in found}, set(), "stale allowlist entries")
        self.assertIn("__main__", {where for where, _, _ in found})  # the bind-host refusal stays on AUTH_REQUIRED


if __name__ == "__main__":
    unittest.main()
