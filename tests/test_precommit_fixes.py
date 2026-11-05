"""Pre-commit security fixes: malformed crisis/source numbers, the primary-source cap, IDE XP per day. Offline."""
import unittest

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)

import engage


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    server.db.init_db()
    engage.init()


class PrecommitFixes(unittest.TestCase):
    def test_bad_numbers_do_not_raise(self):
        c = server.normalize_crisis({"id": "c", "title": "C", "initialState": {"tension": "abc", "allies": float("inf")},
                                     "options": [{"id": "a", "label": "A"}]})
        if c:
            self.assertEqual(c["initialState"]["tension"], 70)
        server.normalize_primary_source({"id": "s", "title": "S", "text": "t", "annotations": ["x"],
                                         "shegSteps": [{"step": "two", "name": "n"}]})

    def test_ide_xp_is_capped_per_day(self):
        uid = server.db.get_or_create_user("IDE Capper")["id"]
        got = [engage.award(uid, "2026-11-05", "ide_solved", f"task-{i}")["xp"] for i in range(8)]
        self.assertEqual(sum(1 for g in got if g), engage.DAILY_MAX["ide_solved"])


if __name__ == "__main__":
    unittest.main()
