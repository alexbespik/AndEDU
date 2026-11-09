"""Security-audit fixes (admins by id, private reviews/activities, inbox, sign-in limits, body caps, uploads,
server-graded quizzes, voice ids, code proposals, headers, gzip, topic cache) and the reviewer's bug list."""
from test_lab import LOCAL, TestClient, server, db, engage  # noqa: F401  (sets up the temp content dir first)

import io
import json
import os
import unittest
import uuid
import zipfile
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException


def setUpModule():
    # test_lab's tearDownModule removes the shared temp dir; recreate what these tests need
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()


def topic(tid, **extra):
    return {"id": tid, "title": "Audit", "category": "Physics", "markdownContent": "# Audit", **extra}


QUIZ = [{"id": "q1", "question": "2+2?", "options": ["4", "5"], "correctAnswer": 0}]


def reply(*calls, text=""):
    return SimpleNamespace(text=text, function_calls=[SimpleNamespace(name=n, args=a) for n, a in calls])


def clear_auth_limit():
    server._rate_hits.pop(("auth", "testclient"), None)


class AccountsCase(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = True
        clear_auth_limit()
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        self.tag = uuid.uuid4().hex[:6]
        self.a, self.a_id = self.acct(f"Audit Alice {self.tag}")
        self.b, self.b_id = self.acct(f"Audit Bob {self.tag}")

    def acct(self, name):
        r = self.c.post("/api/auth/register", json={"name": name, "password": "correct horse battery", "adult": True, "privacy": True}).json()
        return {"Authorization": f"Bearer {r['token']}"}, r["user"]["id"]

    def tearDown(self):
        server.AUTH_REQUIRED = False
        clear_auth_limit()
        self.ctx.__exit__(None, None, None)
        db.close_all()

    def alice_lesson(self, tid):
        course = db.create_course(self.a_id, "Alice course", "g", "", [])
        server.save_topic(topic(tid, quiz=QUIZ, source={"courseId": course["id"]}))
        return course


class AdminsAndSignUp(AccountsCase):
    def test_admins_are_user_ids_not_names(self):
        server.save_topic(topic("audit-shared-lib"))
        with mock.patch.object(server, "ADMINS", {self.a_id}):
            self.assertEqual(self.c.post("/api/topics", json=topic("audit-shared-lib"), headers=self.a).status_code, 200)
            self.assertEqual(self.c.post("/api/topics", json=topic("audit-shared-lib"), headers=self.b).status_code, 403)
        with mock.patch.object(server, "ADMINS", {f"audit bob {self.tag}", f"Audit Bob {self.tag}"}):
            self.assertEqual(self.c.post("/api/topics", json=topic("audit-shared-lib"), headers=self.b).status_code, 403)

    def test_sign_up_cannot_claim_a_password_less_profile(self):
        local = db.get_or_create_user(f"Audit Carol {self.tag}")
        r = self.c.post("/api/auth/register", json={"name": local["name"], "password": "correct horse battery", "adult": True, "privacy": True})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(db.get_user(local["id"]).get("password_hash"))

    def test_eleventh_sign_in_in_a_minute_is_refused(self):
        clear_auth_limit()
        codes = [self.c.post("/api/auth/login", json={"name": f"Audit Alice {self.tag}", "password": "wrong guess"}).status_code
                 for _ in range(11)]
        self.assertEqual(codes, [401] * 10 + [429])
        self.assertEqual(self.c.post("/api/auth/register", json={"name": f"Audit Dan {self.tag}", "password": "correct horse battery",
                                                                  "adult": True, "privacy": True}).status_code, 429)


class PrivateLessons(AccountsCase):
    def test_review_and_activities_skip_lessons_the_user_cannot_see(self):
        self.alice_lesson("audit-alice-review")
        bob, alice = db.get_user(self.b_id), db.get_user(self.a_id)
        for user, visible in ((bob, False), (alice, True)):
            token = server.CURRENT_USER.set(user)
            try:
                self.assertEqual(server._review_question("audit-alice-review", "q1") is not None, visible)
            finally:
                server.CURRENT_USER.reset(token)
        body = {"topicId": "audit-alice-review", "kind": "speed", "correct": 1, "total": 1}
        self.assertEqual(self.c.post(f"/api/activity/{self.b_id}/result", json=body, headers=self.b).status_code, 404)
        self.assertEqual(self.c.post(f"/api/activity/{self.a_id}/result", json=body, headers=self.a).status_code, 200)

    def test_inbox_needs_an_admin(self):
        self.assertEqual(self.c.get("/api/agy/inbox", headers=self.b).status_code, 403)
        self.assertEqual(self.c.post("/api/agy/inbox", json={"task": "x"}, headers=self.b).status_code, 403)
        with mock.patch.object(server, "ADMINS", {self.a_id}):
            self.assertEqual(self.c.get("/api/agy/inbox", headers=self.a).status_code, 200)

    def test_quiz_question_must_exist_with_accounts(self):
        server.save_topic(topic("audit-lib-quiz", quiz=QUIZ))
        answer = {"topicId": "audit-lib-quiz", "questionId": "nope", "selected": 0, "isCorrect": True}
        self.assertEqual(self.c.post("/api/quiz/submit", json=answer, headers=self.a).status_code, 404)

    def test_code_proposals_and_topic_lists_stay_private(self):
        self.alice_lesson("audit-alice-secret")
        seen = {}

        async def fake(contents, role=None, **kw):
            seen["system"] = kw["config"].system_instruction
            return reply(("execute_python_code", {"code": "print(1)"}))
        cur = self.c.get("/api/agy/events", headers=self.a).json()["cursor"]
        with mock.patch.object(server, "acall_gemini", side_effect=fake):
            self.c.post("/api/agy/prompt", json={"prompt": "check it"}, headers=self.b)
        self.assertNotIn("audit-alice-secret", seen["system"])
        self.assertEqual(self.c.get(f"/api/agy/events?since={cur}", headers=self.a).json()["events"], [])
        types_b = [e["type"] for e in self.c.get(f"/api/agy/events?since={cur}", headers=self.b).json()["events"]]
        self.assertIn("CODE_PROPOSAL", types_b)
        self.assertFalse(server.MESSAGES_FILE.exists() and "check it" in server.MESSAGES_FILE.read_text(encoding="utf-8"))


class PersonalMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx = TestClient(server.app, base_url=LOCAL)
        cls.c = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)
        db.close_all()

    def test_inbox_file_is_capped(self):
        server.INBOX_FILE.write_text("x" * (server.MAX_INBOX_FILE_BYTES + 1), encoding="utf-8")
        try:
            self.assertEqual(self.c.post("/api/agy/inbox", json={"task": "x"}).status_code, 507)
        finally:
            server.INBOX_FILE.unlink()
        self.assertEqual(self.c.post("/api/agy/inbox", json={"task": "x"}).status_code, 200)

    def test_oversized_bodies_get_413(self):
        big = b'{"x": "' + b"a" * (server.MAX_BODY_BYTES + 10) + b'"}'
        self.assertEqual(self.c.post("/api/topics", content=big, headers={"Content-Type": "application/json"}).status_code, 413)

        def chunks():  # no Content-Length: counted as it streams
            for _ in range(3):
                yield b"a" * 1_000_000
        self.assertEqual(self.c.post("/api/topics", content=chunks(), headers={"Content-Type": "application/json"}).status_code, 413)
        self.assertNotEqual(self.c.post("/api/upload-multimodal", content=big[:3_000_000],
                                        headers={"Content-Type": "application/json"}).status_code, 413)  # uploads get 30 MB

    def test_docx_zip_bomb_is_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i in range(server.MAX_DOCX_MEMBERS + 1):
                z.writestr(f"word/m{i}.xml", "")
        with self.assertRaises(HTTPException) as e:
            server.extract_document(buf.getvalue(), "bomb.docx")
        self.assertEqual(e.exception.status_code, 413)
        r = self.c.post("/api/upload-multimodal", files={"file": ("bomb.docx", buf.getvalue(), "application/octet-stream")})
        self.assertEqual(r.status_code, 413)
        small = io.BytesIO()
        with zipfile.ZipFile(small, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", "0" * 5000)
        with mock.patch.object(server, "MAX_DOCX_UNZIPPED", 1000), self.assertRaises(HTTPException):
            server.check_docx_archive(small.getvalue(), "big.docx")

    def test_quiz_is_graded_on_the_server(self):
        server.save_topic(topic("audit-graded", quiz=QUIZ))
        right = self.c.post("/api/quiz/submit", json={"topicId": "audit-graded", "questionId": "q1", "selected": 0, "isCorrect": False}).json()
        wrong = self.c.post("/api/quiz/submit", json={"topicId": "audit-graded", "questionId": "q1", "selected": 1, "isCorrect": True}).json()
        self.assertEqual((right["isCorrect"], wrong["isCorrect"]), (True, False))
        # personal machine, unknown question: the client's verdict is all there is
        other = self.c.post("/api/quiz/submit", json={"topicId": "audit-graded", "questionId": "zz", "selected": 1, "isCorrect": True}).json()
        self.assertTrue(other["isCorrect"])

    def test_voice_id_is_checked(self):
        bad = {"content_markdown": "x", "voice_id": "../../v1/user", "api_key": "k"}
        self.assertEqual(self.c.post("/api/elevenlabs-voiceover", json=bad).status_code, 400)
        with mock.patch.object(server, "ELEVENLABS_ENABLED", False):  # never reach the real API with a local key
            self.assertEqual(self.c.post("/api/elevenlabs-voiceover", json={"content_markdown": "x", "voice_id": "george"}).status_code, 200)

    def test_assistant_proposes_code_instead_of_running_it(self):
        cur = self.c.get("/api/agy/events").json()["cursor"]
        with mock.patch.object(server, "acall_gemini", side_effect=mock.AsyncMock(
                return_value=reply(("execute_python_code", {"code": "x = 1\n" * 5000, "reason": "check"})))), \
                mock.patch.object(server, "run_python_sandboxed", side_effect=AssertionError("must not run")):
            r = self.c.post("/api/agy/prompt", json={"prompt": "compute"}).json()
        self.assertEqual(r["reply"], "Proposed to the student; it runs only if they click Run.")
        proposals = [e for e in self.c.get(f"/api/agy/events?since={cur}").json()["events"] if e["type"] == "CODE_PROPOSAL"]
        self.assertEqual(len(proposals), 1)
        self.assertLessEqual(len(proposals[0]["payload"]["code"].encode()), 20_000)
        self.assertEqual(proposals[0]["payload"]["reason"], "check")

    def test_security_headers(self):
        h = self.c.get("/api/status").headers
        self.assertEqual((h["x-content-type-options"], h["x-frame-options"], h["referrer-policy"]),
                         ("nosniff", "SAMEORIGIN", "same-origin"))

    def test_large_topic_list_is_gzipped(self):
        server.save_topic(topic("audit-gzip", markdownContent="# Big\n\n" + "text " * 2000))
        r = self.c.get("/api/topics", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(r.headers.get("content-encoding"), "gzip")
        self.assertIn("audit-gzip", [t["id"] for t in r.json()])

    def test_topic_cache_follows_direct_file_writes(self):
        path = server.topic_path("audit-cache")
        path.write_text(json.dumps(topic("audit-cache", title="First")), encoding="utf-8")
        first = next(t for t in server.read_topics_cached() if t["id"] == "audit-cache")
        self.assertIs(first, next(t for t in server.read_topics_cached() if t["id"] == "audit-cache"))  # not re-parsed
        path.write_text(json.dumps(topic("audit-cache", title="Second, rewritten by agy")), encoding="utf-8")
        titles = [t["title"] for t in self.c.get("/api/topics").json() if t["id"] == "audit-cache"]
        self.assertEqual(titles, ["Second, rewritten by agy"])
        server.save_topic(topic("audit-cache", title="Third"))
        self.assertEqual([t["title"] for t in server.read_topics_cached() if t["id"] == "audit-cache"], ["Third"])
        path.unlink()
        server.read_topics_cached()
        self.assertNotIn(path, server._TOPIC_CACHE)  # deleted files leave the cache

    def test_rewritten_class_starts_over(self):
        user = db.get_or_create_user(f"Audit Regen {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Course", "g", "", [])
        db.replace_classes(course["id"], [{"title": "One"}])
        k = db.list_classes(course["id"])[0]
        server.save_topic(topic("audit-regen", quiz=QUIZ, source={"courseId": course["id"]}))
        db.update_class(k["id"], status="ready", topic_id="audit-regen")
        with mock.patch.object(server, "queue_course_generation", lambda cid: None), \
                mock.patch.object(server, "adapt_next_class", lambda p: None):
            self.c.post("/api/quiz/submit", json={"userId": user["id"], "topicId": "audit-regen", "questionId": "q1", "selected": 0})
            self.assertEqual(db.list_classes(course["id"])[0]["completed"], 1)
            self.assertEqual(self.c.post(f"/api/courses/{course['id']}/classes/1/regenerate", json={}).status_code, 200)
            k = db.list_classes(course["id"])[0]
            self.assertEqual((k["completed"], k["attempts"], k["score"]), (0, 0, None))
            self.assertEqual(db.conn().execute("SELECT COUNT(*) FROM quiz_attempts WHERE topic_id = 'audit-regen'").fetchone()[0], 0)
            db.update_class(k["id"], status="generating")
            self.assertEqual(self.c.post(f"/api/courses/{course['id']}/classes/1/regenerate", json={}).status_code, 409)

    def test_roleplay_history_and_fallback(self):
        seen = {}

        async def fake(contents, role=None, **kw):
            seen["contents"] = contents
            return SimpleNamespace(text=json.dumps({"reply": "Hola", "translation": "Hi", "feedback": {}, "suggested_replies": []}))
        body = {"scenario": "cafe", "target_lang": "es", "user_message": "Un café",
                "history": [{"sender": "partner", "text": "¡Hola!"}, {"sender": "user", "text": "Un café"}]}
        with mock.patch.object(server, "acall_gemini", side_effect=fake):
            r = self.c.post("/api/language/roleplay", json=body).json()
        # the partner's opening line is kept after a synthetic first user turn; the message isn't sent twice
        self.assertEqual([c.role for c in seen["contents"]], ["user", "model", "user"])
        self.assertEqual(seen["contents"][1].parts[0].text, "¡Hola!")
        self.assertEqual(seen["contents"][-1].parts[0].text, "Un café")
        self.assertNotIn("fallback", r)
        self.assertTrue(self.c.post("/api/language/roleplay", json=body).json()["fallback"])  # offline: scripted partner


class StaticCaching(unittest.TestCase):
    def test_assets_are_immutable_and_index_revalidates(self):
        import tempfile
        from fastapi import FastAPI
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "assets"))
            open(os.path.join(d, "index.html"), "w").write("<!doctype html><title>x</title>")
            open(os.path.join(d, "assets", "app-abc123.js"), "w").write("console.log(1)")
            app = FastAPI()
            app.mount("/", server.FrontendFiles(directory=d, html=True), name="frontend")
            with TestClient(app) as c:
                self.assertEqual(c.get("/assets/app-abc123.js").headers["cache-control"], "public, max-age=31536000, immutable")
                self.assertEqual(c.get("/").headers["cache-control"], "no-cache")
                self.assertEqual(c.get("/index.html").headers["cache-control"], "no-cache")


