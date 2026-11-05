"""Server pieces for the studio, history, language and general activity tasks: practice item edit/delete endpoints,
tutor persona mode, the extended language roleplay, /api/diagrams, /api/practice/guide and timeline eras.
Offline: shares test_lab's temporary data folder; models are stubbed by replacing server.call_gemini."""
import json
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)

import db


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)  # test_lab's tearDownModule may already have removed the temp dir
    db.init_db()


def fake_model(text, seen=None):
    """A call_gemini stand-in that records its arguments and answers `text`."""
    def fake(contents, role=None, **kw):
        if seen is not None:
            seen.update(contents=contents, role=role, config=kw.get("config"))
        return SimpleNamespace(text=text)
    return fake


PRACTICE = [
    {"id": "p1", "type": "true_false", "prompt": "Water boils at 100 C at sea level", "answer": True},
    {"id": "p2", "type": "fill_blank", "prompt": "F = m ___", "options": ["a", "v", "t"], "answer": "a"},
]


class StudioEndpoints(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = False
        self.c = TestClient(server.app, base_url=LOCAL)
        self.tid = f"studio-{uuid.uuid4().hex[:6]}"
        self.c.post("/api/topics", json=topic(self.tid, practice=PRACTICE,
                                               flashcards=[{"front": "a", "back": "1"}, {"front": "b", "back": "2"}]))

    def get(self):
        return self.c.get(f"/api/topics/{self.tid}").json()

    def test_remove_practice_item(self):
        ids = [p["id"] for p in self.get()["practice"]]
        r = self.c.delete(f"/api/topics/{self.tid}/practice/{ids[0]}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["removed"]["type"], "true_false")
        self.assertEqual([p["id"] for p in self.get()["practice"]], ids[1:])
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/practice/{ids[0]}").status_code, 404)

    def test_replace_practice_item_keeps_id_and_normalizes(self):
        before = self.get()["practice"][1]
        r = self.c.put(f"/api/topics/{self.tid}/practice/{before['id']}",
                       json={"item": {"type": "true_false", "answer": False, "id": "hijack"}})
        self.assertEqual(r.status_code, 200)
        after = self.get()["practice"][1]
        self.assertEqual(after["id"], before["id"])
        self.assertEqual(after["type"], "true_false")
        self.assertEqual(after["prompt"], before["prompt"])  # kept when the new item has none
        self.assertIs(after["answer"], False)
        bad = self.c.put(f"/api/topics/{self.tid}/practice/{before['id']}", json={"type": "fill_blank", "options": ["x"], "answer": "y"})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.get()["practice"][1], after)  # a rejected replacement changes nothing

    def test_remove_flashcard(self):
        r = self.c.delete(f"/api/topics/{self.tid}/flashcards/0")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["removed"]["front"], "a")
        self.assertEqual([c["front"] for c in self.get()["flashcards"]], ["b"])
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/flashcards/5").status_code, 404)

    def test_edits_emit_topic_updated(self):
        cur = self.c.get("/api/agy/events").json()["cursor"]
        self.c.delete(f"/api/topics/{self.tid}/flashcards/0")
        events = self.c.get(f"/api/agy/events?since={cur}").json()["events"]
        self.assertIn(("TOPIC_UPDATED", self.tid), [(e["type"], e["payload"].get("topicId")) for e in events])

    def test_unknown_topic_is_404_and_bad_ids_are_rejected(self):
        self.assertEqual(self.c.delete("/api/topics/no-such-topic/practice/p1").status_code, 404)
        self.assertEqual(self.c.put("/api/topics/no-such-topic/practice/p1", json={"type": "true_false", "prompt": "x", "answer": True}).status_code, 404)
        self.assertEqual(self.c.delete("/api/topics/no-such-topic/flashcards/0").status_code, 404)
        self.assertEqual(self.c.delete("/api/topics/Bad_Id/flashcards/0").status_code, 422)


