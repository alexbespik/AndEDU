"""Extra language practice types (story, dialogue, conjugate, script_match), their MCP tools and pure helpers.
Offline: shares test_lab's temporary data folder and its Gemini stub."""
import re
import unittest
from pathlib import Path

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)

import mcp_server
import mcp_tools_language_extra as mx
import practice_language_extra as px

ROOT = Path(__file__).resolve().parent.parent


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)


BASE = {"id": "p1", "prompt": "p", "explanation": "", "concept": None}

STORY = {"type": "story", "title": "En el café", "lang": "es",
         "lines": [{"speaker": "Ana", "text": "Hola, ¿qué tal?", "translation": "Hi, how are you?"},
                   {"speaker": "Luis", "text": "Bien. ¿Un café?"}, {"speaker": "Ana", "text": "Sí, con leche."},
                   {"speaker": "Luis", "text": "Aquí tienes."}],
         "questions": [{"after": 2, "question": "What does Ana want?", "options": ["tea", "coffee with milk"], "answer": "coffee with milk"}]}
DIALOGUE = {"type": "dialogue", "persona": "a baker in Seville", "setting": "a bakery", "goal": "buy two loaves", "lang": "es", "level": "A2"}
CONJ = {"type": "conjugate", "verb": "hablar", "tense": "present", "lang": "es", "forms": [["yo", "hablo"], ["tú", "hablas"], ["él", "habla"]]}
SCRIPT = {"type": "script_match", "script": "hiragana", "pairs": [["あ", "a"], ["い", "i"], ["う", "u"], ["え", "e"]]}


class Both:
    """Checks each item through the module directly and through server.normalize_practice (once merged)."""

    def kept(self, item):
        direct = px.NORMALIZERS[item["type"]](item, {**BASE, "type": item["type"]})
        self.assertIsNotNone(direct, item)
        via = server.normalize_practice([{"prompt": "p", **item}])
        self.assertEqual(len(via), 1, item)
        return direct

    def dropped(self, item):
        self.assertIsNone(px.NORMALIZERS[item["type"]](item, {**BASE, "type": item["type"]}), item)
        self.assertEqual(server.normalize_practice([{"prompt": "p", **item}]), [], item)


class Story(Both, unittest.TestCase):
    def test_kept(self):
        s = self.kept(STORY)
        self.assertEqual(len(s["lines"]), 4)
        self.assertEqual(s["lines"][0]["translation"], "Hi, how are you?")
        self.assertNotIn("translation", s["lines"][1])
        self.assertEqual(s["questions"][0]["after"], 2)

    def test_dropped(self):
        self.dropped({**STORY, "lines": STORY["lines"][:3]})                       # fewer than 4 lines
        self.dropped({**STORY, "lines": []})
        self.dropped({**STORY, "lang": "Spanish"})
        self.dropped({**STORY, "questions": [{**STORY["questions"][0], "answer": "juice"}]})  # answer not in options
        self.dropped({**STORY, "questions": [{**STORY["questions"][0], "after": 9}]})         # no such line
        self.dropped({**STORY, "questions": []})

    def test_long_story_is_cut_and_bad_questions_skipped(self):
        lines = [{"speaker": "A", "text": f"línea {i}"} for i in range(20)]
        s = self.kept({**STORY, "lines": lines, "questions": STORY["questions"] + [{"after": 1, "question": "?", "options": ["a", "a"], "answer": "a"}]})
        self.assertEqual(len(s["lines"]), 16)
        self.assertEqual(len(s["questions"]), 1)


class Dialogue(Both, unittest.TestCase):
    def test_kept(self):
        d = self.kept(DIALOGUE)
        self.assertEqual((d["persona"], d["lang"], d["level"]), ("a baker in Seville", "es", "A2"))
        self.assertEqual(self.kept({**DIALOGUE, "level": ""})["level"], "A2")

    def test_dropped(self):
        for k in ("persona", "setting", "goal"):
            self.dropped({**DIALOGUE, k: ""})
        self.dropped({**DIALOGUE, "lang": "español"})


