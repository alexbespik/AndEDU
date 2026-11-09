"""Tests for mcp_tools_studio.py and the three practice/flashcard sub-resource endpoints in server.py.
Offline: uses test_lab's temporary data directory and client."""
import json
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401

import mcp_server
import mcp_tools_studio


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    pass


class StudioPureParsing(unittest.TestCase):
    def test_parse_glossary_colons_and_dashes(self):
        text = """
        # Chapter 1 Glossary
        Photosynthesis: Process by which plants produce glucose
        Gravity - Fundamental force of attraction
        First-order logic — Formal system of quantification
        ATP – Cellular energy currency
        * Mitochondria: Powerhouse of the cell
        - Ribosome - Protein synthesis factory
        Invalid line with no separator
        """
        cards = mcp_tools_studio.parse_glossary(text, lang="en")
        self.assertEqual(len(cards), 6)
        fronts = [c["front"] for c in cards]
        self.assertIn("Photosynthesis", fronts)
        self.assertIn("Gravity", fronts)
        self.assertIn("First-order logic", fronts)
        self.assertIn("ATP", fronts)
        self.assertIn("Mitochondria", fronts)
        self.assertIn("Ribosome", fronts)
        for c in cards:
            self.assertEqual(c["lang"], "en")
            self.assertTrue(len(c["back"]) > 0)

    def test_parse_glossary_deduplication(self):
        text = "Gravity: Force A\ngravity: Force B"
        cards = mcp_tools_studio.parse_glossary(text)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["back"], "Force A")

    def test_parse_timeline_text(self):
        text = """
        1789 - Storming of the Bastille | Key French Revolution event
        44 BCE - Assassination of Caesar
        44 BC - Death of Julius Caesar
        330 CE - Byzantium becomes Constantinople
        1066 AD - Battle of Hastings
        -500 - Classical Greece beginnings
        44 B.C.E. - Fall of the Roman Republic
        Not a timeline event
        """
        events = mcp_tools_studio.parse_timeline_text(text)
        self.assertEqual(len(events), 7)
        by_title = {e["title"]: e for e in events}

        self.assertEqual(by_title["Storming of the Bastille"]["year"], 1789)
        self.assertEqual(by_title["Storming of the Bastille"]["detail"], "Key French Revolution event")

        self.assertEqual(by_title["Assassination of Caesar"]["year"], -44)
        self.assertEqual(by_title["Death of Julius Caesar"]["year"], -44)
        self.assertEqual(by_title["Byzantium becomes Constantinople"]["year"], 330)
        self.assertEqual(by_title["Battle of Hastings"]["year"], 1066)
        self.assertEqual(by_title["Classical Greece beginnings"]["year"], -500)
        self.assertEqual(by_title["Fall of the Roman Republic"]["year"], -44)

    def test_quiz_from_flashcards_logic(self):
        cards = [
            {"front": f"Concept {i}", "back": f"Definition {i}", "hint": f"Hint {i}"}
            for i in range(6)
        ]
        quiz = mcp_tools_studio.build_quiz_from_flashcards(cards, count=4, seed=42)
        self.assertEqual(len(quiz), 4)
        for i, q in enumerate(quiz):
            self.assertEqual(q["id"], f"qff-{i}")
            self.assertTrue(q["question"].startswith("What does 'Concept"))
            self.assertEqual(len(q["options"]), 4)
            self.assertIn(q["correctAnswer"], [0, 1, 2, 3])
            # The chosen correctAnswer must match the right definition
            selected_option = q["options"][q["correctAnswer"]]
            self.assertIn("Definition", selected_option)
            self.assertIn(selected_option, q["explanation"])

    def test_quiz_from_flashcards_insufficient_cards(self):
        # Needs at least 2 distinct backs
        self.assertEqual(mcp_tools_studio.build_quiz_from_flashcards([]), [])
        self.assertEqual(mcp_tools_studio.build_quiz_from_flashcards([{"front": "A", "back": "Same"}]), [])
        self.assertEqual(mcp_tools_studio.build_quiz_from_flashcards([
            {"front": "A", "back": "Same"},
            {"front": "B", "back": "Same"}
        ]), [])

    def test_pick_match_pairs(self):
        cards = [{"front": f"F{i}", "back": f"B{i}"} for i in range(10)]
        pairs = mcp_tools_studio.pick_match_pairs(cards, count=5)
        self.assertEqual(len(pairs), 5)
        self.assertEqual(pairs[0], ["F0", "B0"])
        # If under 3 pairs, returns empty list
        self.assertEqual(mcp_tools_studio.pick_match_pairs(cards[:2]), [])

    def test_lint_topic_finds_all_expected_issues(self):
        bad_topic = {
            "id": "lint-test",
            "cheatSheet": [],  # empty cheatSheet
            "quiz": [
                {"id": "q1", "question": "What is energy?", "explanation": ""},  # no explanation
                {"id": "q2", "question": "What is energy?", "explanation": "Capacity to do work."},  # duplicate
                {"id": "q3", "question": "What is momentum?", "explanation": "p = mv",
                 "check": {"verdict": "ambiguous"}},  # dubious answer check
            ],
            "practice": [
                {"id": "p1", "type": "fill_blank", "prompt": "Fill in"},  # no hint or explanation
            ]
        }
        res = mcp_tools_studio.lint_topic(bad_topic)
        self.assertFalse(res["ok"])
        issues = res["issues"]
        issue_types = [i["issue"] for i in issues]

        self.assertTrue(any("no explanation" in s for s in issue_types))
        self.assertTrue(any("duplicate" in s for s in issue_types))
        self.assertTrue(any("no hint" in s for s in issue_types))
        self.assertTrue(any("empty" in s for s in issue_types))
        self.assertTrue(any("answer check: ambiguous" in s for s in issue_types))

    def test_lint_topic_clean_topic(self):
        clean_topic = {
            "id": "clean-test",
            "cheatSheet": [{"label": "F", "formula": "ma"}],
            "quiz": [
                {"id": "q1", "question": "What is force?", "explanation": "F = ma",
                 "check": {"verdict": "verified"}},
            ],
            "practice": [
                {"id": "p1", "type": "fill_blank", "prompt": "Fill in", "hint": "Think about Newton", "explanation": "F=ma"},
            ]
        }
        res = mcp_tools_studio.lint_topic(clean_topic)
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["issues"]), 0)