class Normalizers(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_non_finite_numeric_items_are_dropped(self):
        items = server.normalize_practice([
            {"type": "numeric", "prompt": "p", "answer": "inf"},
            {"type": "numeric", "prompt": "p", "answer": "nan"},
            {"type": "numeric", "prompt": "p", "answer": 1, "tolerance": float("inf")},
            {"type": "numeric", "prompt": "p", "answer": 2, "tolerance": 0.1},
        ])
        self.assertEqual([i["answer"] for i in items], [2.0])

    def test_bool_answer_key_and_gradable_total(self):
        self.assertIsNone(server.normalize_quiz_item({"question": "?", "options": ["x", "y"], "correctAnswer": True}, 0))
        user = db.get_or_create_user(f"Audit Total {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Course", "g", "", [])
        db.replace_classes(course["id"], [{"title": "One"}])
        k = db.list_classes(course["id"])[0]
        db.upsert_lesson({"id": "audit-total", "title": "T", "quiz": [
            QUIZ[0], {"id": "q2", "question": "?", "options": ["a"], "correctAnswer": 3},
            {"id": "q3", "question": "?", "options": ["a", "b"], "correctAnswer": True}]}, course["id"])
        db.update_class(k["id"], status="ready", topic_id="audit-total")
        progress = db.record_attempt(user["id"], "audit-total", "q1", 0, True)
        self.assertEqual((progress["score"], progress["completed"]), (1.0, True))

    def test_job_ids_are_unique_within_one_millisecond(self):
        async def work(job):
            return None
        before = set(server.JOBS)
        with mock.patch.object(server, "MAIN_LOOP", None), mock.patch.object(server.time, "time", return_value=1_900_000_000.0):
            for _ in range(2):
                with self.assertRaises(RuntimeError):  # no event loop outside uvicorn: recorded, then refused
                    server.start_job("audit", "audit", work)
        new = set(server.JOBS) - before
        for j in new:
            server.JOBS.pop(j, None)
        self.assertEqual(len(new), 2)


if __name__ == "__main__":
    unittest.main()
