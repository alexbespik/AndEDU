"""Philosophy dialogue: GET /api/philosophy/figures and POST /api/philosophy/dialogue. The model is mocked (and
tests/offline_guard.py blocks the network anyway); quotation text must always come from the quote bank."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import LOCAL, TestClient, server, topic  # noqa: E402
import db  # noqa: E402
import philosophy_dialogue  # noqa: E402


def quote(qid, author, text, **extra):
    return {"id": qid, "author": author, "work": "On Things", "ref": "1.1", "translator": "A. Translator", "year": 1900,
            "text": text, "partial": True, "tags": [], "source_url": "https://example.org/x", "pd": True, **extra}


def write_bank(folder: Path, name: str, quotes: list):
    (folder / f"{name}.json").write_text(json.dumps({"version": 1, "collection": name, "quotes": quotes}), encoding="utf-8")


class FakeModel:
    def __init__(self, text):
        self.text, self.calls = text, []

    async def __call__(self, contents=None, role=None, **kwargs):
        self.calls.append({"contents": contents, "role": role, **kwargs})
        return SimpleNamespace(text=self.text)


class Dialogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.client = TestClient(server.app, base_url=LOCAL)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        write_bank(self.dir, "stoic", [quote("ep-1", "Epictetus", "Some things are in our control and others not."),
                                       quote("ma-1", "Marcus Aurelius", "You have power over your mind, not outside events.")])
        write_bank(self.dir, "extra", [quote("ma-2", "Marcus Aurelius", "The impediment to action advances action.")])
        patcher = mock.patch.object(server, "QUOTES_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.clear_hits()
        self.addCleanup(self.clear_hits)

    @staticmethod
    def clear_hits():
        for key in [k for k in server._rate_hits if k[0] == "dialogue"]:
            server._rate_hits.pop(key, None)

    def ask(self, reply, **body):
        model = FakeModel(reply if isinstance(reply, str) else json.dumps(reply))
        with mock.patch.object(server, "acall_gemini", model):
            r = self.client.post("/api/philosophy/dialogue", json={"figure": "marcus-aurelius", "message": "How do I stay calm?", **body})
        return r, model

    # ---- figures
    def test_figures_come_from_the_banks(self):
        r = self.client.get("/api/philosophy/figures")
        self.assertEqual(r.status_code, 200)
        figs = {f["id"]: f for f in r.json()}
        self.assertEqual(set(figs), {"epictetus", "marcus-aurelius"})
        marcus = figs["marcus-aurelius"]
        self.assertEqual(set(marcus), {"id", "name", "era", "collection", "quote_count"})
        self.assertEqual(marcus["name"], "Marcus Aurelius")
        self.assertEqual(marcus["quote_count"], 2)
        self.assertEqual(sorted(marcus["collection"]), ["extra", "stoic"])
        self.assertIsInstance(marcus["collection"], list)
        self.assertTrue(marcus["era"])

    def test_any_number_of_banks_and_new_files_show_up(self):
        for i in range(5):
            write_bank(self.dir, f"bank{i}", [quote(f"b{i}-1", f"Thinker {i}", "A sentence."), quote(f"b{i}-2", f"Thinker {i}", "Another sentence.")])
        ids = [f["id"] for f in self.client.get("/api/philosophy/figures").json()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("thinker-4", ids)
        write_bank(self.dir, "late", [quote("late-1", "Late Author", "Later.")])
        self.assertIn("late-author", [f["id"] for f in self.client.get("/api/philosophy/figures").json()])

    def test_figure_ids_are_unique_even_for_alike_names(self):
        write_bank(self.dir, "alike", [quote("a1", "J. S. Mill", "One."), quote("a2", "J S Mill", "Two.")])
        ids = [f["id"] for f in self.client.get("/api/philosophy/figures") .json() if f["name"].replace(".", "").replace(" ", "") == "JSMill"]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)

    def test_broken_bank_files_are_skipped(self):
        (self.dir / "junk.json").write_text("{not json", encoding="utf-8")
        write_bank(self.dir, "noauthor", [{"id": "x", "text": "t"}])
        self.assertEqual(len(self.client.get("/api/philosophy/figures").json()), 2)

    def test_the_shipped_banks_make_unique_kebab_ids(self):
        real = Path(server.__file__).parent / "content" / "quotes"
        with mock.patch.object(server, "QUOTES_DIR", real):
            figs = self.client.get("/api/philosophy/figures").json()
        self.assertTrue(figs)
        ids = [f["id"] for f in figs]
        self.assertEqual(len(ids), len(set(ids)))
        for f in figs:
            self.assertRegex(f["id"], r"^[a-z0-9][a-z0-9-]*$")
            self.assertGreaterEqual(f["quote_count"], 1)
            self.assertIsInstance(f["collection"], list)
        self.assertIn("socrates", ids)

    # ---- dialogue
    def test_quote_text_comes_from_the_bank_never_from_the_model(self):
        r, model = self.ask({"reply": "Look to your own judgements. What do you control here?", "quote_id": "ma-1",
                             "quote": "FORGED TEXT", "suggested_questions": ["What is in my control?", "Is calm a duty?", "Why?", "A fourth"]})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(set(body), {"reply", "quote", "suggested_questions"})
        self.assertEqual(body["quote"], {"id": "ma-1", "text": "You have power over your mind, not outside events.", "author": "Marcus Aurelius",
                                         "work": "On Things", "ref": "1.1", "translator": "A. Translator", "source_url": "https://example.org/x"})
        self.assertNotIn("FORGED", json.dumps(body))
        self.assertEqual(len(body["suggested_questions"]), 3)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(model.calls[0]["role"], "lesson")

    def test_an_id_outside_the_figures_list_is_ignored(self):
        for qid in ("ep-1", "nope", 5, None):
            r, _ = self.ask({"reply": "Hm.", "quote_id": qid})
            self.assertEqual(r.status_code, 200)
            self.assertIsNone(r.json()["quote"], qid)

    def test_plain_text_reply_is_still_an_answer(self):
        r, _ = self.ask("I would ask you first what is yours to decide.")
        self.assertEqual(r.json()["reply"], "I would ask you first what is yours to decide.")
        self.assertIsNone(r.json()["quote"])
        self.assertEqual(r.json()["suggested_questions"], [])

    def test_unknown_figure_is_422_and_costs_nothing(self):
        model = FakeModel("{}")
        with mock.patch.object(server, "acall_gemini", model):
            r = self.client.post("/api/philosophy/dialogue", json={"figure": "somebody-alive", "message": "hi"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(model.calls, [])

    def test_prompt_fences_data_lists_allowed_quotes_and_states_the_rules(self):
        _, model = self.ask({"reply": "ok"}, history=[{"role": "user", "content": "Hello"}, {"role": "model", "content": "Greetings."}])
        system = model.calls[0]["config"].system_instruction
        self.assertIn(server.DATA_NOTICE, system)
        self.assertRegex(system, r"<<<FIGURE\n?.*Marcus Aurelius")
        self.assertIn("ma-1:", system)
        self.assertIn("ma-2:", system)
        self.assertNotIn("ep-1", system, "another figure's quotations are not offered")
        self.assertIn("AI portrayal", system)
        self.assertIn("Return only this JSON", system)
        for i, part in enumerate(system.split("\n")):
            if part.startswith("Rules:"):
                self.assertLess(i, system.split("\n").index(next(l for l in system.split("\n") if l.startswith("The quotations you may"))))
        self.assertEqual(len(model.calls[0]["contents"]), 3)  # two history turns and the new message

    def test_quote_list_is_capped_and_ranked_by_the_question(self):
        write_bank(self.dir, "big", [quote(f"big-{i}", "Big Author", f"Filler words number {i} here.") for i in range(40)]
                   + [quote("big-key", "Big Author", "Courage means acting rightly despite the fear.")])
        r, model = self.ask({"reply": "ok"}, figure="big-author", message="What is courage?")
        self.assertEqual(r.status_code, 200)
        system = model.calls[0]["config"].system_instruction
        listed = re.findall(r"^(big-[a-z0-9]+):", system, re.M)
        self.assertEqual(len(listed), 20)
        self.assertIn("big-key", listed)

    def test_topic_context_follows_the_visibility_rule(self):
        self.client.post("/api/topics", json=topic("dialogue-lesson", summary="About the Stoics", markdownContent="# Stoics\n\nControl."))
        _, model = self.ask({"reply": "ok"}, topicId="dialogue-lesson")
        self.assertIn("Stoics", model.calls[0]["config"].system_instruction)
        r, _ = self.ask({"reply": "ok"}, topicId="no-such-lesson")
        self.assertEqual(r.status_code, 404)

    def test_rate_limit_entry_exists_and_applies(self):
        self.assertEqual(server.RATE_LIMITS["dialogue"], 120)
        with mock.patch.dict(server.RATE_LIMITS, {"dialogue": 1}):
            first, _ = self.ask({"reply": "one"})
            second, _ = self.ask({"reply": "two"})
        self.assertEqual((first.status_code, second.status_code), (200, 429))

    def test_the_call_goes_through_acall_gemini_so_the_budget_counts(self):
        # acall_gemini -> call_gemini is where SCIEDU_DAILY_MODEL_CALLS is counted; with no key the offline stub answers 503
        with mock.patch.object(server, "call_gemini", side_effect=RuntimeError("no key")) as call:
            r = self.client.post("/api/philosophy/dialogue", json={"figure": "epictetus", "message": "hi"})
        self.assertEqual(r.status_code, 503)
        self.assertEqual(call.call_count, 1)


class DialogueHelpers(unittest.TestCase):
    def test_slug_and_reply_reading(self):
        self.assertEqual(philosophy_dialogue.slug("Marcus Aurelius"), "marcus-aurelius")
        self.assertEqual(philosophy_dialogue.slug("  J. S. Mill! "), "j-s-mill")
        allowed = {"q1": {"id": "q1", "text": "T", "author": "A", "work": "W", "ref": "1", "translator": "X", "source_url": "https://e.org"}}
        self.assertEqual(philosophy_dialogue.read_reply({"reply": " hi ", "quote_id": "q1"}, allowed)["quote"]["text"], "T")
        self.assertIsNone(philosophy_dialogue.read_reply({"reply": "hi", "quote_id": "q2"}, allowed)["quote"])
        self.assertEqual(philosophy_dialogue.read_reply(["junk"], allowed)["suggested_questions"], [])


if __name__ == "__main__":
    unittest.main()
