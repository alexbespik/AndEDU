"""Advisor chat keywords: generic request verbs never crowd out the topic words."""
import unittest
import uuid

from test_lab import LOCAL, server  # noqa: E402  (sets up the temporary data folder and offline Gemini)
import advisor  # noqa: E402
import advisor_chat  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class Keywords(unittest.TestCase):
    def test_request_verbs_are_dropped(self):
        kws = advisor_chat._keywords("could you find me some stoic courses, please show anything interesting")
        for w in ("find", "could", "some", "please", "show", "anything"):
            self.assertNotIn(w, kws)
        self.assertIn("stoic", kws)


class StoicContext(unittest.TestCase):
    def test_context_surfaces_matching_courses(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            user = c.post("/api/users", json={"name": f"Stoic {uuid.uuid4().hex[:6]}"}).json()
            uid = user.get("id") or user["user"]["id"]
            advisor.upsert_courses([{"code": "ZQPH 210", "title": "Stoic Ethics", "credits": "3",
                                     "description": "Stoic philosophy of living well."}], "test")
            ctx = advisor_chat.build_context(uid, "could you find me some stoic courses")
            self.assertIn("ZQPH 210", ctx)


if __name__ == "__main__":
    unittest.main()