class StudioMcpTools(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.orig_call = mcp_server.call

        def fake_call(method, path, body=None):
            self.calls.append((method, path, body))
            if method == "GET" and "/api/topics/" in path and not path.endswith("/api/topics/"):
                tid = path.split("/api/topics/")[1].split("?")[0]
                return {
                    "id": tid, "title": "Test Topic",
                    "flashcards": [{"front": f"Term {i}", "back": f"Def {i}"} for i in range(5)],
                    "practice": [{"id": f"p{i}", "type": "fill_blank", "prompt": f"P{i}"} for i in range(3)],
                    "timeline": [{"year": 1900 + i, "title": f"Event {i}"} for i in range(3)],
                    "quiz": [{"id": "q1", "question": "Question 1", "explanation": "Explanation 1"}],
                    "cheatSheet": [{"label": "F", "formula": "ma"}]
                }
            if method == "GET" and path == "/api/topics":
                return [
                    {"id": "topic-1", "title": "Calculus I", "summary": "Limits and derivatives", "workspace": "math"},
                    {"id": "topic-2", "title": "French Revolution", "summary": "1789 events", "workspace": "history"}
                ]
            if method == "GET" and "/api/courses/" in path:
                cid = path.split("/api/courses/")[1]
                return {
                    "id": cid, "title": "Course Title", "status": "active", "workspace": "math",
                    "classes": [
                        {"seq": 1, "title": "Class 1", "status": "ready", "score": 0.85, "topic_id": "topic-1"}
                    ]
                }
            if method == "GET" and "/api/users/" in path and path.endswith("/courses"):
                return {"courses": [{"id": "course-1", "title": "Course 1"}]}
            if method == "GET" and "/api/engage/" in path:
                return {"totalXp": 120, "xpToday": 30, "streak": 5, "dailyGoal": 20, "level": {"level": 2}, "badges": []}
            if method == "GET" and "/api/review/" in path:
                return {"questions": [{"topicId": "t1", "questionId": "q1", "question": "What is X?"}], "nextReview": "tomorrow"}
            if method == "POST" and path == "/api/agy/events":
                return {"status": "ok", "event": body}
            return {"status": "ok", "added": 1}

        mcp_server.call = fake_call
        self.tool_map = {n: fn for n, _, _, fn in mcp_tools_studio.tools(
            fake_call, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR
        )}

    def tearDown(self):
        mcp_server.call = self.orig_call

    def test_all_16_tools_present(self):
        expected_tools = [
            "quiz_from_flashcards", "flashcards_from_glossary", "match_pairs_from_flashcards",
            "timeline_from_text", "copy_activities", "topic_stats", "lint_topic",
            "search_topics", "course_outline", "student_dashboard", "review_queue",
            "open_workspace", "daily_challenge", "remove_practice_item", "replace_practice_item",
            "remove_flashcard"
        ]
        for name in expected_tools:
            self.assertIn(name, self.tool_map)

    def test_quiz_from_flashcards_tool(self):
        res = self.tool_map["quiz_from_flashcards"]({"topic_id": "test-topic", "count": 3})
        self.assertEqual(res["status"], "ok")
        # Ensure POST /api/topics/test-topic/quiz was called
        post_calls = [c for c in self.calls if c[0] == "POST" and "/quiz" in c[1]]
        self.assertEqual(len(post_calls), 1)

    def test_flashcards_from_glossary_tool(self):
        res = self.tool_map["flashcards_from_glossary"]({
            "topic_id": "test-topic",
            "text": "Cell: Basic unit of life\nDNA - Genetic blueprint",
            "lang": "en"
        })
        self.assertEqual(res["status"], "ok")
        post_calls = [c for c in self.calls if c[0] == "POST" and "/flashcards" in c[1]]
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(len(post_calls[0][2]["items"]), 2)

    def test_match_pairs_from_flashcards_tool(self):
        res = self.tool_map["match_pairs_from_flashcards"]({"topic_id": "test-topic", "count": 4})
        self.assertEqual(res["status"], "ok")
        post_calls = [c for c in self.calls if c[0] == "POST" and "/practice" in c[1]]
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(post_calls[0][2]["items"][0]["type"], "match_pairs")

    def test_timeline_from_text_tool(self):
        res = self.tool_map["timeline_from_text"]({
            "topic_id": "test-topic",
            "text": "1969 - Moon landing\n1989 - Fall of Berlin Wall"
        })
        self.assertEqual(res["status"], "ok")
        post_calls = [c for c in self.calls if c[0] == "POST" and "/timeline" in c[1]]
        self.assertEqual(len(post_calls), 1)
        self.assertEqual(len(post_calls[0][2]["items"]), 2)

    def test_copy_activities_tool(self):
        res = self.tool_map["copy_activities"]({
            "from_topic": "src-topic",
            "to_topic": "dest-topic",
            "kinds": ["practice", "flashcards"]
        })
        self.assertIn("copied", res)
        post_paths = [c[1] for c in self.calls if c[0] == "POST"]
        self.assertIn("/api/topics/dest-topic/practice", post_paths)
        self.assertIn("/api/topics/dest-topic/flashcards", post_paths)

    def test_search_topics_tool(self):
        res = self.tool_map["search_topics"]({"query": "calculus", "workspace": "math"})
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "topic-1")

    def test_open_workspace_tool(self):
        res = self.tool_map["open_workspace"]({"mode": "history", "tab": "timeline"})
        self.assertIn("opened", res.get("status", ""))
        event_calls = [c for c in self.calls if c[1] == "/api/agy/events"]
        self.assertEqual(len(event_calls), 1)
        self.assertEqual(event_calls[0][2]["payload"]["mode"], "history")
        self.assertEqual(event_calls[0][2]["payload"]["tab"], "timeline")

    def test_crud_practice_and_flashcards_tools(self):
        self.tool_map["remove_practice_item"]({"topic_id": "topic-1", "item_id": "p1"})
        del_practice = [c for c in self.calls if c[0] == "DELETE" and "/practice/p1" in c[1]]
        self.assertEqual(len(del_practice), 1)

        self.tool_map["replace_practice_item"]({"topic_id": "topic-1", "item_id": "p1", "item": {"type": "true_false", "answer": True}})
        put_practice = [c for c in self.calls if c[0] == "PUT" and "/practice/p1" in c[1]]
        self.assertEqual(len(put_practice), 1)

        self.tool_map["remove_flashcard"]({"topic_id": "topic-1", "index": 2})
        del_card = [c for c in self.calls if c[0] == "DELETE" and "/flashcards/2" in c[1]]
        self.assertEqual(len(del_card), 1)

    def test_add_drawing_to_notes_tool(self):
        diag = {
            "kind": "geometry",
            "title": "Inclined Plane",
            "bodies": [{"id": "b1", "type": "box", "x": 0, "y": 0, "width": 1, "height": 1}],
            "forces": [{"id": "fg", "magnitude": 9.8, "angle": 270}]
        }
        res = self.tool_map["add_drawing_to_notes"]({"topic_id": "topic-1", "diagram": diag, "caption": "FBD Diagram"})
        self.assertEqual(res["status"], "added")
        post_topics = [c for c in self.calls if c[0] == "POST" and c[1] == "/api/topics"]
        self.assertEqual(len(post_topics), 1)
        self.assertIn("```geometry", post_topics[0][2]["markdownContent"])
        self.assertIn("### FBD Diagram", post_topics[0][2]["markdownContent"])

    def test_preview_geometry_diagram_tool(self):
        diag = {
            "kind": "fbd",
            "bodies": [{"id": "b1", "type": "box", "x": 0, "y": 0, "width": 1, "height": 1}],
            "forces": [{"id": "fg", "magnitude": 9.8, "angle": 270}]
        }
        self.tool_map["preview_geometry_diagram"]({"spec": diag})
        ui_geom = [c for c in self.calls if c[0] == "POST" and c[1] == "/api/ui/geometry"]
        self.assertEqual(len(ui_geom), 1)
        self.assertEqual(ui_geom[0][2]["spec"]["kind"], "fbd")


