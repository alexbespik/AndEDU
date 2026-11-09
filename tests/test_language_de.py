"""Built-in German course (language_de.py) and POST /api/language/seed. Offline; shares test_lab's temporary data folder."""
import re
import unittest
import uuid

from test_lab import LOCAL, TestClient, server  # noqa: F401  (sets up the temp data dir first)

import db
import language_de
import mcp_tools_language

ARTICLE = {"m": "der", "f": "die", "n": "das", "pl": "die"}


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)


def remove_seeded():
    for p in server.TOPICS_DIR.glob("de-*.json"):
        p.unlink()


class GermanCourse(unittest.TestCase):
    def test_ten_units_with_de_ids(self):
        topics = language_de.unit_topics()
        self.assertGreaterEqual(len(topics), 10)
        ids = [t["id"] for t in topics]
        self.assertEqual(len(set(ids)), len(ids))
        for t in topics:
            self.assertTrue(t["id"].startswith("de-") and server.TOPIC_ID_RE.fullmatch(t["id"]), t["id"])
            self.assertEqual(t["source"]["workspace"], "language")
            self.assertEqual(t["lang"], "de")

    def test_every_unit_normalizes_without_drops(self):
        for t in language_de.unit_topics():
            items = server.normalize_practice(t["practice"])
            self.assertEqual(len(items), len(t["practice"]), t["id"])
            topic, warnings = server.normalize_topic({**t, "practice": items})
            self.assertEqual(warnings, [], t["id"])
            self.assertEqual(len(topic["flashcards"]), len(t["flashcards"]), t["id"])
            kinds = {p["type"] for p in items}
            for k in ("match_pairs", "translate", "word_bank", "listen_type", "speak", "fill_blank"):
                self.assertIn(k, kinds, t["id"])

    def test_cards_are_german_and_nouns_carry_their_article(self):
        for unit in language_de.UNITS:
            cards = mcp_tools_language.unit_topic({**unit, "lang": "de"})["flashcards"]
            for w, card in zip(unit["words"], cards):
                self.assertEqual(card["lang"], "de")
                if w["word"][0].isupper() and w["word"] not in ("Hallo",):  # German nouns are capitalized
                    self.assertIn(w["gender"], ARTICLE, w["word"])
                if w["gender"]:
                    self.assertTrue(card["front"].startswith(ARTICLE[w["gender"]] + " "), card["front"])
                    self.assertEqual(card["article"], ARTICLE[w["gender"]])
                    if w["plural"]:
                        self.assertIn(f"Plural: die {w['plural']}.", card["hint"])

    def test_word_banks_contain_their_answers_and_match_pairs_are_unique(self):
        for t in language_de.unit_topics():
            for p in t["practice"]:
                if p["type"] == "word_bank":
                    self.assertLessEqual(len(p["bank"]), 14)
                    self.assertEqual(len(p["bank"]), len(set(p["bank"])), p["answer"])  # no duplicate tiles
                if p["type"] == "match_pairs":
                    rights = [r for _, r in p["pairs"]]
                    self.assertEqual(len(rights), len(set(rights)), t["id"])
                if p["type"] == "fill_blank":
                    self.assertIn("___", p["prompt"])
                    self.assertIn(p["answer"], p["options"])

    def test_unit_topic_stays_backward_compatible(self):
        t = mcp_tools_language.unit_topic({"title": "Spanish: food", "lang": "es",
                                           "words": [{"word": "pan", "meaning": "bread"}, {"word": "agua", "meaning": "water"}, {"word": "sal", "meaning": "salt"}]})
        self.assertEqual([c["front"] for c in t["flashcards"]], ["pan", "agua", "sal"])
        self.assertNotIn("gender", t["flashcards"][0])
        self.assertIn("| Word | Meaning | Pronunciation |", t["markdownContent"])
        self.assertNotIn("source", t)


class SeedEndpoint(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = False
        remove_seeded()
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

    def tearDown(self):
        server.AUTH_REQUIRED = False
        self.ctx.__exit__(None, None, None)
        remove_seeded()

    def test_seed_is_idempotent_and_never_overwrites(self):
        r = self.c.post("/api/language/seed", json={"lang": "de"})
        self.assertEqual(r.status_code, 200, r.text)
        created = r.json()["created"]
        self.assertEqual(len(created), len(language_de.UNITS))
        self.assertEqual(r.json()["dropped"], {})
        t = self.c.get(f"/api/topics/{created[0]}").json()
        self.assertEqual(t["workspace"], "language")
        self.assertTrue(all(p.get("id") for p in t["practice"]))
        # an edited unit stays as the student or teacher left it
        path = server.topic_path(created[0])
        path.write_text(path.read_text(encoding="utf-8").replace("German 1:", "Edited 1:"), encoding="utf-8")
        again = self.c.post("/api/language/seed", json={"lang": "de"}).json()
        self.assertEqual(again["created"], [])
        self.assertEqual(sorted(again["skipped"]), sorted(created))
        self.assertIn("Edited 1:", path.read_text(encoding="utf-8"))

    def test_unknown_language(self):
        self.assertEqual(self.c.post("/api/language/seed", json={"lang": "xx"}).status_code, 400)

    def test_admin_only_in_accounts_mode(self):
        server.AUTH_REQUIRED = True
        server._rate_hits.pop(("auth", "testclient"), None)
        self.assertEqual(self.c.post("/api/language/seed", json={"lang": "de"}).status_code, 401)
        reg = self.c.post("/api/auth/register", json={"name": f"Seed {uuid.uuid4().hex[:6]}", "password": "password123",
                                                     "adult": True, "privacy": True}).json()
        h = {"Authorization": f"Bearer {reg['token']}"}
        self.assertEqual(self.c.post("/api/language/seed", json={"lang": "de"}, headers=h).status_code, 403)
        self.assertEqual(list(server.TOPICS_DIR.glob("de-*.json")), [])
        old = set(server.ADMINS)
        server.ADMINS.add(reg["user"]["id"])
        try:
            r = self.c.post("/api/language/seed", json={"lang": "de"}, headers=h)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(len(r.json()["created"]), len(language_de.UNITS))
        finally:
            server.ADMINS.clear()
            server.ADMINS.update(old)
            db.close_all()


class WordOrder(unittest.TestCase):
    """Cheap checks on the German itself: verb-final after weil/dass, prefix at the end of separable verbs."""
    def test_subordinate_clauses_end_with_a_verb(self):
        verbs = {"bin", "kommt", "hat", "ist", "will", "habe", "regnet"}
        for unit in language_de.UNITS:
            for p in unit["phrases"]:
                for clause in re.findall(r"\b(?:weil|dass|wenn|Wenn)\b([^,.?!]*)", p["text"]):
                    self.assertIn(clause.split()[-1], verbs, p["text"])


if __name__ == "__main__":
    unittest.main()