class StudioOwnerChecks(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = True
        server._rate_hits.pop(("auth", "testclient"), None)
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        tag = uuid.uuid4().hex[:6]

        def acct(name):
            r = self.c.post("/api/auth/register", json={"name": name, "password": "correct horse battery", "adult": True}).json()
            return {"Authorization": f"Bearer {r['token']}"}, r["user"]["id"]
        self.a, self.a_id = acct(f"Extras Alice {tag}")
        self.b, _ = acct(f"Extras Bob {tag}")
        course = db.create_course(self.a_id, "Alice course", "g", "", [])
        self.tid = f"owned-{tag}"
        server.AUTH_REQUIRED = False
        self.c.post("/api/topics", json=topic(self.tid, source={"courseId": course["id"], "workspace": "history"},
                                              practice=PRACTICE, flashcards=[{"front": "a", "back": "1"}],
                                              timeline=[{"year": 1789, "title": "Bastille"}]))
        self.c.post("/api/topics", json=topic(f"shared-{tag}", practice=PRACTICE, flashcards=[{"front": "a", "back": "1"}]))
        server.AUTH_REQUIRED = True
        self.pid = self.c.get(f"/api/topics/{self.tid}", headers=self.a).json()["practice"][0]["id"]
        self.shared = f"shared-{tag}"

    def tearDown(self):
        server.AUTH_REQUIRED = False
        self.ctx.__exit__(None, None, None)
        db.close_all()

    def test_only_the_owner_edits_practice_and_cards(self):
        item = {"type": "true_false", "prompt": "x", "answer": False}
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/practice/{self.pid}", headers=self.b).status_code, 404)
        self.assertEqual(self.c.put(f"/api/topics/{self.tid}/practice/{self.pid}", json=item, headers=self.b).status_code, 404)
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/flashcards/0", headers=self.b).status_code, 404)
        self.assertEqual(self.c.delete(f"/api/topics/{self.shared}/flashcards/0", headers=self.b).status_code, 403)
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/flashcards/0").status_code, 401)  # not signed in
        self.assertEqual(self.c.put(f"/api/topics/{self.tid}/practice/{self.pid}", json=item, headers=self.a).status_code, 200)
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/flashcards/0", headers=self.a).status_code, 200)
        self.assertEqual(self.c.delete(f"/api/topics/{self.tid}/practice/{self.pid}", headers=self.a).status_code, 200)

    def test_persona_and_roleplay_need_a_session_and_hide_other_lessons(self):
        body = {"topicId": self.tid, "mode": "persona", "persona": "Robespierre", "message": "Hi"}
        self.assertEqual(self.c.post("/api/tutor/lesson", json=body).status_code, 401)
        self.assertEqual(self.c.post("/api/tutor/lesson", json=body, headers=self.b).status_code, 404)
        rp = {"topicId": self.tid, "persona": "vendor", "lang": "es", "user_message": "Hola"}
        self.assertEqual(self.c.post("/api/language/roleplay", json=rp).status_code, 401)
        self.assertEqual(self.c.post("/api/language/roleplay", json=rp, headers=self.b).status_code, 404)
        with mock.patch.object(server, "call_gemini", fake_model("Bonjour, citoyen. What do you wish to know?")):
            self.assertEqual(self.c.post("/api/tutor/lesson", json=body, headers=self.a).status_code, 200)
        self.assertEqual(self.c.post("/api/language/roleplay", json=rp, headers=self.a).status_code, 200)


class PersonaMode(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = False
        self.c = TestClient(server.app, base_url=LOCAL)
        self.c.post("/api/topics", json=topic("persona-lesson", markdownContent="# The Terror\n\nThe Committee of Public Safety ...",
                                              timeline=[{"year": 1793, "title": "Law of Suspects", "era": "The Terror"}]))

    def test_persona_prompt_reply_and_history(self):
        seen = {}
        with mock.patch.object(server, "call_gemini", fake_model("I am Robespierre. What brings you to Paris?", seen)):
            r = self.c.post("/api/tutor/lesson", json={
                "topicId": "persona-lesson", "mode": "persona", "persona": "Maximilien Robespierre", "era": "Paris, 1794",
                "message": "Why the Terror?", "history": [{"role": "user", "content": "Hello"}, {"role": "model", "content": "Bonjour"}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["reply"], "I am Robespierre. What brings you to Paris?")
        system = seen["config"].system_instruction
        for needle in ("Maximilien Robespierre", "Paris, 1794", "first person", "Never invent quotations", "120 words",
                       "Committee of Public Safety", "Law of Suspects"):
            self.assertIn(needle, system)
        self.assertEqual([c.role for c in seen["contents"]], ["user", "model", "user"])
        self.assertEqual(seen["contents"][-1].parts[0].text, "Why the Terror?")

    def test_persona_is_required_and_other_modes_are_unchanged(self):
        r = self.c.post("/api/tutor/lesson", json={"topicId": "persona-lesson", "mode": "persona", "message": "hi"})
        self.assertEqual(r.status_code, 422)
        seen = {}
        with mock.patch.object(server, "call_gemini", fake_model("What do you notice?", seen)):
            r = self.c.post("/api/tutor/lesson", json={"topicId": "persona-lesson", "message": "help"})
        self.assertEqual(r.json()["reply"], "What do you notice?")
        self.assertIn("Socratic tutor", seen["config"].system_instruction)
        self.assertEqual(self.c.post("/api/tutor/lesson", json={"topicId": "nope-missing", "mode": "persona", "persona": "x"}).status_code, 404)

    def test_offline_model_gives_503(self):
        r = self.c.post("/api/tutor/lesson", json={"topicId": "persona-lesson", "mode": "persona", "persona": "Danton"})
        self.assertEqual(r.status_code, 503)


class LanguageRoleplayExtension(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = False
        self.c = TestClient(server.app, base_url=LOCAL)

    def test_old_request_shape_still_works_offline(self):
        r = self.c.post("/api/language/roleplay", json={"scenario": "At the Café", "target_lang": "es",
                                                        "user_message": "Hola", "history": [], "level": "A2"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        for k in ("reply", "translation", "feedback", "suggested_replies", "corrections"):
            self.assertIn(k, data)
        self.assertTrue(all(isinstance(c, str) for c in data["feedback"]["corrections"]))
        self.assertTrue(all(set(c) == {"said", "better", "why"} for c in data["corrections"]))
        self.assertTrue(data["fallback"])

    def test_dialogue_fields_shape_the_prompt_and_corrections_come_back_structured(self):
        self.c.post("/api/topics", json=topic("market-unit", markdownContent="# Market\n\nlas manzanas, el pan"))
        reply = {"reply": "¡Claro! ¿Cuántas manzanas quiere?", "translation": "Sure! How many apples?",
                 "feedback": {"has_corrections": True, "tip": "Use quiero.",
                              "corrections": [{"said": "Yo querer manzanas", "better": "Quiero manzanas", "why": "conjugate querer"}]},
                 "suggested_replies": ["Dos, por favor."]}
        seen = {}
        with mock.patch.object(server, "call_gemini", fake_model(json.dumps(reply), seen)):
            r = self.c.post("/api/language/roleplay", json={
                "topicId": "market-unit", "persona": "a fruit vendor", "setting": "a market in Seville", "goal": "buy apples",
                "lang": "es", "level": "A1", "history": [{"role": "user", "content": "Yo querer manzanas"}]})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["corrections"], [{"said": "Yo querer manzanas", "better": "Quiero manzanas", "why": "conjugate querer"}])
        self.assertEqual(data["feedback"]["corrections"], ["Yo querer manzanas → Quiero manzanas (conjugate querer)"])
        self.assertTrue(data["feedback"]["has_corrections"])
        system = seen["config"].system_instruction
        for needle in ("a fruit vendor", "a market in Seville", "buy apples", "(es)", "CEFR A1", "las manzanas"):
            self.assertIn(needle, system)
        self.assertEqual(seen["contents"][-1].parts[0].text, "Yo querer manzanas")  # not duplicated from history
        self.assertEqual(len(seen["contents"]), 1)

    def test_string_corrections_from_the_model_still_map(self):
        reply = {"reply": "Bien", "translation": "Good", "feedback": {"has_corrections": True, "corrections": ["Say 'un café'"], "tip": ""},
                 "suggested_replies": []}
        with mock.patch.object(server, "call_gemini", fake_model(json.dumps(reply))):
            data = self.c.post("/api/language/roleplay", json={"scenario": "cafe", "target_lang": "es", "user_message": "cafe"}).json()
        self.assertEqual(data["feedback"]["corrections"], ["Say 'un café'"])
        self.assertEqual(data["corrections"], [{"said": "", "better": "", "why": "Say 'un café'"}])

    def test_unknown_topic_and_own_rate_limit(self):
        self.assertEqual(self.c.post("/api/language/roleplay", json={"topicId": "missing-unit", "lang": "es"}).status_code, 404)
        self.assertEqual(self.c.post("/api/language/roleplay", json={"topicId": "../server", "lang": "es"}).status_code, 422)
        self.assertIn("language_roleplay", server.RATE_LIMITS)
        server._rate_hits.pop(("language_roleplay", "testclient"), None)
        self.c.post("/api/language/roleplay", json={"lang": "es", "user_message": "Hola"})
        self.assertEqual(len(server._rate_hits[("language_roleplay", "testclient")]), 1)


class DiagramsAndGuide(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(server.app, base_url=LOCAL)

    def test_lists_names_only(self):
        r = self.c.get("/api/diagrams")
        self.assertEqual(r.status_code, 200)
        names = r.json()["diagrams"]
        on_disk = sorted(p.name for p in server.DIAGRAMS_DIR.glob("*.svg")) if server.DIAGRAMS_DIR.is_dir() else []
        self.assertEqual(names, on_disk)
        self.assertTrue(all("/" not in n and n.endswith(".svg") for n in names))

    def test_traversal_and_odd_names_are_rejected(self):
        for bad in ("../server.py", "..%2Fserver.py", "../../etc/passwd", "/etc/passwd", "cell.svg/../x.svg", ".hidden.svg",
                    "server.py", "a b.svg", "x\\..\\y.svg"):
            self.assertEqual(self.c.get("/api/diagrams", params={"name": bad}).status_code, 400, bad)
        ok = self.c.get("/api/diagrams", params={"name": "no-such-diagram.svg"}).json()
        self.assertEqual(ok, {"name": "no-such-diagram.svg", "exists": False, "image": "/diagrams/no-such-diagram.svg"})

    def test_practice_guide_covers_every_type(self):
        guide = self.c.get("/api/practice/guide").json()
        self.assertEqual(set(guide), set(server.PRACTICE_NORMALIZERS))
        self.assertTrue(all(isinstance(v, str) for v in guide.values()))
        self.assertEqual(set(server.PRACTICE_NORMALIZERS), server.PRACTICE_TYPES)


class TimelineEra(unittest.TestCase):
    def test_era_is_optional_and_bounded(self):
        out = server.normalize_timeline([{"year": 1793, "title": "Law of Suspects", "era": "The Terror " * 20},
                                         {"year": -44, "title": "Caesar", "era": "  "}, {"year": 1789, "title": "Bastille"}])
        self.assertEqual([e["title"] for e in out], ["Caesar", "Bastille", "Law of Suspects"])
        self.assertEqual(len(out[2]["era"]), 60)
        self.assertNotIn("era", out[0])
        self.assertEqual(set(out[1]), {"year", "title", "date", "detail"})  # unchanged shape without an era

    def test_new_types_are_in_the_generation_prompts(self):
        extras = server.WORKSPACE_EXTRAS
        for t in ("categorize", "cause_effect", "source_analysis"):
            self.assertIn(f'"type": "{t}"', extras["history"])
        for t in ("story", "conjugate"):
            self.assertIn(f'"type": "{t}"', extras["language"])
        self.assertIn('"type": "sort_by"', extras["lab"])
        self.assertIn('"type": "spot_the_bug"', extras["code"])
        self.assertIn('"type": "cloze"', extras["math"])


if __name__ == "__main__":
    unittest.main()