class ServerEndpoints(unittest.TestCase):
    def setUp(self):
        import db
        db.init_db()
        self.client = TestClient(server.app, base_url=LOCAL)
        self.topic_id = f"test-subres-{uuid.uuid4().hex[:6]}"
        # Seed topic with 2 practice items and 3 flashcards
        test_topic_data = topic(
            self.topic_id,
            practice=[
                {"id": "p1", "type": "fill_blank", "prompt": "Fill blank 1", "options": ["a", "b"], "answer": "a"},
                {"id": "p2", "type": "true_false", "prompt": "Statement 2", "answer": True}
            ],
            flashcards=[
                {"front": "Card 0", "back": "Back 0"},
                {"front": "Card 1", "back": "Back 1"},
                {"front": "Card 2", "back": "Back 2"}
            ]
        )
        r = self.client.post("/api/topics", json=test_topic_data)
        self.assertEqual(r.status_code, 200)

    def test_remove_practice_item_success(self):
        res = self.client.delete(f"/api/topics/{self.topic_id}/practice/p1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["removed"]["id"], "p1")
        self.assertEqual(data["total"], 1)

        # Verify through GET
        t = self.client.get(f"/api/topics/{self.topic_id}").json()
        self.assertEqual(len(t["practice"]), 1)
        self.assertEqual(t["practice"][0]["id"], "p2")

    def test_remove_practice_item_404(self):
        # Unknown item id
        res = self.client.delete(f"/api/topics/{self.topic_id}/practice/p999")
        self.assertEqual(res.status_code, 404)
        # Unknown topic id
        res2 = self.client.delete("/api/topics/non-existent-topic/practice/p1")
        self.assertEqual(res2.status_code, 404)

    def test_replace_practice_item_success(self):
        new_item = {"type": "true_false", "prompt": "Updated statement", "answer": False}
        res = self.client.put(f"/api/topics/{self.topic_id}/practice/p2", json={"item": new_item})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["after"]["id"], "p2")  # ID kept stable
        self.assertEqual(data["after"]["answer"], False)

        # Verify topic
        t = self.client.get(f"/api/topics/{self.topic_id}").json()
        p2 = next(p for p in t["practice"] if p["id"] == "p2")
        self.assertEqual(p2["answer"], False)

    def test_replace_practice_item_404_and_422(self):
        # Unknown item id
        res = self.client.put(f"/api/topics/{self.topic_id}/practice/p999", json={"type": "true_false", "prompt": "P", "answer": True})
        self.assertEqual(res.status_code, 404)

        # Invalid practice item rejected with 422
        res2 = self.client.put(f"/api/topics/{self.topic_id}/practice/p1", json={"type": "unknown_shape_xyz"})
        self.assertEqual(res2.status_code, 422)

    def test_remove_flashcard_success(self):
        res = self.client.delete(f"/api/topics/{self.topic_id}/flashcards/1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["removed"]["front"], "Card 1")
        self.assertEqual(data["total"], 2)

        # Verify topic
        t = self.client.get(f"/api/topics/{self.topic_id}").json()
        fronts = [c["front"] for c in t["flashcards"]]
        self.assertEqual(fronts, ["Card 0", "Card 2"])

    def test_remove_flashcard_404(self):
        # Index out of range
        res = self.client.delete(f"/api/topics/{self.topic_id}/flashcards/99")
        self.assertEqual(res.status_code, 404)
        res_neg = self.client.delete(f"/api/topics/{self.topic_id}/flashcards/-1")
        self.assertEqual(res_neg.status_code, 404)
        # Unknown topic
        res_topic = self.client.delete("/api/topics/non-existent-topic/flashcards/0")
        self.assertEqual(res_topic.status_code, 404)

    def test_preview_geometry_sim_endpoint(self):
        spec = {
            "kind": "geometry",
            "title": "Test Sim",
            "bodies": [{"id": "b1", "type": "box", "x": 0, "y": 0, "width": 1, "height": 1}],
            "forces": [{"id": "f1", "magnitude": 5, "angle": 90}]
        }
        r = self.client.post("/api/ui/geometry", json={"spec": spec})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "shown")
        self.assertEqual(data["spec"]["kind"], "geometry")


