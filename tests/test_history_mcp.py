"""Tests for History and Language MCP tools and their backend endpoints.
Offline: shares test_lab's temporary data folder and its offline Gemini stub."""
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401

import mcp_server
import mcp_tools_history
import mcp_tools_language


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    import db
    import advisor
    import engage
    db.init_db()
    advisor.init()
    engage.init()


def tearDownModule():
    pass


class HistoryMcpToolsTests(unittest.TestCase):
    def test_tools_registered(self):
        names = {t[0]: t for t in mcp_server.TOOLS}
        for n in (
            "start_historical_crisis",
            "add_crisis_scenario",
            "open_primary_source",
            "add_primary_source_lab",
            "start_timeline_challenge",
            "get_historical_context",
            "add_historical_flashcards",
            "add_history_timeline_events",
            "add_history_quiz",
            "add_history_practice",
            "create_history_topic",
            "open_history_tab",
            "start_history_quiz",
            "start_flashcard_review",
            "list_history_topics",
            "start_roleplay",
            "explain_answer",
            "start_language_practice",
        ):
            self.assertIn(n, names)
            self.assertEqual(names[n][2]["type"], "object")

    def test_history_tool_calls_build_valid_requests(self):
        sent = []
        fake = lambda method, path, body=None: sent.append((method, path, body)) or (
            [{"id": "french-rev", "title": "French Rev", "category": "History", "workspace": "history", "crisis": {"id": "c1"}, "primarySources": [{"id": "s1"}], "timeline": [{"year": 1789}], "flashcards": [{"front": "a", "back": "b"}], "quiz": [{"question": "q"}]}]
            if method == "GET" and path == "/api/topics"
            else {"ok": True}
        )
        tools = {
            n: fn
            for n, _, _, fn in mcp_tools_history.tools(
                fake, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR
            )
        }

        # 1. start_historical_crisis
        tools["start_historical_crisis"]({"crisis_id": "cuban-missile-crisis"})
        self.assertEqual(
            sent[-1][2],
            {
                "type": "SWITCH_STUDIO_MODE",
                "payload": {"mode": "history", "tab": "crisis", "crisisId": "cuban-missile-crisis"},
            },
        )

        # 2. add_crisis_scenario
        tools["add_crisis_scenario"]({
            "topic_id": "cold-war",
            "scenario": {
                "id": "berlin-blockade",
                "title": "Berlin Blockade",
                "role": "Truman",
                "options": [],
            },
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics/cold-war/crisis")
        self.assertEqual(sent[-1][2]["scenario"]["id"], "berlin-blockade")

        # 3. open_primary_source
        tools["open_primary_source"]({"doc_id": "magna-carta-1215"})
        self.assertEqual(
            sent[-1][2],
            {
                "type": "SWITCH_STUDIO_MODE",
                "payload": {"mode": "history", "tab": "sources", "docId": "magna-carta-1215"},
            },
        )

        # 4. add_primary_source_lab
        tools["add_primary_source_lab"]({
            "topic_id": "medieval-england",
            "source": {
                "id": "magna-carta",
                "title": "Magna Carta",
                "author": "Barons",
                "text": "Clause 39",
            },
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics/medieval-england/primary-source")
        self.assertEqual(sent[-1][2]["source"]["id"], "magna-carta")

        # 5. start_timeline_challenge
        tools["start_timeline_challenge"]({})
        self.assertEqual(
            sent[-1][2],
            {
                "type": "SWITCH_STUDIO_MODE",
                "payload": {"mode": "history", "tab": "timeline", "challenge": True},
            },
        )

        # 6. get_historical_context
        tools["get_historical_context"]({"topic_id": "cold-war"})
        self.assertEqual(sent[-1][0], "GET")
        self.assertEqual(sent[-1][1], "/api/topics/cold-war")

        # 7. add_historical_flashcards
        tools["add_historical_flashcards"]({
            "topic_id": "cold-war",
            "items": [{"front": "1962", "back": "Cuban Missile Crisis"}],
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics/cold-war/flashcards")
        self.assertEqual(sent[-1][2]["items"][0]["front"], "1962")

        # 8. add_history_timeline_events
        tools["add_history_timeline_events"]({
            "topic_id": "cold-war",
            "events": [{"year": 1962, "title": "Cuban Missile Crisis"}],
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics/cold-war/timeline")
        self.assertEqual(sent[-1][2]["events"][0]["year"], 1962)

        # 9. add_history_quiz
        tools["add_history_quiz"]({
            "topic_id": "cold-war",
            "questions": [{
                "id": "q1",
                "question": "When was the crisis?",
                "options": ["1962", "1972"],
                "correctAnswer": 0,
            }],
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics/cold-war/quiz")
        self.assertEqual(sent[-1][2]["questions"][0]["id"], "q1")

        # 10. add_history_practice
        tools["add_history_practice"]({
            "topic_id": "cold-war",
            "items": [{"type": "true_false", "prompt": "JFK was president", "answer": True}],
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics/cold-war/practice")

        # 11. create_history_topic
        tools["create_history_topic"]({
            "title": "Ancient Greece",
            "category": "Ancient History",
            "summary": "The cradle of Western civilization.",
            "content": "# Ancient Greece\n\nAthens and Sparta.",
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/topics")
        self.assertEqual(sent[-1][2]["id"], "ancient-greece")
        self.assertEqual(sent[-1][2]["workspace"], "history")

        # 12. open_history_tab
        tools["open_history_tab"]({"tab": "sources"})
        self.assertEqual(
            sent[-1][2],
            {"type": "SWITCH_STUDIO_MODE", "payload": {"mode": "history", "tab": "sources"}},
        )

        # 13. start_history_quiz
        tools["start_history_quiz"]({"topic_id": "cold-war"})
        self.assertEqual(
            sent[-1][2],
            {"type": "SWITCH_TOPIC", "payload": {"topicId": "cold-war", "tab": "speed"}},
        )

        # 14. start_flashcard_review
        tools["start_flashcard_review"]({"topic_id": "cold-war"})
        self.assertEqual(
            sent[-1][2],
            {"type": "SWITCH_TOPIC", "payload": {"topicId": "cold-war", "tab": "cards"}},
        )

        # 15. list_history_topics
        hist_topics = tools["list_history_topics"]({})
        self.assertEqual(len(hist_topics), 1)
        self.assertEqual(hist_topics[0]["id"], "french-rev")
        self.assertTrue(hist_topics[0]["has_crisis"])
        self.assertTrue(hist_topics[0]["has_sources"])
        self.assertEqual(hist_topics[0]["timeline_events"], 1)

    def test_language_new_tools(self):
        sent = []
        fake = lambda method, path, body=None: sent.append((method, path, body)) or {"ok": True}
        tools = {
            n: fn
            for n, _, _, fn in mcp_tools_language.tools(
                fake, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR
            )
        }

        # start_roleplay
        tools["start_roleplay"]({"scenario": "At the Market"})
        self.assertEqual(
            sent[-1][2],
            {
                "type": "SWITCH_STUDIO_MODE",
                "payload": {"mode": "language", "tab": "roleplay", "scenario": "At the Market"},
            },
        )

        # explain_answer
        tools["explain_answer"]({
            "question": "Translate: apple",
            "student_answer": "la pomme",
            "correct_answer": "une pomme",
            "context": "An apple",
            "lang": "fr",
        })
        self.assertEqual(sent[-1][0], "POST")
        self.assertEqual(sent[-1][1], "/api/tutor/explain-answer")
        self.assertEqual(sent[-1][2]["student_answer"], "la pomme")

        # start_language_practice
        tools["start_language_practice"]({"mode": "speak"})
        self.assertEqual(
            sent[-1][2],
            {
                "type": "SWITCH_STUDIO_MODE",
                "payload": {"mode": "language", "tab": "practice", "sessionMode": "speak", "unitId": None},
            },
        )


class HistoryEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server.app, base_url=LOCAL)
        self.client.post("/api/topics", json=topic("hist-topic-1", title="Cold War History"))

    def test_attach_crisis_scenario(self):
        # Initial GET before crisis attached
        get_init = self.client.get("/api/topics/hist-topic-1/crisis")
        self.assertEqual(get_init.status_code, 200)

        res = self.client.post("/api/topics/hist-topic-1/crisis", json={
            "scenario": {
                "id": "cuban-missile",
                "title": "Cuban Missile Crisis",
                "role": "JFK",
            }
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertTrue(res.json()["ok"])
        get_res = self.client.get("/api/topics/hist-topic-1").json()
        self.assertEqual(get_res.get("crisis", {}).get("id"), "cuban-missile")

        # GET /api/topics/{id}/crisis endpoint returns the scenario
        get_crisis = self.client.get("/api/topics/hist-topic-1/crisis")
        self.assertEqual(get_crisis.status_code, 200)
        self.assertEqual(get_crisis.json().get("id"), "cuban-missile")

        # Invalid scenario without id or title must return 422
        bad_res = self.client.post("/api/topics/hist-topic-1/crisis", json={"scenario": "not-a-dict"})
        self.assertEqual(bad_res.status_code, 422)

        # 404 on nonexistent topic
        self.assertEqual(self.client.get("/api/topics/no-such-topic/crisis").status_code, 404)

    def test_attach_primary_source(self):
        # Initial GET before source attached
        get_init = self.client.get("/api/topics/hist-topic-1/primary-source")
        self.assertEqual(get_init.status_code, 200)
        self.assertEqual(get_init.json(), [])

        res = self.client.post("/api/topics/hist-topic-1/primary-source", json={
            "source": {
                "id": "magna-carta",
                "title": "Magna Carta",
                "text": "Clause 39 text",
            }
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertTrue(res.json()["ok"])
        get_res = self.client.get("/api/topics/hist-topic-1").json()
        self.assertEqual(get_res.get("primary_source", {}).get("id"), "magna-carta")
        self.assertIn("primarySources", get_res)

        # GET /api/topics/{id}/primary-source endpoint returns the source list
        get_source = self.client.get("/api/topics/hist-topic-1/primary-source")
        self.assertEqual(get_source.status_code, 200)
        self.assertEqual(len(get_source.json()), 1)
        self.assertEqual(get_source.json()[0]["id"], "magna-carta")

        # Invalid primary source without title must return 422
        bad_res = self.client.post("/api/topics/hist-topic-1/primary-source", json={"source": {"id": "no-title"}})
        self.assertEqual(bad_res.status_code, 422)

        # 404 on nonexistent topic
        self.assertEqual(self.client.get("/api/topics/no-such-topic/primary-source").status_code, 404)

    def test_subresource_endpoints(self):
        # Timeline: POST with {"events": [...]} and GET
        res_tl = self.client.post("/api/topics/hist-topic-1/timeline", json={
            "events": [{"year": 1945, "title": "Yalta Conference"}],
        })
        self.assertEqual(res_tl.status_code, 200)
        self.assertEqual(res_tl.json()["added"], 1)

        get_tl = self.client.get("/api/topics/hist-topic-1/timeline")
        self.assertEqual(get_tl.status_code, 200)
        self.assertEqual(len(get_tl.json()), 1)
        self.assertEqual(get_tl.json()[0]["year"], 1945)

        # Flashcards: POST with {"items": [...]} and GET
        res_fc = self.client.post("/api/topics/hist-topic-1/flashcards", json={
            "items": [{"front": "Iron Curtain", "back": "Churchill's 1946 speech"}],
        })
        self.assertEqual(res_fc.status_code, 200)
        self.assertEqual(res_fc.json()["added"], 1)

        get_fc = self.client.get("/api/topics/hist-topic-1/flashcards")
        self.assertEqual(get_fc.status_code, 200)
        self.assertEqual(len(get_fc.json()), 1)

        # Quiz: POST with {"questions": [...]} and GET
        res_qz = self.client.post("/api/topics/hist-topic-1/quiz", json={
            "questions": [{
                "question": "Which treaty created NATO?",
                "options": ["North Atlantic Treaty", "Warsaw Pact"],
                "correctAnswer": 0,
            }],
        })
        self.assertEqual(res_qz.status_code, 200)
        self.assertEqual(res_qz.json()["added"], 1)

        get_qz = self.client.get("/api/topics/hist-topic-1/quiz")
        self.assertEqual(get_qz.status_code, 200)
        self.assertGreaterEqual(len(get_qz.json()), 1)

        # Practice: POST with {"items": [...]} and GET
        res_pr = self.client.post("/api/topics/hist-topic-1/practice", json={
            "items": [{
                "type": "true_false",
                "prompt": "NATO was formed in 1949",
                "answer": True,
            }],
        })
        self.assertEqual(res_pr.status_code, 200)
        self.assertEqual(res_pr.json()["added"], 1)

        get_pr = self.client.get("/api/topics/hist-topic-1/practice")
        self.assertEqual(get_pr.status_code, 200)
        self.assertGreaterEqual(len(get_pr.json()), 1)

    def test_advisor_sections_endpoint_with_query(self):
        import advisor
        sections = [
            {"school": "wm", "term": "202420", "term_name": "Fall 2024", "crn": "90101",
             "code": "CSCI 141", "section": "01", "title": "Intro CS",
             "instructor": "John Doe", "meets": "MWF 10-10:50a", "credits": "4"},
            {"school": "wm", "term": "202620", "term_name": "Spring 2026", "crn": "90202",
             "code": "MATH 211", "section": "01", "title": "Linear Algebra",
             "instructor": "Jane Smith", "meets": "TR 11-12:20p", "credits": "3"},
            {"school": "wm", "term": "202420", "term_name": "Fall 2024", "crn": "90303",
             "code": "HIST 150", "section": "01", "title": "American History",
             "instructor": "Alice Johnson", "meets": "MWF 1-1:50p", "credits": "4"},
        ]
        advisor.upsert_sections(sections)

        # 1. Department code prefix (case-insensitive: "csci")
        res_dept = self.client.get("/api/advisor/sections?q=csci&limit=20")
        self.assertEqual(res_dept.status_code, 200)
        csci_codes = [s["code"] for s in res_dept.json()["sections"]]
        self.assertTrue(all(c.startswith("CSCI") for c in csci_codes))
        self.assertIn("CSCI 141", csci_codes)

        # 2. Term name substring without spaces ("Fall2024") and with space ("fall 2024")
        res_term1 = self.client.get("/api/advisor/sections?q=Fall2024")
        self.assertEqual(res_term1.status_code, 200)
        terms1 = [s["term_name"] for s in res_term1.json()["sections"]]
        self.assertTrue(all(t == "Fall 2024" for t in terms1))
        self.assertIn("Fall 2024", terms1)

        res_term2 = self.client.get("/api/advisor/sections?q=fall%202024")
        self.assertEqual(res_term2.status_code, 200)
        terms2 = [s["term_name"] for s in res_term2.json()["sections"]]
        self.assertTrue(all(t == "Fall 2024" for t in terms2))

        # 3. Instructor name substring (case-insensitive: "smith")
        res_inst = self.client.get("/api/advisor/sections?q=smith")
        self.assertEqual(res_inst.status_code, 200)
        insts = [s["instructor"] for s in res_inst.json()["sections"]]
        self.assertTrue(all("Smith" in inst for inst in insts))
        self.assertIn("Jane Smith", insts)

        # 4. Limit parameter: default 50, custom limit 1, max clamp 200
        res_lim1 = self.client.get("/api/advisor/sections?q=Fall2024&limit=1")
        self.assertEqual(res_lim1.status_code, 200)
        self.assertEqual(len(res_lim1.json()["sections"]), 1)

        res_default = self.client.get("/api/advisor/sections")
        self.assertEqual(res_default.status_code, 200)
        self.assertLessEqual(len(res_default.json()["sections"]), 50)

    def test_practice_and_flashcards_mutation_endpoints(self):
        # Setup topic with practice items and flashcards
        tid = "hist-topic-1"
        self.client.post(f"/api/topics/{tid}/practice", json={
            "items": [
                {"type": "true_false", "prompt": "Question 1", "answer": True},
                {"type": "true_false", "prompt": "Question 2", "answer": False},
            ]
        })
        self.client.post(f"/api/topics/{tid}/flashcards", json={
            "items": [
                {"front": "Card 1", "back": "Back 1"},
                {"front": "Card 2", "back": "Back 2"},
            ]
        })

        # PUT /api/topics/{id}/practice/{item_id}
        put_res = self.client.put(f"/api/topics/{tid}/practice/p1", json={
            "item": {"type": "true_false", "prompt": "Updated Question 1", "answer": False}
        })
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.json()["after"]["prompt"], "Updated Question 1")
        self.assertEqual(put_res.json()["after"]["id"], "p1")

        # DELETE /api/topics/{id}/practice/{item_id}
        del_p_res = self.client.delete(f"/api/topics/{tid}/practice/p1")
        self.assertEqual(del_p_res.status_code, 200)
        self.assertEqual(del_p_res.json()["removed"]["id"], "p1")

        # DELETE 404 for removed item
        self.assertEqual(self.client.delete(f"/api/topics/{tid}/practice/p1").status_code, 404)

        # DELETE /api/topics/{id}/flashcards/{index}
        del_fc_res = self.client.delete(f"/api/topics/{tid}/flashcards/0")
        self.assertEqual(del_fc_res.status_code, 200)
        self.assertEqual(del_fc_res.json()["removed"]["front"], "Card 1")

        # DELETE 404 for out-of-range index
        self.assertEqual(self.client.delete(f"/api/topics/{tid}/flashcards/99").status_code, 404)


if __name__ == "__main__":
    unittest.main()
