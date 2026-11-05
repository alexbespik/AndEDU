"""Fixes from the review of the new practice types: malformed items never raise, ids are matched in full,
and the scripted roleplay partner moves on after the student's first reply. Offline."""
import unittest

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)


class ReviewFixes(unittest.TestCase):
    def test_malformed_story_is_dropped_not_raised(self):
        bad = [{"type": "story", "prompt": "p", "lang": "es", "lines": 5, "questions": 3},
               {"type": "story", "prompt": "p", "lang": "es", "title": "t",
                "lines": [{"speaker": "A", "text": f"l{i}"} for i in range(4)],
                "questions": [{"after": float("nan"), "question": "q", "options": ["a", "b"], "answer": "a"}]}]
        self.assertEqual(server.normalize_practice(bad), [])

    def test_base_fields_are_capped(self):
        out = server.normalize_practice([{"type": "true_false", "prompt": "x" * 9000, "answer": True,
                                          "concept": {"nested": 1}, "id": "i" * 99}])
        self.assertEqual(len(out[0]["prompt"]), 4000)
        self.assertIsNone(out[0]["concept"])
        self.assertEqual(len(out[0]["id"]), 40)

    def test_topic_id_with_trailing_newline_is_rejected(self):
        with self.assertRaises(Exception):
            server.require_topic_id("abc\n")

    def test_fallback_partner_moves_on_after_first_reply(self):
        opening = server._get_roleplay_fallback("cafe", "es", "", [], "A2")["reply"]
        second = server._get_roleplay_fallback("cafe", "es", "Un café, por favor",
                                               [{"role": "model", "content": opening}], "A2")["reply"]
        self.assertNotEqual(opening, second)
        # older clients put the message in history too; that must not skip a line
        old = server._get_roleplay_fallback("cafe", "es", "Un café, por favor",
                                            [{"sender": "ai", "text": opening}, {"sender": "user", "text": "Un café, por favor"}], "A2")["reply"]
        self.assertEqual(second, old)


if __name__ == "__main__":
    unittest.main()
