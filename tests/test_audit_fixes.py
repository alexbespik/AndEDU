"""Fixes from the Nov 2026 audit: XP awards under concurrency, stable daily quests. Offline, shares test_lab's setup."""
import threading
import unittest

from test_lab import db, engage, server  # noqa: F401  (sets up the temp data dir first)


def setUpModule():
    # test_lab's tearDownModule removes the shared temp folder (test_lab cleans it up at the end of the run)
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()


class XpAwards(unittest.TestCase):
    def test_concurrent_identical_awards_pay_once(self):
        user = db.get_or_create_user("Double Clicker")
        results, start = [], threading.Barrier(8)

        def go():
            start.wait()
            results.append(engage.award(user["id"], "2026-11-04", "practice_correct", "topic:p1")["xp"])
            db.conn().close()

        threads = [threading.Thread(target=go) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), [0] * 7 + [engage.SOURCES["practice_correct"][0]])

    def test_daily_quests_do_not_change_during_the_day(self):
        user = db.get_or_create_user("Quest Keeper")
        day = "2026-11-05"
        first = [q["id"] for q in engage.quests(user["id"], day)]
        engage.award(user["id"], day, "review_session", "s1")   # changes what the picker would see
        engage.award(user["id"], day, "practice_correct", "x")
        self.assertEqual([q["id"] for q in engage.quests(user["id"], day)], first)


class DatabaseIndexes(unittest.TestCase):
    def test_sqlite_foreign_key_indexes_exist(self):
        c = db.conn()
        try:
            rows = c.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
            index_names = {r["name"] for r in rows}
            self.assertIn("lessons_by_course", index_names)
            self.assertIn("sessions_by_user", index_names)
            self.assertIn("courses_by_user", index_names)
            self.assertIn("attempts_by_topic", index_names)
        finally:
            db.close_conn()


if __name__ == "__main__":
    unittest.main()


class QuizLookup(unittest.TestCase):
    def test_matches_the_players_rules(self):
        topic = {"quiz": [
            {"question": "bad", "options": ["a", "b"], "correctAnswer": 5},           # not gradable, position 0
            {"question": "legacy", "options": ["a", "b"], "correct": "1"},           # no id, legacy key
            {"id": "q3", "question": "id", "options": ["a", "b", "c"], "correctAnswer": 2},
        ]}
        self.assertIsNone(server.find_quiz_question(topic, "0"))
        self.assertEqual(server.find_quiz_question(topic, "1")["correctAnswer"], 1)   # position in the full quiz
        self.assertEqual(server.find_quiz_question(topic, "q3")["correctAnswer"], 2)
        self.assertIsNone(server.find_quiz_question(topic, "2"))                      # position of an item that has an id


class RequestGuards(unittest.TestCase):
    def test_cross_site_writes_are_refused(self):
        from test_lab import LOCAL, TestClient
        with TestClient(server.app, base_url=LOCAL) as c:
            self.assertEqual(c.post("/api/quiz/submit", json={}, headers={"Origin": "https://evil.example"}).status_code, 403)
            self.assertNotEqual(c.post("/api/quiz/submit", json={}, headers={"Origin": "http://localhost:5173"}).status_code, 403)
            self.assertNotEqual(c.post("/api/quiz/submit", json={}, headers={"Origin": "http://localhost"}).status_code, 403)  # same origin
            self.assertEqual(c.get("/api/status", headers={"Origin": "https://evil.example"}).status_code, 200)  # reads stay CORS's job

    def test_chunked_body_with_a_small_content_length_is_still_capped(self):
        import asyncio
        sent = []

        async def app(scope, receive, send):
            sent.append("app")

        mw = server.BodyLimitMiddleware(app)
        chunks = [{"type": "http.request", "body": b"x" * 1_000_000, "more_body": True} for _ in range(3)]

        async def receive():
            return chunks.pop(0)

        async def send(msg):
            sent.append(msg.get("status"))

        scope = {"type": "http", "path": "/api/topics", "headers": [(b"content-length", b"10"), (b"transfer-encoding", b"chunked")]}
        asyncio.run(mw(scope, receive, send))
        self.assertIn(413, sent)
        self.assertNotIn("app", sent)

    def test_one_user_cannot_spend_the_whole_daily_budget(self):
        old = (server.AUTH_REQUIRED, server.USER_DAILY_MODEL_CALLS, dict(server._budget))
        try:
            server.AUTH_REQUIRED, server.USER_DAILY_MODEL_CALLS = True, 2
            server._budget.update(day="", used=0, users={})
            token = server.CLIENT_KEY.set("user-a")
            server.spend_model_call()
            server.spend_model_call()
            with self.assertRaises(RuntimeError):
                server.spend_model_call()
            server.CLIENT_KEY.reset(token)
            server.CLIENT_KEY.set("user-b")
            server.spend_model_call()  # others still have their share
        finally:
            server.AUTH_REQUIRED, server.USER_DAILY_MODEL_CALLS = old[0], old[1]
            server._budget.clear()
            server._budget.update(old[2])
            server.CLIENT_KEY.set("local")
