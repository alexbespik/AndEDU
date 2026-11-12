"""The offline quote bank (content/quotes/*.json): the loading screens show only these, never generated text."""
import json
import re
import unittest
from pathlib import Path

QUOTES_DIR = Path(__file__).resolve().parent.parent / "content" / "quotes"
FIELDS = {"id", "author", "work", "ref", "translator", "year", "text", "partial", "tags", "source_url", "pd"}


class QuoteBank(unittest.TestCase):
    def banks(self):
        files = sorted(QUOTES_DIR.glob("*.json"))
        self.assertTrue(files, "no quote banks")
        return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in files}

    def test_fields_and_ids(self):
        ids = set()
        for name, bank in self.banks().items():
            self.assertEqual(bank["collection"], name)
            self.assertTrue(bank["quotes"])
            for q in bank["quotes"]:
                self.assertEqual(set(q), FIELDS, q.get("id"))
                self.assertRegex(q["id"], r"^[a-z0-9][a-z0-9-]*$")
                self.assertNotIn(q["id"], ids, "ids must be unique across banks")
                ids.add(q["id"])
                self.assertTrue(q["text"].strip() and q["author"] and q["work"] and q["ref"] and q["translator"])
                self.assertLessEqual(len(q["text"]), 200, q["id"])
                self.assertTrue(q["source_url"].startswith("https://"), q["id"])
                self.assertIs(q["pd"], True, q["id"])
                self.assertIsInstance(q["partial"], bool)
                self.assertIsInstance(q["tags"], list)
                self.assertIsInstance(q["year"], int)

    def test_no_markup(self):
        for bank in self.banks().values():
            for q in bank["quotes"]:
                self.assertIsNone(re.search(r"[<>]|https?:|\$", q["text"]), q["id"])

    def test_loading_screens_have_quotes(self):
        usable = [q for b in self.banks().values() for q in b["quotes"] if "no-loading" not in q["tags"]]
        self.assertGreaterEqual(len(usable), 10)


if __name__ == "__main__":
    unittest.main()
