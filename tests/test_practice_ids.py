"""Practice item ids: unique inside a lesson, never renumbered by a second pass, and new items start after the highest
existing number. Nothing here touches the real content/topics (test_lab points the server at a temp folder)."""
import copy
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import LOCAL, TestClient, server, topic  # noqa: E402
import db  # noqa: E402


def tf(prompt, **extra):
    return {"type": "true_false", "prompt": prompt, "answer": True, **extra}


class UniqueIds(unittest.TestCase):
    def test_duplicates_and_missing_ids_get_the_next_free_number(self):
        items = [tf("a", id="p1"), tf("b", id="p1"), tf("c"), tf("d", id="p2")]
        out = server.unique_practice_ids(items)
        ids = [p["id"] for p in out]
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(ids[0], "p1")
        self.assertEqual(ids[3], "p2")  # a later explicit id is never taken by a renumbered item
        self.assertEqual({ids[1], ids[2]}, {"p3", "p4"})

    def test_second_pass_changes_nothing(self):
        once = server.unique_practice_ids([tf("a", id="p1"), tf("b", id="p1"), tf("c")])
        self.assertEqual(server.unique_practice_ids(copy.deepcopy(once)), once)

    def test_normalize_topic_keeps_every_legacy_item_and_is_idempotent(self):
        legacy_cloze = {"type": "cloze", "prompt": "Fill the gaps", "text": "a ___ b", "gaps": ["x"], "bank": ["x", "y"]}
        data = topic("ids-legacy", practice=[tf("a", id="p1"), tf("b", id="p1"), legacy_cloze, tf("c")])
        first, warnings = server.normalize_topic(data)
        self.assertEqual(len(first["practice"]), 4, "an older item the normalizers cannot read must not be dropped")
        self.assertEqual(warnings, [])
        ids = [p["id"] for p in first["practice"]]
        self.assertEqual(len(set(ids)), 4)
        second, _ = server.normalize_topic(copy.deepcopy(first))
        self.assertEqual(second["practice"], first["practice"])

    def test_next_number_is_one_past_the_highest(self):
        self.assertEqual(server.next_practice_number([]), 1)
        self.assertEqual(server.next_practice_number([{"id": "p1"}, {"id": "p7"}, {"id": "custom"}]), 8)


class AddAfterRemove(unittest.TestCase):
    def setUp(self):
        db.init_db()
        self.client = TestClient(server.app, base_url=LOCAL)
        self.tid = f"ids-{uuid.uuid4().hex[:8]}"
        r = self.client.post("/api/topics", json=topic(self.tid, practice=[tf("one"), tf("two"), tf("three")]))
        self.assertEqual(r.status_code, 200)

    def test_new_items_do_not_reuse_a_removed_number(self):
        self.assertEqual(self.client.delete(f"/api/topics/{self.tid}/practice/p2").status_code, 200)
        r = self.client.post(f"/api/topics/{self.tid}/practice", json={"items": [tf("four")]})
        self.assertEqual(r.json()["added"], 1)
        ids = [p["id"] for p in self.client.get(f"/api/topics/{self.tid}").json()["practice"]]
        self.assertEqual(ids, ["p1", "p3", "p4"])


if __name__ == "__main__":
    unittest.main()
