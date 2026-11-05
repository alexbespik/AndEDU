"""Language exercises (gamified practice types), the normalizer registry and the language MCP tools.
Offline: shares test_lab's temporary data folder and its Gemini stub."""
import json
import shutil
import unittest

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)

import mcp_server
import mcp_tools_language

N = server.normalize_practice


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)  # test_lab's tearDownModule may already have removed the temp dir


def tearDownModule():
    pass


class LanguagePracticeTypes(unittest.TestCase):
    def one(self, item):
        out = N([{"prompt": "p", **item}])
        return out[0] if out else None

    def test_translate(self):
        t = self.one({"type": "translate", "source": "Good night", "answer": "Buenas noches", "lang": "es",
                      "accepted": ["buenas noches", "Buenas noches", *[f"alt {i}" for i in range(9)]]})
        self.assertEqual(t["answer"], "Buenas noches")
        self.assertNotIn("Buenas noches", t["accepted"])
        self.assertLessEqual(len(t["accepted"]), 6)
        self.assertIsNone(self.one({"type": "translate", "source": "x", "answer": "", "lang": "es"}))
        self.assertIsNone(self.one({"type": "translate", "answer": "x", "lang": "es"}))

    def test_word_bank_needs_every_answer_word(self):
        ok = self.one({"type": "word_bank", "answer": "Yo como pan", "bank": ["Yo", "como", "pan", "agua"], "lang": "es"})
        self.assertEqual(ok["bank"], ["Yo", "como", "pan", "agua"])
        punct_ok = self.one({"type": "word_bank", "answer": "Yo como pan.", "bank": ["Yo", "como", "pan", "agua"], "lang": "es"})
        self.assertIsNotNone(punct_ok)
        self.assertEqual(punct_ok["bank"], ["Yo", "como", "pan", "agua"])
        self.assertIsNone(self.one({"type": "word_bank", "answer": "Yo como pan", "bank": ["Yo", "como", "agua", "tú"]}))
        self.assertIsNone(self.one({"type": "word_bank", "answer": "a a b", "bank": ["a", "b", "c", "d"]}))  # needs two "a" tiles
        self.assertIsNone(self.one({"type": "word_bank", "answer": "a b", "bank": ["a", "b", "c"]}))        # bank too small

    def test_listening_and_speaking(self):
        lt = self.one({"type": "listen_type", "audio_text": "Buenos días", "lang": "es"})
        self.assertEqual(lt["answer"], "Buenos días")
        self.assertIsNone(self.one({"type": "listen_type", "audio_text": "Buenos días"}))  # no language to read it in
        lc = self.one({"type": "listen_choose", "audio_text": "gato", "options": ["gato", "pato", "rato"], "answer": "gato", "lang": "es"})
        self.assertIn("gato", lc["options"])
        self.assertIsNone(self.one({"type": "listen_choose", "audio_text": "gato", "options": ["pato", "rato"], "answer": "gato", "lang": "es"}))
        sp = self.one({"type": "speak", "target": "Добрий день", "lang": "uk", "ipa": "ˈdɔbrɪj dɛnʲ"})
        self.assertEqual(sp["lang"], "uk")
        self.assertIsNone(self.one({"type": "speak", "target": "x", "lang": "not a lang"}))

    def test_prompt_is_required_for_every_type(self):
        self.assertEqual(N([{"type": "speak", "target": "hola", "lang": "es"}]), [])

    def test_old_types_unchanged(self):
        items = [
            {"type": "fill_blank", "prompt": "p", "options": ["a", "b"], "answer": "b"},
            {"type": "order_steps", "prompt": "p", "steps": ["1", "2", "3"]},
            {"type": "numeric", "prompt": "p", "answer": "4.2", "tolerance": 0.05, "unit": "m"},
            {"type": "numeric", "prompt": "p", "answer": "nope"},
            {"type": "true_false", "prompt": "p", "answer": False},
            {"type": "true_false", "prompt": "p", "answer": "false"},
            {"type": "code", "prompt": "p", "tests": "assert f() == 1"},
            {"type": "code", "prompt": "p", "tests": "print('assert')"},
            {"type": "match_pairs", "prompt": "p", "pairs": [["a", "1"], ["b", "2"], ["c", "3"]]},
            {"type": "draw", "prompt": "p", "criteria": ["arrow"], "background": "nope"},
            {"type": "unknown", "prompt": "p"},
            {"type": ["translate"], "prompt": "p"},
        ]
        out = N(items)
        self.assertEqual([p["type"] for p in out], ["fill_blank", "order_steps", "numeric", "true_false", "code", "match_pairs", "draw"])
        self.assertEqual(out[2]["answer"], 4.2)
        self.assertIs(out[3]["answer"], False)
        self.assertEqual(out[6]["background"], "grid")
        self.assertEqual([p["id"] for p in out], ["p1", "p2", "p3", "p5", "p7", "p9", "p10"])

    def test_registry_and_type_set_agree(self):
        self.assertEqual(set(server.PRACTICE_NORMALIZERS), server.PRACTICE_TYPES)


