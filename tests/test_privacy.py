"""Privacy (PRIVACY_AND_DEPLOYMENT.md §3): consent, "Export my data", "Delete my account and data", the course-delete
race that left orphan lesson files, and the catalog upsert keeping known prereqs/descriptions."""
from test_lab import LOCAL, TestClient, server, db, engage  # noqa: F401  (sets up the temp content dir first)

import json
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

import advisor
from local_accounts import BothFlagsMixin, LocalAccountsMixin, local_account

REAL_QUEUE = server.queue_course_generation  # some test_lab tests replace it for good; captured at import
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PASSWORD = "correct horse battery"


def setUpModule():
    # test_lab's tearDownModule removes the shared temp dir; recreate what these tests need
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    server.NOTES_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()
    advisor.init()


def clear_auth_limit():
    server._rate_hits.pop(("auth", "testclient"), None)


def user_id_tables():
    """Every table in the database that has a user_id column."""
    c = db.conn()
    names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    return [t for t in names if "user_id" in {r["name"] for r in c.execute(f"PRAGMA table_info({t})")}]


def fill_user_tables(uid):
    """One row per USER_DATA_TABLES table for this user, whatever its columns (NOT NULL ones get a placeholder)."""
    c = db.conn()
    for t in db.USER_DATA_TABLES:
        cols = list(c.execute(f"PRAGMA table_info({t})"))
        if not cols:
            continue
        values = {"user_id": uid}
        for col in cols:
            if col["name"] in values or col["pk"] and col["type"].upper() == "INTEGER" or not col["notnull"] or col["dflt_value"] is not None:
                continue
            values[col["name"]] = 1 if col["type"].upper() in ("INTEGER", "REAL") else f"{t}-{uuid.uuid4().hex[:6]}"
        c.execute(f"INSERT INTO {t} ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    c.commit()


def append_quiz_log(*user_ids):
    with open(server.RESULTS_FILE, "a", encoding="utf-8") as f:
        for uid in user_ids:
            f.write(json.dumps({"userId": uid, "topicId": "t", "questionId": 0, "selected": 0, "isCorrect": True}) + "\n")


def quiz_log_users():
    if not server.RESULTS_FILE.exists():
        return []
    return [json.loads(line).get("userId") for line in server.RESULTS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def seed(uid, tag):
    """A course with one class whose lesson exists as a topic file, notes file and lesson row, plus data in every table."""
    course = db.create_course(uid, f"Course {tag}", "goal", "materials", [])
    db.replace_classes(course["id"], [{"title": "Class one"}])
    tid = f"priv-{tag}-lesson"
    topic, _ = server.save_topic({"id": tid, "title": "Lesson", "category": "Physics", "markdownContent": "# Lesson",
                                  "source": {"kind": "course", "courseId": course["id"]}}, course_id=course["id"])
    server.write_notes_file(topic)
    db.update_class(db.list_classes(course["id"])[0]["id"], status="ready", topic_id=tid)
    fill_user_tables(uid)
    append_quiz_log(uid)
    return course, tid


class AccountsCase(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = True
        clear_auth_limit()
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        self.tag = uuid.uuid4().hex[:6]
        self.a, self.a_id, self.a_name = self.acct(f"Privacy Alice {self.tag}")
        self.b, self.b_id, _ = self.acct(f"Privacy Bob {self.tag}")

    def acct(self, name):
        r = self.c.post("/api/auth/register", json={"name": name, "password": PASSWORD, "adult": True, "privacy": True})
        self.assertEqual(r.status_code, 200, r.text)
        r = r.json()
        return {"Authorization": f"Bearer {r['token']}"}, r["user"]["id"], name

    def tearDown(self):
        server.AUTH_REQUIRED = False
        clear_auth_limit()
        self.ctx.__exit__(None, None, None)
        db.close_all()

    def delete(self, headers, name=None, password=PASSWORD):
        clear_auth_limit()
        return self.c.post("/api/auth/delete-account", headers=headers,
                           json={"confirmName": self.a_name if name is None else name, "password": password})


class Export(AccountsCase):
    def test_export_holds_all_of_the_users_data_and_no_secrets(self):
        course, tid = seed(self.a_id, self.tag)
        seed(self.b_id, self.tag + "b")
        r = self.c.get(f"/api/users/{self.a_id}/export", headers=self.a)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn(f'filename="andedu-export-{self.a_id}-', r.headers["content-disposition"])
        self.assertTrue(r.headers["content-disposition"].startswith("attachment;"))
        self.assertEqual(r.headers["cache-control"], "no-store")
        data = r.json()
        self.assertEqual((data["format"], data["version"]), ("andedu-export", 1))
        self.assertEqual(data["user"]["id"], self.a_id)
        existing = {t for t in db.USER_DATA_TABLES if db.conn().execute(f"PRAGMA table_info({t})").fetchall()}
        self.assertTrue(existing)
        for t in existing:
            self.assertGreaterEqual(len(data["tables"][t]), 1, t)
            self.assertTrue(all(row["user_id"] == self.a_id for row in data["tables"][t]), t)
        self.assertEqual([c["id"] for c in data["courses"]], [course["id"]])
        self.assertEqual(len(data["courses"][0]["classes"]), 1)
        self.assertIn(tid, [lesson["topic_id"] for lesson in data["lessons"]])
        self.assertEqual(list(data["topics"]), [tid])
        self.assertIn("# Lesson", data["notes"][tid])
        self.assertEqual([q["userId"] for q in data["quizLog"]], [self.a_id])
        self.assertTrue(data["consent"]["privacyVersion"])
        self.assertTrue(data["user"]["privacy_version"])  # the user row keeps its consent fields, only secrets go
        for secret in ("password_hash", "token_hash", "scrypt$"):
            self.assertNotIn(secret, r.text)
        self.assertNotIn(self.b_id, r.text)

    def test_someone_elses_export_is_forbidden(self):
        seed(self.a_id, self.tag)
        self.assertEqual(self.c.get(f"/api/users/{self.a_id}/export", headers=self.b).status_code, 403)


class DeleteAccount(AccountsCase):
    def test_wrong_name_password_or_admin_id_is_refused(self):
        r = self.delete(self.a, name="Someone Else")
        self.assertEqual(r.status_code, 422)
        self.assertIn("name", r.json()["detail"])
        self.assertEqual(self.delete(self.a, password="not my password").status_code, 401)
        with mock.patch.object(server, "ADMINS", {self.a_id}):
            r = self.delete(self.a, name=f"  privacy   ALICE {self.tag} ")  # spacing and case do not matter
            self.assertEqual(r.status_code, 409)
            self.assertIn("SCIEDU_ADMINS", r.json()["detail"])
        self.assertIsNotNone(db.get_user(self.a_id))

    def test_delete_removes_the_user_everywhere_and_leaves_shared_data(self):
        course, tid = seed(self.a_id, self.tag)
        _, bob_tid = seed(self.b_id, self.tag + "b")
        library = f"priv-{self.tag}-library"
        server.save_topic({"id": library, "title": "Library", "category": "Physics", "markdownContent": "# L"})
        db.record_attempt(None, library, "q1", 0, True)  # a local-mode answer with no owner
        append_quiz_log(None)
        nulls_before = db.conn().execute("SELECT COUNT(*) FROM quiz_attempts WHERE user_id IS NULL").fetchone()[0]

        r = self.delete(self.a)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "deleted")
        self.assertEqual(r.json()["removed"]["users"], 1)

        c = db.conn()
        for t in user_id_tables():
            self.assertEqual(c.execute(f"SELECT COUNT(*) FROM {t} WHERE user_id = ?", (self.a_id,)).fetchone()[0], 0, t)
        self.assertIsNone(db.get_user(self.a_id))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM classes WHERE course_id = ?", (course["id"],)).fetchone()[0], 0)
        self.assertIsNone(db.get_lesson(tid))
        self.assertFalse(server.topic_path(tid).exists())
        self.assertFalse((server.NOTES_DIR / f"{tid}.md").exists())
        self.assertTrue(server.topic_path(library).exists())
        self.assertTrue(server.topic_path(bob_tid).exists())
        self.assertIsNotNone(db.get_lesson(bob_tid))
        users = quiz_log_users()
        self.assertNotIn(self.a_id, users)
        self.assertIn(self.b_id, users)
        self.assertIn(None, users)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM quiz_attempts WHERE user_id IS NULL").fetchone()[0], nulls_before)
        self.assertNotIn(tid, {t["id"] for t in server.read_topics_cached()})

        self.assertEqual(self.c.get("/api/auth/me", headers=self.a).status_code, 401)
        self.assertIn(self.delete(self.a).status_code, (401, 404))
        self.assertEqual(self.c.get("/api/auth/me", headers=self.b).status_code, 200)

    def test_delete_drops_the_users_jobs_and_events(self):
        server.JOBS["job-priv-" + self.tag] = {"id": "job-priv-" + self.tag, "owner": self.a_id, "status": "done", "created": time.time()}
        server.emit_event("COURSE_UPDATED", {"courseId": "x"}, owner=self.a_id)
        self.assertEqual(self.delete(self.a).status_code, 200)
        self.assertNotIn("job-priv-" + self.tag, server.JOBS)
        self.assertFalse([e for e in server.ui_events_queue if e.get("owner") == self.a_id and e["type"] == "COURSE_UPDATED"])


class LocalDelete(unittest.TestCase):
    def setUp(self):
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def test_local_profile_is_deleted_by_name_without_a_password(self):
        user = db.get_or_create_user(f"Local Privacy {uuid.uuid4().hex[:6]}")
        _, tid = seed(user["id"], uuid.uuid4().hex[:6])
        self.assertEqual(self.c.post(f"/api/users/{user['id']}/delete", json={"confirmName": "nope"}).status_code, 422)
        r = self.c.post(f"/api/users/{user['id']}/delete", json={"confirmName": user["name"].upper()})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(db.get_user(user["id"]))
        self.assertFalse(server.topic_path(tid).exists())
        self.assertEqual(self.c.post(f"/api/users/{user['id']}/delete", json={"confirmName": user["name"]}).status_code, 404)
        self.assertEqual(self.c.post("/api/auth/delete-account", json={"confirmName": user["name"]}).status_code, 404)


class Guard(unittest.TestCase):
    def test_every_user_id_table_is_covered_by_export_and_delete(self):
        # user_secrets: delete_user removes it explicitly; exports must never carry the sealed keys
        known = set(db.USER_DATA_TABLES) | {"users", "courses", "classes", "lessons", "sessions", "user_secrets"}
        missing = [t for t in user_id_tables() if t not in known]
        self.assertEqual(missing, [], "add these tables to db.USER_DATA_TABLES so export and delete cover them")


class Consent(AccountsCase):
    def test_sign_up_needs_the_privacy_notice_and_login_reports_it(self):
        clear_auth_limit()
        r = self.c.post("/api/auth/register", json={"name": f"Privacy Carl {self.tag}", "password": PASSWORD, "adult": True})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "Please accept the privacy notice.")
        self.assertIsNone(db.get_user_by_name(f"Privacy Carl {self.tag}"))
        login = self.c.post("/api/auth/login", json={"name": self.a_name, "password": PASSWORD}).json()
        self.assertIs(login["privacyAccepted"], True)
        db.set_consent(self.a_id, "privacy", "2000-01-01")  # an older notice
        login = self.c.post("/api/auth/login", json={"name": self.a_name, "password": PASSWORD}).json()
        self.assertIs(login["privacyAccepted"], False)
        r = self.c.post(f"/api/users/{self.a_id}/consent", json={"kind": "privacy"}, headers=self.a)
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()["privacyAccepted"], True)
        self.assertEqual(self.c.post(f"/api/users/{self.a_id}/consent", json={"kind": "privacy"}, headers=self.b).status_code, 403)
        self.assertEqual(self.c.post(f"/api/users/{self.a_id}/consent", json={"kind": "cookies"}, headers=self.a).status_code, 422)

    def test_status_reports_privacy_version(self):
        s = self.c.get("/api/status").json()
        self.assertEqual(s["privacy_version"], server.PRIVACY_VERSION)
        self.assertIs(s["auth_required"], True)
        self.assertIsInstance(s["elevenlabs_enabled"], bool)
        self.assertIsInstance(s["port"], int)

    def test_image_upload_needs_upload_consent(self):
        calls = []

        async def fake_gemini(contents, role=None, **kwargs):
            calls.append(contents)
            return SimpleNamespace(text="transcribed board")

        with mock.patch.object(server, "acall_gemini", fake_gemini):
            r = self.c.post("/api/upload-multimodal", headers=self.a, files={"file": ("board.png", PNG, "image/png")})
            self.assertEqual(r.status_code, 428)
            self.assertIn("Google Gemini", r.json()["detail"])
            self.assertEqual(calls, [])
            self.assertEqual(self.c.post(f"/api/users/{self.a_id}/consent", json={"kind": "upload"}, headers=self.a).status_code, 200)
            r = self.c.post("/api/upload-multimodal", headers=self.a, files={"file": ("board.png", PNG, "image/png")})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertIn("transcribed board", r.json()["extracted_text"])
            self.assertEqual(len(calls), 1)
            # Bob has not agreed, and a course built from uploaded files is gated the same way
            self.assertEqual(self.c.post("/api/upload-multimodal", headers=self.b,
                                         files={"file": ("board.png", PNG, "image/png")}).status_code, 428)
            r = self.c.post("/api/courses", headers=self.b, json={"userId": self.b_id, "materials_text": "notes " * 20,
                                                                 "filenames": ["notes.pdf"]})
            self.assertEqual(r.status_code, 428)
        self.assertIsNotNone(db.get_consent(self.a_id)["uploadConsentAt"])


