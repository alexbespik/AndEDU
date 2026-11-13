"""Accounts on this computer (docs/plans/ACCOUNTS.md). Phase 1: SCIEDU_LOCAL_ACCOUNTS scopes every request to its
signed-in user like SCIEDU_AUTH, keeps the server-only rules off, never hands out password hashes, and loses to
SCIEDU_AUTH when both are set. Phase 2: sign-in with optional passwords, the admin account, each account's sealed
Gemini key, lock, auto-lock, forgot-password delete and the pre-migration backup."""
from test_lab import LOCAL, TestClient, server, db, engage  # noqa: F401  (sets up the temp content dir first)

import ast
import contextlib
import json
import os
import sqlite3
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import language_tts
import userkeys
from local_accounts import TEST_SCRYPT_N, LocalAccountsCase, local_account

QUIZ = [{"id": "q1", "question": "2+2?", "options": ["4", "5"], "correctAnswer": 0}]
PASSWORD = "correct horse battery"


def setUpModule():
    # test_lab's tearDownModule removes the shared temp dir; recreate what these tests need
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()


def topic(tid, **extra):
    return {"id": tid, "title": "Local", "category": "Physics", "markdownContent": "# Local", **extra}


def set_admin(user_id, on):
    db.conn().execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if on else 0, user_id))
    db.conn().commit()


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
        # the shared library: only the admin account on this computer may write it (phase 2, Admin decision)
        self.assertEqual(self.c.post("/api/topics", json=topic(f"local-{self.tag}-lib"), headers=self.b).status_code, 403)
        set_admin(self.b_id, True)
        try:
            self.assertEqual(self.c.post("/api/topics", json=topic(f"local-{self.tag}-lib"), headers=self.b).status_code, 200)
        finally:
            set_admin(self.b_id, False)

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


@contextlib.contextmanager
def fresh_db():
    """An empty database for this block (first-account and migration checks); the shared one comes back afterwards."""
    old = db.DB_PATH
    with tempfile.TemporaryDirectory(prefix="andedu-accounts-") as d:
        with server._purge_running:  # the running app's purge thread must not be mid-query when connections close
            db.close_all()
            db.DB_PATH = Path(d) / "edu_studio.db"
        try:
            db.init_db()
            yield Path(d)
        finally:
            with server._purge_running:
                db.close_all()
                db.DB_PATH = old


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