class Conjugate(Both, unittest.TestCase):
    def test_kept(self):
        c = self.kept(CONJ)
        self.assertEqual(c["forms"][1], ["tú", "hablas"])
        self.assertEqual(self.kept({**CONJ, "forms": [{"pronoun": p, "form": f} for p, f in CONJ["forms"]]})["forms"], CONJ["forms"])

    def test_dropped(self):
        self.dropped({**CONJ, "forms": []})
        self.dropped({**CONJ, "forms": CONJ["forms"][:2]})                          # fewer than 3
        self.dropped({**CONJ, "forms": CONJ["forms"] * 3})                          # more than 8 (and repeated)
        self.dropped({**CONJ, "forms": CONJ["forms"] + [["yo", "hablo"]]})          # duplicate pronoun
        self.dropped({**CONJ, "forms": CONJ["forms"] + [["nosotros", ""]]})
        self.dropped({**CONJ, "forms": CONJ["forms"] + [["vosotros"]]})
        self.dropped({**CONJ, "verb": ""})
        self.dropped({**CONJ, "lang": None})


class ScriptMatch(Both, unittest.TestCase):
    def test_kept(self):
        s = self.kept(SCRIPT)
        self.assertEqual(s["lang"], "ja")                                            # default for the script
        self.assertEqual(self.kept({**SCRIPT, "script": "cyrillic", "lang": "uk",
                                    "pairs": [["А", "a"], ["Б", "b"], ["В", "v"], ["Г", "h"]]})["lang"], "uk")

    def test_dropped(self):
        self.dropped({**SCRIPT, "script": "latin"})
        self.dropped({**SCRIPT, "pairs": SCRIPT["pairs"][:3]})
        self.dropped({**SCRIPT, "pairs": SCRIPT["pairs"] + [["お", "a"]]})           # duplicate romanization
        self.dropped({**SCRIPT, "pairs": SCRIPT["pairs"] + [["お"]]})
        self.dropped({**SCRIPT, "pairs": [[f"g{i}", f"r{i}"] for i in range(11)]})


class Module(unittest.TestCase):
    def test_every_normalizer_has_a_docstring_and_the_lang_regex_matches_the_server(self):
        self.assertEqual(set(px.NORMALIZERS), {"story", "dialogue", "conjugate", "script_match"})
        for fn in px.NORMALIZERS.values():
            self.assertTrue((fn.__doc__ or "").strip())
        self.assertEqual(px.LANG_RE.pattern, server.LANG_RE.pattern)

    def test_alphabet_tables_are_small_and_cover_every_script(self):
        src = (ROOT / "src/components/language/alphabets.js").read_text(encoding="utf-8")
        tables = dict(re.findall(r"(\w+): \{[^}]*data: '([^']*)'", src))
        self.assertEqual(set(tables), set(px.SCRIPTS))
        for name, data in tables.items():
            self.assertLess(len(data.encode("utf-8")), 3000, name)
            entries = [e.split("=") for e in data.split(" ")]
            self.assertTrue(all(len(e) in (2, 3) and e[0] and e[1] for e in entries), name)


class Helpers(unittest.TestCase):
    def test_parse_vocab_csv(self):
        rows = mx.parse_vocab_csv('word,meaning,ipa\ncafé,coffee,/kaˈfe/\n\n"pan, blanco",white bread\nagua,water,\nsolo\ncafé,again\n')
        self.assertEqual(rows, [{"word": "café", "meaning": "coffee", "ipa": "kaˈfe"},
                                {"word": "pan, blanco", "meaning": "white bread"}, {"word": "agua", "meaning": "water"}])
        self.assertEqual(mx.parse_vocab_csv(""), [])
        self.assertEqual(mx.vocab_cards(rows[:1], "es"), [{"front": "café", "back": "coffee  /kaˈfe/", "lang": "es"}])

    def test_flashcards_to_translate(self):
        cards = [{"front": "café", "back": "coffee  /kaˈfe/", "lang": "es"}, {"front": "pan", "back": "bread [pan] ·"},
                 {"front": "café", "back": "duplicate"}, {"front": "", "back": "x"}]
        items = mx.translate_items(cards, "es")
        self.assertEqual([(i["answer"], i["source"], i["lang"]) for i in items], [("café", "coffee", "es"), ("pan", "bread", "es")])
        self.assertEqual(len(server.normalize_practice(items)), 2)

    def test_minimal_pairs_and_dictation_survive_the_server(self):
        items = mx.minimal_pair_items("en", [["ship", "sheep"], ["bit", "beat"], ["x"]]) + mx.dictation_items("en", ["I see a ship.", " "])
        self.assertEqual([i["audio_text"] for i in items], ["ship", "beat", "I see a ship."])
        self.assertEqual([p["type"] for p in server.normalize_practice(items)], ["listen_choose", "listen_choose", "listen_type"])