class OrphanLessons(unittest.TestCase):
    """A class that finishes (or fails) after its course was deleted must not leave a topic file behind,
    or it shows up as a shared library lesson."""

    def setUp(self):
        self.ctx = TestClient(server.app, base_url=LOCAL)  # its lifespan gives jobs an event loop
        self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def run_build(self, fail):
        user = db.get_or_create_user(f"Race {uuid.uuid4().hex[:6]}")
        course = db.create_course(user["id"], "Race", "goal", "", [])
        db.update_course(course["id"], status="ready", concepts=[])
        db.replace_classes(course["id"], [{"title": "Only class"}])
        tid = f"race-{uuid.uuid4().hex[:6]}"

        async def fake_build(course_row, klass, classes, on_step=None):
            topic = {"id": tid, "title": "Race", "category": "Physics", "markdownContent": "# Race",
                     "source": {"kind": "course", "courseId": course_row["id"]}}
            server.save_json_file(server.topic_path(tid), topic)
            server.write_notes_file(server.normalize_topic(topic)[0])
            db.delete_course(course_row["id"])  # the student deletes the course mid-build
            if fail:
                raise RuntimeError("lesson row refused")
            return topic

        with mock.patch.object(server, "build_class", fake_build), \
                mock.patch.object(server, "queue_course_generation", REAL_QUEUE):
            job = server.queue_course_generation(course["id"])
            deadline = time.time() + 5
            while server.JOBS[job["id"]]["status"] in ("queued", "running") and time.time() < deadline:
                time.sleep(0.02)
        self.assertEqual(server.JOBS[job["id"]]["status"], "done")
        self.assertTrue(server.JOBS[job["id"]]["result"]["cancelled"])
        self.assertFalse(server.topic_path(tid).exists())
        self.assertFalse((server.NOTES_DIR / f"{tid}.md").exists())

    def test_finished_class_of_a_deleted_course_leaves_no_files(self):
        self.run_build(fail=False)

    def test_failed_class_of_a_deleted_course_leaves_no_files(self):
        self.run_build(fail=True)

    def test_purge_course_artifacts_only_touches_that_course(self):
        user = db.get_or_create_user(f"Purge {uuid.uuid4().hex[:6]}")
        mine, other = (db.create_course(user["id"], n, "g", "", []) for n in ("Mine", "Other"))
        tids = {}
        for course in (mine, other):
            tids[course["id"]] = f"purge-{uuid.uuid4().hex[:6]}"
            saved, _ = server.save_topic({"id": tids[course["id"]], "title": "P", "category": "Physics", "markdownContent": "# P",
                                          "source": {"courseId": course["id"]}}, course_id=course["id"])
            server.write_notes_file(saved)
        self.assertEqual(server.purge_course_artifacts(mine["id"]), 2)  # topic file + notes
        self.assertFalse(server.topic_path(tids[mine["id"]]).exists())
        self.assertTrue(server.topic_path(tids[other["id"]]).exists())
        self.assertTrue((server.NOTES_DIR / f"{tids[other['id']]}.md").exists())
        self.assertIsNotNone(db.get_lesson(tids[mine["id"]]))  # lesson rows are not purged here