class LocalSignIn(LocalAccountsCase):
    """Phase 2: sign-in, passwords, the account's own Gemini key, lock and auto-lock (ACCOUNTS.md)."""
    def setUp(self):
        super().setUp()
        self.limits = mock.patch.object(server, "AUTH_ATTEMPTS_PER_MINUTE", 10_000)
        self.limits.start()
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        self.tag = uuid.uuid4().hex[:6]

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self.limits.stop()
        server._rate_hits.pop(("key_check", "testclient"), None)
        db.close_all()
        super().tearDown()

    def register(self, who, password=None):
        body = {"name": f"{who} {self.tag}", **({"password": password} if password else {})}
        r = self.c.post("/api/auth/register", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return bearer(r.json()["token"]), r.json()["user"]["id"]

    def login(self, who, password=None):
        return self.c.post("/api/auth/login", json={"name": f"{who} {self.tag}", **({"password": password} if password else {})})

    def put_key(self, headers, key="AIza-test-key-1234", verdict="ok"):
        with mock.patch.object(userkeys, "check_key", return_value=verdict) as check:
            r = self.c.put("/api/me/gemini-key", json={"key": key}, headers=headers)
        check.assert_called_once_with(key)
        return r

    def test_public_paths_add_the_sign_in_screen_only_locally(self):
        self.assertEqual(server.public_paths(), {"/api/status", "/api/auth/login", "/api/auth/register",
                                                 "/api/auth/profiles", "/api/auth/forgot-delete"})
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = True, True
        self.assertNotIn("/api/auth/profiles", server.public_paths())
        self.assertEqual(self.c.get("/api/auth/profiles").status_code, 401)

    def test_profiles_never_leak_hashes(self):
        _, open_id = self.register("Open Olga")
        _, locked_id = self.register("Locked Lena", PASSWORD)
        r = self.c.get("/api/auth/profiles")  # no session: the sign-in screen
        self.assertEqual(r.status_code, 200)
        tiles = {p["id"]: p for p in r.json()}
        self.assertEqual(tiles[open_id], {"id": open_id, "name": f"Open Olga {self.tag}", "locked": False})
        self.assertEqual(tiles[locked_id], {"id": locked_id, "name": f"Locked Lena {self.tag}", "locked": True})
        self.assertTrue(all(set(p) == {"id", "name", "locked"} for p in r.json()))
        self.assertNotIn("scrypt", r.text)

    def test_register_takes_an_optional_password_of_8_or_more(self):
        r = self.c.post("/api/auth/register", json={"name": f"Short {self.tag}", "password": "1234567"})
        self.assertEqual(r.status_code, 422)
        headers, uid = self.register("Nopass Nina")  # no adult or privacy field needed on this computer
        me = self.c.get("/api/auth/me", headers=headers).json()
        self.assertEqual((me["localAccounts"], me["hasPassword"], me["keyState"], me["autoLockMin"]), (True, False, "none", 30))
        self.assertIsNone(db.get_user_auth(uid)["password_hash"])
        headers, uid = self.register("Pass Paul", PASSWORD)
        self.assertTrue(db.get_user_auth(uid)["password_hash"].startswith(f"scrypt2${TEST_SCRYPT_N}$8$1$"))
        self.assertTrue(self.c.get("/api/auth/me", headers=headers).json()["hasPassword"])
        self.assertEqual(self.c.post("/api/auth/register", json={"name": f"pass paul {self.tag}"}).status_code, 409)

    def test_login_is_passwordless_only_without_a_password(self):
        self.register("Open Otto")
        self.register("Locked Lars", PASSWORD)
        r = self.login("Open Otto")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.c.get("/api/auth/me", headers=bearer(r.json()["token"])).json()["user"]["name"], f"Open Otto {self.tag}")
        self.assertEqual(self.login("Locked Lars").status_code, 401)
        self.assertEqual(self.login("Locked Lars", "wrong password").status_code, 401)
        self.assertEqual(self.login("Nobody").status_code, 401)
        r = self.login("Locked Lars", PASSWORD)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("scrypt", r.text)

    def test_wrong_passwords_back_off_per_name(self):
        self.register("Backoff Bea", PASSWORD)
        self.register("Other Olli", PASSWORD)
        name = f"backoff bea {self.tag}"
        for _ in range(5):  # five free failures
            self.assertEqual(self.login("Backoff Bea", "wrong password").status_code, 401)
        self.assertLessEqual(server._login_failures[name]["until"], time.time())
        self.assertEqual(self.login("Backoff Bea", "wrong password").status_code, 401)
        self.assertAlmostEqual(server._login_failures[name]["until"] - time.time(), 2, delta=1)
        r = self.login("Backoff Bea", PASSWORD)  # even the right password waits
        self.assertEqual(r.status_code, 429)
        self.assertIn("Try again in", r.json()["detail"])
        self.assertEqual(self.login("Other Olli", PASSWORD).status_code, 200)  # per name, not per computer
        server._login_failures[name]["until"] = 0
        self.assertEqual(self.login("Backoff Bea", "wrong password").status_code, 401)
        self.assertAlmostEqual(server._login_failures[name]["until"] - time.time(), 4, delta=1)
        server._login_failures[name].update(count=100, until=0)
        self.login("Backoff Bea", "wrong password")
        self.assertLessEqual(server._login_failures[name]["until"] - time.time(), 900)
        server._login_failures[name]["until"] = 0
        self.assertEqual(self.login("Backoff Bea", PASSWORD).status_code, 200)
        self.assertNotIn(name, server._login_failures)  # a success starts over

    def test_old_scrypt_hash_is_upgraded_on_local_login(self):
        name = f"Legacy Lou {self.tag}"
        user = db.create_account(name, PASSWORD)  # server-mode hash: scrypt$, n=2^14
        self.assertTrue(db.get_user_auth(user["id"])["password_hash"].startswith("scrypt$"))
        self.assertEqual(self.login("Legacy Lou", PASSWORD).status_code, 200)
        stored = db.get_user_auth(user["id"])["password_hash"]
        self.assertTrue(stored.startswith("scrypt2$"))
        self.assertTrue(db.check_password(PASSWORD, stored))
        self.assertFalse(db.check_password("wrong password", stored))
        self.assertEqual(self.login("Legacy Lou", PASSWORD).status_code, 200)
        self.assertTrue(db.hash_password(PASSWORD).startswith("scrypt$"))  # server accounts keep scrypt$

    def test_first_account_is_the_admin(self):
        with fresh_db():
            first, first_id = self.register("First Fay")
            second, _ = self.register("Second Sam", PASSWORD)
            self.assertTrue(self.c.get("/api/auth/me", headers=first).json()["isAdmin"])
            self.assertFalse(self.c.get("/api/auth/me", headers=second).json()["isAdmin"])
            lib = topic(f"local-{self.tag}-admin")
            self.assertEqual(self.c.post("/api/topics", json=lib, headers=second).status_code, 403)
            self.assertEqual(self.c.post("/api/topics", json=lib, headers=first).status_code, 200)
            self.assertEqual(self.c.post("/api/simulations/backfill", headers=second).status_code, 403)
            self.assertEqual(self.c.get("/api/agy/inbox", headers=second).status_code, 403)
            self.assertEqual(self.c.get("/api/agy/inbox", headers=first).status_code, 200)
            self.assertEqual(db.conn().execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0], 1)
        server._unlink_topic(None, lib["id"])

    def test_upgrade_makes_the_oldest_user_admin_once(self):
        with fresh_db():
            old = db.get_or_create_user(f"Oldest {self.tag}")
            new = db.get_or_create_user(f"Newer {self.tag}")
            db.conn().execute("UPDATE users SET created_at = created_at - 100 WHERE id = ?", (old["id"],))
            db.conn().commit()
            self.assertFalse(db.is_local_admin(new["id"]))
            self.assertTrue(db.is_local_admin(old["id"]))
            later = db.create_local_account(f"Later {self.tag}", None)
            self.assertFalse(db.is_local_admin(later["id"]))
            self.assertEqual(db.conn().execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0], 1)

    def test_deleting_the_admin_hands_the_role_to_nobody(self):
        with fresh_db():
            admin_headers, admin = self.register("Boss Bo", PASSWORD)
            _, other = self.register("Next Ned")
            self.assertTrue(db.is_local_admin(admin))
            r = self.c.post("/api/auth/forgot-delete", json={"userId": admin, "confirmName": f"Boss Bo {self.tag}"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertFalse(db.is_local_admin(other))

    def test_upgrade_elects_the_admin_before_a_new_account_joins(self):
        with fresh_db():
            old = db.get_or_create_user(f"Elder {self.tag}")
            new = db.create_local_account(f"Newcomer {self.tag}", None)
            self.assertTrue(db.is_local_admin(old["id"]))
            self.assertFalse(db.is_local_admin(new["id"]))

    def test_is_admin_outside_local_mode_is_unchanged(self):
        _, uid = self.register("Mode Mia")
        token = server.CURRENT_USER.set({"id": uid, "name": "x"})
        try:
            server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, False
            self.assertTrue(server.is_admin())  # personal machine: everyone
            server.AUTH_REQUIRED = True
            self.assertFalse(server.is_admin())  # server accounts: SCIEDU_ADMINS only
            with mock.patch.object(server, "ADMINS", {uid}):
                self.assertTrue(server.is_admin())
        finally:
            server.CURRENT_USER.reset(token)

    def test_gemini_key_is_checked_sealed_and_never_returned(self):
        headers, uid = self.register("Key Kim", PASSWORD)
        self.assertEqual(server.RATE_LIMITS["key_check"], 20)
        r = self.put_key(headers, verdict="invalid")
        self.assertEqual(r.status_code, 400)
        self.assertIn("rejected", r.json()["detail"])
        r = self.put_key(headers, verdict="service_disabled")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Gemini API", r.json()["detail"])
        self.assertIsNone(db.get_secret(uid, "gemini"))
        r = self.put_key(headers, key="AIza-secret-key-9876")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["verified"], r.json()["hint"], r.json()["keyState"]), (True, "9876", "ok"))
        self.assertNotIn("AIza-secret", r.text)
        row = db.get_secret(uid, "gemini")
        self.assertEqual((row["mode"], row["hint"]), ("password", "9876"))
        self.assertNotIn(b"AIza-secret", row["ciphertext"])
        self.assertEqual(userkeys.UNLOCKED[uid]["key"], "AIza-secret-key-9876")
        me = self.c.get("/api/auth/me", headers=headers)
        self.assertEqual(me.json()["keyState"], "ok")
        self.assertNotIn("AIza-secret", me.text)
        # the key comes back only with the password
        self.c.post("/api/auth/lock", headers=headers)
        r = self.login("Key Kim", PASSWORD)
        self.assertEqual(r.json()["keyState"], "ok")
        self.assertEqual(userkeys.UNLOCKED[uid]["key"], "AIza-secret-key-9876")
        r = self.c.delete("/api/me/gemini-key", headers=bearer(r.json()["token"]))
        self.assertEqual(r.json(), {"status": "removed", "keyState": "none"})
        self.assertIsNone(db.get_secret(uid, "gemini"))
        self.assertIsNone(userkeys.UNLOCKED[uid]["key"])
        self.assertEqual(self.c.put("/api/me/gemini-key", json={"key": "has spaces in it"}, headers=headers).status_code, 401)

    def test_open_account_key_uses_the_device_key(self):
        headers, uid = self.register("Device Dan")
        self.assertEqual(self.c.put("/api/me/gemini-key", json={"key": "two words"}, headers=headers).status_code, 422)
        r = self.put_key(headers, verdict="unverified")
        self.assertEqual((r.status_code, r.json()["verified"]), (200, False))
        self.assertEqual(db.get_secret(uid, "gemini")["mode"], "device")
        userkeys.UNLOCKED.clear()
        self.assertEqual(self.login("Device Dan").json()["keyState"], "ok")
        userkeys.DEVICE_KEY = None  # no keychain on this computer: nothing is stored, the old key cannot be opened
        userkeys.UNLOCKED.clear()
        r = self.login("Device Dan")
        self.assertEqual(r.json()["keyState"], "locked")
        r = self.put_key(bearer(r.json()["token"]))
        self.assertEqual(r.status_code, 409)
        self.assertIn("Set a password", r.json()["detail"])

    def test_password_set_change_and_remove_rewrap_the_key(self):
        headers, uid = self.register("Rewrap Rae")
        self.put_key(headers, key="AIza-rewrap-0001")
        self.assertEqual(self.c.post("/api/auth/password", json={}, headers=headers).status_code, 422)
        # set: the key moves under the password
        r = self.c.post("/api/auth/password", json={"new": PASSWORD}, headers=headers)
        self.assertEqual((r.status_code, r.json()["hasPassword"], r.json()["keyRemoved"]), (200, True, False))
        self.assertEqual(db.get_secret(uid, "gemini")["mode"], "password")
        # change: the current password is required, then the key opens only with the new one
        self.assertEqual(self.c.post("/api/auth/password", json={"new": "another password"}, headers=headers).status_code, 401)
        r = self.c.post("/api/auth/password", json={"current": "wrong password", "new": "another password"}, headers=headers)
        self.assertEqual(r.status_code, 401)
        r = self.c.post("/api/auth/password", json={"current": PASSWORD, "new": "another password"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        userkeys.UNLOCKED.clear()
        self.assertEqual(self.login("Rewrap Rae", PASSWORD).status_code, 401)
        r = self.login("Rewrap Rae", "another password")
        self.assertEqual(r.json()["keyState"], "ok")
        self.assertEqual(userkeys.UNLOCKED[uid]["key"], "AIza-rewrap-0001")
        headers = bearer(r.json()["token"])
        # remove with a device key: the key moves to device mode
        r = self.c.post("/api/auth/password", json={"current": "another password"}, headers=headers)
        self.assertEqual((r.json()["hasPassword"], r.json()["keyRemoved"], r.json()["keyState"]), (False, False, "ok"))
        self.assertEqual(db.get_secret(uid, "gemini")["mode"], "device")
        self.assertIsNone(db.get_user_auth(uid)["password_hash"])
        # remove without a device key: the key cannot be kept, and the answer says so
        self.c.post("/api/auth/password", json={"new": PASSWORD}, headers=headers)
        userkeys.DEVICE_KEY = None
        r = self.c.post("/api/auth/password", json={"current": PASSWORD}, headers=headers)
        self.assertEqual((r.status_code, r.json()["keyRemoved"], r.json()["keyState"]), (200, True, "none"))
        self.assertIn("removed", r.json()["message"])
        self.assertIsNone(db.get_secret(uid, "gemini"))

    def test_parallel_guesses_cannot_skip_the_backoff(self):
        _, uid = self.register("Race Rex", PASSWORD)
        user = db.get_user_auth(uid)
        for _ in range(6):  # attempts are counted before the password is checked
            server._login_attempt(user["name"])
        with self.assertRaises(server.HTTPException) as e:
            server._login_attempt(user["name"])
        self.assertEqual(e.exception.status_code, 429)

    def test_password_change_and_delete_share_the_backoff(self):
        headers, uid = self.register("Guess Gus", PASSWORD)
        body = {"confirmName": f"Guess Gus {self.tag}", "password": "wrong password"}
        for _ in range(3):
            self.assertEqual(self.c.post("/api/auth/password", json={"current": "wrong password", "new": "x" * 9},
                                         headers=headers).status_code, 401)
        for _ in range(3):
            self.assertEqual(self.c.post("/api/auth/delete-account", json=body, headers=headers).status_code, 401)
        self.assertEqual(self.c.post("/api/auth/delete-account", json=body, headers=headers).status_code, 429)
        self.assertEqual(self.login("Guess Gus", PASSWORD).status_code, 429)
        self.assertIsNotNone(db.get_user(uid))

    def test_logout_signs_out_every_window_of_a_password_account(self):
        a, uid = self.register("Two Tabs", PASSWORD)
        b = bearer(self.login("Two Tabs", PASSWORD).json()["token"])
        self.assertEqual(self.c.post("/api/auth/logout", headers=a).status_code, 200)
        self.assertEqual(self.c.get("/api/topics", headers=b).status_code, 401)
        # a session left without an unlocked key (e.g. lost in a race) is refused as well
        c = bearer(self.login("Two Tabs", PASSWORD).json()["token"])
        userkeys.UNLOCKED.pop(uid)
        self.assertEqual(self.c.get("/api/topics", headers=c).status_code, 401)
        self.assertEqual(self.c.get("/api/topics", headers=c).status_code, 401)
        # an open account's other windows stay signed in (it has nothing to lock)
        o1, _ = self.register("Open Tabs")
        o2 = bearer(self.login("Open Tabs").json()["token"])
        self.c.post("/api/auth/logout", headers=o1)
        self.assertEqual(self.c.get("/api/topics", headers=o2).status_code, 200)

    def test_password_change_ends_the_other_sessions(self):
        a, uid = self.register("Change Cal", PASSWORD)
        b = bearer(self.login("Change Cal", PASSWORD).json()["token"])
        r = self.c.post("/api/auth/password", json={"current": PASSWORD, "new": "another password"}, headers=a)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.c.get("/api/topics", headers=a).status_code, 200)
        self.assertEqual(self.c.get("/api/topics", headers=b).status_code, 401)

    def test_failed_rewrap_keeps_the_old_password_and_key(self):
        headers, uid = self.register("Atomic Ada", PASSWORD)
        self.put_key(headers, key="AIza-atomic-0001")
        before = db.get_user_auth(uid)["password_hash"], db.get_secret(uid, "gemini")["ciphertext"]
        with mock.patch.object(userkeys, "wrap", side_effect=RuntimeError("boom")), self.assertRaises(RuntimeError):
            self.c.post("/api/auth/password", json={"current": PASSWORD, "new": "another password"}, headers=headers)
        self.assertEqual((db.get_user_auth(uid)["password_hash"], db.get_secret(uid, "gemini")["ciphertext"]), before)
        userkeys.UNLOCKED.clear()
        r = self.login("Atomic Ada", PASSWORD)
        self.assertEqual(r.json()["keyState"], "ok")

    def test_export_never_includes_the_sealed_key(self):
        headers, uid = self.register("Export Eve", PASSWORD)
        self.put_key(headers, key="AIza-export-0001")
        r = self.c.get(f"/api/users/{uid}/export", headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("user_secrets", r.text)
        self.assertNotIn("0001", r.text)
        self.assertNotIn("scrypt", r.text)

    def test_lock_drops_the_key_and_the_session(self):
        headers, uid = self.register("Lock Liv", PASSWORD)
        self.put_key(headers)
        self.assertIn(uid, userkeys.UNLOCKED)
        self.assertEqual(self.c.post("/api/auth/lock", headers=headers).json(), {"status": "locked"})
        self.assertNotIn(uid, userkeys.UNLOCKED)
        self.assertEqual(self.c.get("/api/auth/me", headers=headers).status_code, 401)

    def test_forgot_password_deletes_the_account_after_its_name_is_typed(self):
        _, open_id = self.register("Forgot Open")
        headers, uid = self.register("Forgot Fred", PASSWORD)
        self.put_key(headers)
        course = db.create_course(uid, "Fred course", "g", "", [])
        r = self.c.post("/api/auth/forgot-delete", json={"userId": uid, "confirmName": "Fred"})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/auth/forgot-delete", json={"userId": open_id, "confirmName": f"Forgot Open {self.tag}"})
        self.assertEqual(r.status_code, 409)  # an open account just signs in to delete itself
        self.assertEqual(self.c.post("/api/auth/forgot-delete", json={"userId": "u-none", "confirmName": "x"}).status_code, 404)
        r = self.c.post("/api/auth/forgot-delete", json={"userId": uid, "confirmName": f" forgot  FRED {self.tag}"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["removed"]["user_secrets"], 1)
        self.assertIsNone(db.get_user(uid))
        self.assertIsNone(db.get_course(course["id"]))
        self.assertIsNone(db.get_secret(uid, "gemini"))
        self.assertNotIn(uid, userkeys.UNLOCKED)
        self.assertEqual(self.c.get("/api/auth/me", headers=headers).status_code, 401)
        self.assertNotIn(uid, [p["id"] for p in self.c.get("/api/auth/profiles").json()])

    def test_deleting_a_password_account_needs_its_password(self):
        headers, uid = self.register("Delete Dora", PASSWORD)
        body = {"confirmName": f"Delete Dora {self.tag}"}
        self.assertEqual(self.c.post("/api/auth/delete-account", json=body, headers=headers).status_code, 401)
        self.assertEqual(self.c.post("/api/auth/delete-account", json={**body, "password": "wrong password"}, headers=headers).status_code, 401)
        r = self.c.post("/api/auth/delete-account", json={**body, "password": PASSWORD}, headers=headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(db.get_user(uid))
        open_headers, open_id = self.register("Delete Open")  # no password: the typed name is enough
        r = self.c.post(f"/api/users/{open_id}/delete", json={"confirmName": f"Delete Open {self.tag}"}, headers=open_headers)
        self.assertEqual(r.status_code, 200, r.text)

    def test_idle_password_account_locks_itself(self):
        headers, uid = self.register("Idle Ida", PASSWORD)
        self.assertEqual(self.c.get("/api/topics", headers=headers).status_code, 200)
        userkeys.UNLOCKED[uid]["last_active"] = time.time() - 31 * 60
        r = self.c.get("/api/topics/version", headers=headers)  # a poll after the idle time is refused too
        self.assertEqual(r.status_code, 401)
        self.assertIn("locked", r.json()["detail"])
        self.assertNotIn(uid, userkeys.UNLOCKED)
        self.assertEqual(self.c.get("/api/topics", headers=headers).status_code, 401)  # the session is gone

    def test_polls_do_not_count_as_activity(self):
        headers, uid = self.register("Poll Pia", PASSWORD)
        start = time.time() - 100
        userkeys.UNLOCKED[uid]["last_active"] = start
        for path in ("/api/agy/events", "/api/jobs", "/api/jobs/job-none", "/api/topics/version", "/api/status", "/api/auth/me"):
            self.c.get(path, headers=headers)
            self.assertEqual(userkeys.UNLOCKED[uid]["last_active"], start, path)
        self.c.get("/api/topics", headers=headers)
        self.assertGreater(userkeys.UNLOCKED[uid]["last_active"], start)

    def test_auto_lock_minutes_per_account(self):
        headers, uid = self.register("Prefs Pam", PASSWORD)
        self.assertEqual(self.c.put("/api/auth/prefs", json={"autoLockMin": 5000}, headers=headers).status_code, 422)
        self.assertEqual(self.c.put("/api/auth/prefs", json={"autoLockMin": 1}, headers=headers).json(), {"autoLockMin": 1})
        self.assertEqual(self.c.get("/api/auth/me", headers=headers).json()["autoLockMin"], 1)
        userkeys.UNLOCKED[uid]["last_active"] = time.time() - 61
        self.assertEqual(self.c.get("/api/topics", headers=headers).status_code, 401)
        r = self.login("Prefs Pam", PASSWORD)
        headers = bearer(r.json()["token"])
        self.c.put("/api/auth/prefs", json={"autoLockMin": 0}, headers=headers)  # never
        userkeys.UNLOCKED[uid]["last_active"] = time.time() - 86400
        self.assertEqual(self.c.get("/api/topics", headers=headers).status_code, 200)
        # an account without a password never locks itself
        open_headers, open_id = self.register("Prefs Open")
        userkeys.UNLOCKED[open_id]["last_active"] = time.time() - 86400
        self.assertEqual(self.c.get("/api/topics", headers=open_headers).status_code, 200)

    def test_sessions_are_cleared_at_launch_only_locally(self):
        headers, _ = self.register("Launch Leo")
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, False
        server.start_signed_out()
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, True
        self.assertEqual(self.c.get("/api/auth/me", headers=headers).status_code, 200)
        server.start_signed_out()
        self.assertEqual(self.c.get("/api/auth/me", headers=headers).status_code, 401)

    def test_local_endpoints_are_off_in_other_modes(self):
        headers, _ = self.register("Modes Max")
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, False
        for method, path in (("get", "/api/auth/profiles"), ("post", "/api/auth/lock"), ("post", "/api/auth/password"),
                             ("post", "/api/auth/forgot-delete"), ("put", "/api/auth/prefs"), ("put", "/api/me/gemini-key"),
                             ("delete", "/api/me/gemini-key")):
            body = {"get": {}, "delete": {}}.get(method, {"json": {"userId": "u", "confirmName": "x", "autoLockMin": 1, "key": "k"}})
            self.assertEqual(getattr(self.c, method)(path, **body).status_code, 404, path)
        me = self.c.get("/api/auth/me").json()
        self.assertEqual(me, {"user": None, "authRequired": False, "localAccounts": False})


class MigrationBackup(unittest.TestCase):
    """The first start with accounts copies the database once (edu_studio.pre-accounts.db) before migrating it."""
    def old_database(self, d, users=1):
        path = Path(d) / "edu_studio.db"
        c = sqlite3.connect(path)
        c.execute("CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, created_at REAL NOT NULL, last_seen REAL NOT NULL)")
        for i in range(users):
            c.execute("INSERT INTO users VALUES (?, ?, 1, 1)", (f"u-{i}", f"Old {i}"))
        c.commit()
        c.close()
        return path

    @contextlib.contextmanager
    def database_at(self, path):
        old = db.DB_PATH
        with server._purge_running:
            db.close_all()
            db.DB_PATH = path
        try:
            yield
        finally:
            with server._purge_running:
                db.close_all()
                db.DB_PATH = old

    def test_backup_is_written_once_before_the_migration(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.old_database(d)
            backup = Path(d) / "backups" / "edu_studio.pre-accounts.db"
            with self.database_at(path):
                db.init_db()
                self.assertTrue(backup.exists())
                copy = sqlite3.connect(backup)
                tables = {r[0] for r in copy.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                cols = {r[1] for r in copy.execute("PRAGMA table_info(users)")}
                self.assertEqual(copy.execute("SELECT name FROM users").fetchall(), [("Old 0",)])
                copy.close()
                self.assertEqual(tables, {"users"})  # taken before any CREATE or ALTER
                self.assertNotIn("is_admin", cols)
                cols = {r["name"] for r in db.conn().execute("PRAGMA table_info(users)")}
                self.assertTrue({"is_admin", "auto_lock_minutes", "password_hash"} <= cols)
                before = backup.stat().st_mtime_ns
                db.init_db()  # migrated now: no second copy
                self.assertEqual(backup.stat().st_mtime_ns, before)

    def test_existing_backup_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = self.old_database(d)
            backup = Path(d) / "backups" / "edu_studio.pre-accounts.db"
            backup.parent.mkdir()
            backup.write_bytes(b"an earlier copy")
            with self.database_at(path):
                db.init_db()
            self.assertEqual(backup.read_bytes(), b"an earlier copy")

    def test_new_or_empty_database_needs_no_backup(self):
        for users in (None, 0):
            with self.subTest(users=users), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "edu_studio.db" if users is None else self.old_database(d, users)
                with self.database_at(path):
                    db.init_db()
                self.assertFalse((Path(d) / "backups").exists())

class FlagGuard(unittest.TestCase):
    """Every AUTH_REQUIRED / LOCAL_ACCOUNTS read in server.py sits in a function that is meant to tell the modes apart.
    Anything else should call scoped() (both accounts modes) or local_mode() (this computer only)."""
    ALLOWED = {
        "scoped", "local_mode",
        # S rows: server accounts only
        "execute_code", "is_admin", "submit_quiz_answer", "activity_result",
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