class LanguageUnits(unittest.TestCase):
    UNIT = {"title": "Spanish: At the café", "lang": "es",
            "words": [{"word": "café", "meaning": "coffee", "ipa": "kaˈfe"}, {"word": "agua", "meaning": "water"}, {"word": "pan", "meaning": "bread"}],
            "phrases": [{"text": "Un café, por favor", "meaning": "A coffee, please"}, {"text": "La cuenta, por favor", "meaning": "The bill, please"}]}

    def test_unit_topic_survives_the_server(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            r = c.post("/api/topics", json=mcp_tools_language.unit_topic(self.UNIT))
            self.assertEqual(r.status_code, 200, r.text)
            t = c.get("/api/topics/spanish-at-the-cafe").json()
        self.assertEqual(t.get("workspace"), "language")
        self.assertEqual(len(t["flashcards"]), 3)
        self.assertEqual(t["flashcards"][0]["lang"], "es")
        kinds = [p["type"] for p in t["practice"]]
        for k in ("match_pairs", "translate", "word_bank", "listen_type", "speak"):
            self.assertIn(k, kinds)
        self.assertEqual(len(kinds), len(mcp_tools_language.unit_topic(self.UNIT)["practice"]))  # nothing dropped

    def test_exercises_reach_a_lesson_through_the_practice_endpoint(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/topics", json=topic("lang-practice"))
            r = c.post("/api/topics/lang-practice/practice", json={"items": [
                {"type": "translate", "prompt": "Translate", "source": "Thanks", "answer": "Gracias", "lang": "es"},
                {"type": "listen_choose", "prompt": "?", "audio_text": "sí", "options": ["no"], "answer": "sí", "lang": "es"}]}).json()
            t = c.get("/api/topics/lang-practice").json()
        self.assertEqual([p["type"] for p in t["practice"]], ["translate"])
        self.assertIn("1", json.dumps(r))


class LanguageMcpTools(unittest.TestCase):
    def test_tools_are_listed_with_schemas(self):
        names = {t["name"]: t for t in mcp_server.handle({"method": "tools/list", "id": 1})["tools"]}
        for n in ("add_translation_exercise", "add_word_bank", "add_listening_exercise", "add_speaking_exercise",
                  "add_language_exercises", "add_vocab_set", "build_language_unit", "start_language_session",
                  "open_language_tab", "language_overview"):
            self.assertIn(n, names)
            self.assertEqual(names[n]["inputSchema"]["type"], "object")
        self.assertEqual(len(names), len(mcp_server.TOOLS))  # no duplicate names

    def test_tool_calls_build_valid_requests(self):
        sent = []
        orig = mcp_server.call
        try:
            fake = lambda method, path, body=None: sent.append((method, path, body)) or {"ok": True}
            tools = {n: fn for n, _, _, fn in mcp_tools_language.tools(fake, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR)}
            tools["add_word_bank"]({"topic_id": "t", "answer": "Yo como pan", "distractors": ["agua", "tú"], "lang": "es"})
            tools["add_listening_exercise"]({"topic_id": "t", "audio_text": "gato", "lang": "es", "kind": "choose", "options": ["gato", "pato", "rato"]})
            tools["start_language_session"]({"mode": "listen"})
        finally:
            mcp_server.call = orig
        bank = sent[0][2]["items"][0]
        self.assertEqual(N([bank])[0]["bank"], ["Yo", "como", "pan", "agua", "tú"])
        self.assertEqual(N([sent[1][2]["items"][0]])[0]["type"], "listen_choose")
        self.assertEqual(sent[2][2], {"type": "SWITCH_STUDIO_MODE", "payload": {"mode": "language", "tab": "session", "sessionMode": "listen", "unitId": None}})


class LanguageAIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app, base_url=LOCAL)

    def test_language_roleplay_fallback(self):
        res = self.client.post("/api/language/roleplay", json={
            "scenario": "At the Café",
            "target_lang": "es",
            "user_message": "Hola, un café por favor",
            "history": [],
            "level": "A2"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("reply", data)
        self.assertIn("translation", data)
        self.assertIn("feedback", data)
        self.assertIn("suggested_replies", data)
        self.assertIsInstance(data["feedback"]["has_corrections"], bool)
        self.assertIsInstance(data["feedback"]["corrections"], list)
        self.assertIsInstance(data["suggested_replies"], list)
        self.assertTrue(len(data["reply"]) > 0)
        self.assertTrue(len(data["suggested_replies"]) > 0)

    def test_tutor_explain_answer_fallback(self):
        res = self.client.post("/api/tutor/explain-answer", json={
            "question": "Translate: The boy drinks water.",
            "student_answer": "El niño bebo agua.",
            "correct_answer": "El niño bebe agua.",
            "context": "The boy drinks water.",
            "lang": "es"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("verdict", data)
        self.assertIn("explanation", data)
        self.assertIn("key_rule", data)
        self.assertIn("example", data)
        self.assertTrue(len(data["verdict"]) > 0)
        self.assertTrue(len(data["explanation"]) > 0)


if __name__ == "__main__":
    unittest.main()