class CatalogUpsert(unittest.TestCase):
    def test_a_later_upsert_with_empty_fields_keeps_known_prereqs_and_description(self):
        advisor.upsert_courses([{"code": "PRVY 210", "title": "Privacy Law", "description": "Data protection.",
                                 "prereqs": "PRVY 110"}], "test 2025-2026 catalog")
        advisor.upsert_courses([{"code": "PRVY 210", "title": "Privacy Law", "description": "", "prereqs": ""}], "schedule")
        c = advisor.get_course("PRVY 210")
        self.assertEqual(c["description"], "Data protection.")
        self.assertEqual(c["prereqs"], "PRVY 110")
        self.assertIn("PRVY 110", json.dumps(c["prereq_codes"]))



# The same isolation checks with accounts on this computer (SCIEDU_LOCAL_ACCOUNTS), and with both flags set (server
# accounts win). Deleting a local account (password rules) comes with local sign-in.
class ExportLocal(LocalAccountsMixin, Export):
    def acct(self, name):
        return (*local_account(name), name)


class ExportBothFlags(BothFlagsMixin, Export):
    pass


class DeleteAccountBothFlags(BothFlagsMixin, DeleteAccount):
    pass


class ConsentBothFlags(BothFlagsMixin, Consent):
    pass


if __name__ == "__main__":
    unittest.main()