class McpTools(unittest.TestCase):
    NAMES = ("add_story", "add_dialogue", "add_conjugation", "add_script_drill", "add_minimal_pairs", "add_dictation",
             "import_vocab_csv", "translate_drill_from_flashcards", "roleplay_turn")

    def tools(self, fake):
        return {n: fn for n, _, _, fn in mx.tools(fake, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR)}

    def test_listed_once_with_schemas(self):
        listed = mx.tools(lambda *a: None, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR)
        self.assertEqual(tuple(n for n, *_ in listed), self.NAMES)
        names = [t["name"] for t in mcp_server.handle({"method": "tools/list", "id": 1})["tools"]]
        for n in self.NAMES:
            self.assertEqual(names.count(n), 1, n)

    def test_tool_calls_build_items_the_server_keeps(self):
        sent = []
        fake = lambda method, path, body=None: sent.append((method, path, body)) or (
            {"flashcards": [{"front": "hola", "back": "hello", "lang": "es"}]} if method == "GET" else {"ok": True})
        t = self.tools(fake)
        t["add_story"]({"topic_id": "t", **{k: STORY[k] for k in ("title", "lang", "lines", "questions")}})
        t["add_dialogue"]({"topic_id": "t", **{k: DIALOGUE[k] for k in ("persona", "setting", "goal", "lang")}})
        t["add_conjugation"]({"topic_id": "t", **{k: CONJ[k] for k in ("verb", "tense", "lang", "forms")}})
        t["add_script_drill"]({"topic_id": "t", "script": "hiragana", "pairs": SCRIPT["pairs"]})
        t["add_minimal_pairs"]({"topic_id": "t", "lang": "en", "pairs": [["ship", "sheep"]]})
        t["add_dictation"]({"topic_id": "t", "lang": "en", "sentences": ["Hello there."]})
        t["translate_drill_from_flashcards"]({"topic_id": "t"})
        posts = [b for m, p, b in sent if m == "POST" and p == "/api/topics/t/practice"]
        items = [i for b in posts for i in b["items"]]
        self.assertTrue(all(i.get("prompt") for i in items))
        self.assertEqual([p["type"] for p in server.normalize_practice(items)],
                         ["story", "dialogue", "conjugate", "script_match", "listen_choose", "listen_type", "translate"])
        t["import_vocab_csv"]({"topic_id": "t", "lang": "es", "csv_text": "gato,cat"})
        self.assertEqual(sent[-1], ("POST", "/api/topics/t/flashcards", {"items": [{"front": "gato", "back": "cat", "lang": "es"}]}))
        t["roleplay_turn"]({"topic_id": "t", "persona": "a baker", "message": "Hola", "lang": "es"})
        m, p, body = sent[-1]
        self.assertEqual((m, p, body["topicId"], body["user_message"], body["target_lang"], body["lang"]),
                         ("POST", "/api/language/roleplay", "t", "Hola", "es", "es"))

    def test_items_reach_a_lesson_through_the_practice_endpoint(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/topics", json=topic("lang-extra"))
            c.post("/api/topics/lang-extra/practice", json={"items": [{"prompt": "p", **STORY}, {"prompt": "p", **CONJ},
                                                                     {"prompt": "p", **{**SCRIPT, "script": "latin"}}]})
            kinds = [p["type"] for p in c.get("/api/topics/lang-extra").json()["practice"]]
        self.assertEqual(kinds, ["story", "conjugate"])

    def test_roleplay_body_works_with_the_endpoint_offline(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/topics", json=topic("lang-roleplay"))
            r = c.post("/api/language/roleplay", json=mx.roleplay_body({"topic_id": "lang-roleplay", "persona": "a baker",
                                                                         "setting": "a bakery", "lang": "es", "message": ""}))
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertTrue(data["reply"])
        self.assertTrue(data.get("fallback"))


if __name__ == "__main__":
    unittest.main()