class AccountsModeOwnerEndpoints(unittest.TestCase):
    """With SCIEDU_AUTH=1, only topic owners can modify practice items and flashcards."""
    def setUp(self):
        server.AUTH_REQUIRED = True
        server._rate_hits.pop(("auth", "testclient"), None)
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

        def register_user(name):
            r = self.c.post("/api/auth/register", json={"name": name, "password": "password123", "adult": True, "privacy": True}).json()
            return {"Authorization": f"Bearer {r['token']}"}, r["user"]["id"]

        tag = uuid.uuid4().hex[:6]
        self.alice_headers, self.alice_id = register_user(f"Alice {tag}")
        self.bob_headers, self.bob_id = register_user(f"Bob {tag}")

        import db
        course = db.create_course(self.alice_id, "Alice Course", "g", "", [])
        self.topic_id = f"alice-lesson-{tag}"
        server.AUTH_REQUIRED = False
        self.c.post("/api/topics", json=topic(
            self.topic_id,
            source={"courseId": course["id"]},
            practice=[{"id": "p1", "type": "true_false", "prompt": "P1", "answer": True}],
            flashcards=[{"front": "F1", "back": "B1"}]
        ))
        server.AUTH_REQUIRED = True

    def tearDown(self):
        server.AUTH_REQUIRED = False
        self.ctx.__exit__(None, None, None)
        import db
        db.close_all()

    def test_bob_cannot_modify_alice_activities(self):
        # Bob tries to remove Alice's practice item
        r_del_p = self.c.delete(f"/api/topics/{self.topic_id}/practice/p1", headers=self.bob_headers)
        self.assertIn(r_del_p.status_code, (403, 404))

        # Bob tries to replace Alice's practice item
        r_put_p = self.c.put(f"/api/topics/{self.topic_id}/practice/p1", json={"answer": False}, headers=self.bob_headers)
        self.assertIn(r_put_p.status_code, (403, 404))

        # Bob tries to delete Alice's flashcard
        r_del_fc = self.c.delete(f"/api/topics/{self.topic_id}/flashcards/0", headers=self.bob_headers)
        self.assertIn(r_del_fc.status_code, (403, 404))

    def test_alice_can_modify_her_own_activities(self):
        # Alice replaces practice item
        r_put = self.c.put(f"/api/topics/{self.topic_id}/practice/p1", json={"answer": False}, headers=self.alice_headers)
        self.assertEqual(r_put.status_code, 200)

        # Alice deletes flashcard
        r_del_fc = self.c.delete(f"/api/topics/{self.topic_id}/flashcards/0", headers=self.alice_headers)
        self.assertEqual(r_del_fc.status_code, 200)

        # Alice deletes practice item
        r_del_p = self.c.delete(f"/api/topics/{self.topic_id}/practice/p1", headers=self.alice_headers)
        self.assertEqual(r_del_p.status_code, 200)


class McpServerRegistration(unittest.TestCase):
    def test_all_studio_tools_registered_in_mcp_server(self):
        resp = mcp_server.handle({"method": "tools/list", "id": 1})
        self.assertIsNotNone(resp)
        tools = {t["name"]: t for t in resp["tools"]}
        expected = [
            "quiz_from_flashcards", "flashcards_from_glossary", "match_pairs_from_flashcards",
            "timeline_from_text", "copy_activities", "topic_stats", "lint_topic",
            "search_topics", "course_outline", "student_dashboard", "review_queue",
            "open_workspace", "daily_challenge", "remove_practice_item", "replace_practice_item",
            "remove_flashcard", "add_drawing_to_notes", "preview_geometry_diagram"
        ]
        for name in expected:
            self.assertIn(name, tools)
            self.assertEqual(tools[name]["inputSchema"]["type"], "object")


if __name__ == "__main__":
    unittest.main()
