"""
Unit tests for Philosophy practice normalizers (practice_philosophy.py),
logic endpoints (server.py: /api/logic/guide, /api/logic/grade),
workspace guessing priority, and philosophy MCP tools (mcp_tools_philosophy.py).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from test_lab import LOCAL, TestClient, server

import mcp_tools_philosophy
import practice_philosophy


class TestPhilosophyPractice(unittest.TestCase):
    def setUp(self):
        self.base = {
            "id": "p1",
            "type": "",
            "prompt": "Test prompt",
            "explanation": "Test explanation",
            "concept": None,
        }

    # ---- 1. truth_table ----
    def test_truth_table_normalizer_computes_deterministic_rows(self):
        fn = practice_philosophy.NORMALIZERS["truth_table"]
        # Model gives bogus answer field; normalizer strips it and computes real truth table
        item = fn({"formulas": ["P -> Q", "~P | Q"], "bogus_answer": [True, False]}, self.base)
        self.assertIsNotNone(item)
        self.assertEqual(item["letters"], ["P", "Q"])
        self.assertEqual(len(item["rows"]), 4)
        # For P=T, Q=T: P->Q is T, ~P|Q is T
        self.assertEqual(item["rows"][0]["values"], [True, True])
        # For P=T, Q=F: P->Q is F, ~P|Q is F
        self.assertEqual(item["rows"][1]["values"], [False, False])
        self.assertNotIn("bogus_answer", item)

    def test_truth_table_normalizer_drops_invalid(self):
        fn = practice_philosophy.NORMALIZERS["truth_table"]
        # Syntax error
        self.assertIsNone(fn({"formulas": ["P -> & Q"]}, self.base))
        # More than 4 variables
        self.assertIsNone(fn({"formulas": ["P & Q & R & S & T"]}, self.base))
        # No variables
        self.assertIsNone(fn({"formulas": []}, self.base))

    # ---- 2. validity ----
    def test_validity_normalizer_evaluates_argument(self):
        fn = practice_philosophy.NORMALIZERS["validity"]
        # Modus Ponens: Valid
        valid_item = fn({"premises": ["P -> Q", "P"], "conclusion": "Q"}, self.base)
        self.assertIsNotNone(valid_item)
        self.assertTrue(valid_item["valid"])
        self.assertIsNone(valid_item["counterexample"])

        # Affirming the Consequent: Invalid
        invalid_item = fn({"premises": ["P -> Q", "Q"], "conclusion": "P"}, self.base)
        self.assertIsNotNone(invalid_item)
        self.assertFalse(invalid_item["valid"])
        self.assertEqual(invalid_item["counterexample"], {"P": False, "Q": True})

    def test_validity_normalizer_drops_invalid(self):
        fn = practice_philosophy.NORMALIZERS["validity"]
        self.assertIsNone(fn({"premises": [], "conclusion": "P"}, self.base))
        self.assertIsNone(fn({"premises": ["P"], "conclusion": ""}, self.base))
        self.assertIsNone(fn({"premises": ["P &"], "conclusion": "P"}, self.base))

    # ---- 3. syllogism ----
    def test_syllogism_normalizer_form_and_statements(self):
        fn = practice_philosophy.NORMALIZERS["syllogism"]
        # Valid form AAA-1 (Barbara)
        syl = fn({"form": "AAA-1"}, self.base)
        self.assertIsNotNone(syl)
        self.assertEqual(syl["name"], "Barbara")
        self.assertTrue(syl["valid"])
        self.assertEqual(syl["violations"], [])

        # Statement-based syllogism
        statements_syl = fn({
            "major": {"type": "A", "subject": "mammals", "predicate": "animals"},
            "minor": {"type": "A", "subject": "dogs", "predicate": "mammals"},
            "conclusion": {"type": "A", "subject": "dogs", "predicate": "animals"},
        }, self.base)
        self.assertIsNotNone(statements_syl)
        self.assertEqual(statements_syl["name"], "Barbara")
        self.assertTrue(statements_syl["valid"])

        # Invalid form with rule violations (AAA-2: undistributed middle)
        broken = fn({"form": "AAA-2"}, self.base)
        self.assertIsNotNone(broken)
        self.assertFalse(broken["valid"])
        self.assertTrue(any(v["rule"] == "undistributed_middle" for v in broken["violations"]))

    # ---- 4. proof_steps ----
    def test_proof_steps_normalizer(self):
        fn = practice_philosophy.NORMALIZERS["proof_steps"]
        # Simple proof of Q from P and P -> Q
        lines = [
            {"formula": "P", "rule": "PR", "cites": [], "depth": 0},
            {"formula": "P -> Q", "rule": "PR", "cites": [], "depth": 0},
            {"formula": "Q", "rule": "->E", "cites": [1, 2], "depth": 0},
        ]
        item = fn({"premises": ["P", "P -> Q"], "goal": "Q", "lines": lines}, self.base)
        self.assertIsNotNone(item)
        self.assertTrue(item["proven"])
        self.assertEqual(len(item["verdicts"]), 3)

    # ---- 5. argument_map ----
    def test_argument_map_normalizer(self):
        fn = practice_philosophy.NORMALIZERS["argument_map"]
        map_data = {
            "claims": [
                {"id": "c1", "text": "Premise A", "role": "premise"},
                {"id": "c2", "text": "Conclusion B", "role": "conclusion"},
            ],
            "edges": [{"from": ["c1"], "to": "c2", "type": "supports"}],
            "main": "c2",
        }
        item = fn({"map": map_data}, self.base)
        self.assertIsNotNone(item)
        self.assertEqual(item["map"]["main"], "c2")
        self.assertIn("findings", item)

    # ---- 6. spot_parts ----
    def test_spot_parts_normalizer(self):
        fn = practice_philosophy.NORMALIZERS["spot_parts"]
        item = fn({
            "text": "All humans are mortal. Socrates is human. Therefore, Socrates is mortal.",
            "target": "Identify the conclusion",
            "options": ["All humans are mortal", "Socrates is human", "Socrates is mortal"],
            "answer": "Socrates is mortal",
        }, self.base)
        self.assertIsNotNone(item)
        self.assertEqual(item["answer"], "Socrates is mortal")
        self.assertEqual(len(item["options"]), 3)

    # ---- 7. fallacy_id ----
    def test_fallacy_id_normalizer(self):
        fn = practice_philosophy.NORMALIZERS["fallacy_id"]
        item = fn({
            "argument": "You cannot trust his argument on taxation because he is wealthy.",
            "options": ["Ad Hominem", "Straw Man", "False Dilemma", "Slippery Slope"],
            "answer": "Ad Hominem",
            "fallacy_type": "informal",
            "why": "Attacks the speaker rather than addressing the substance of the argument.",
        }, self.base)
        self.assertIsNotNone(item)
        self.assertEqual(item["answer"], "Ad Hominem")
        self.assertEqual(item["fallacy_type"], "informal")


class TestLogicServerEndpoints(unittest.TestCase):
    def setUp(self):
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.client = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def test_logic_guide_endpoint(self):
        res = self.client.get("/api/logic/guide")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("guide", data)
        self.assertIn("ops", data)
        self.assertIn("practice", data)
        self.assertIn("truth_table", data["practice"])
        self.assertIn("syllogism", data["practice"])
        self.assertIn("validity", data["practice"])

    def test_logic_grade_endpoint(self):
        # Grade validity deterministically
        res = self.client.post("/api/logic/grade", json={
            "op": "validity",
            "premises": ["P -> Q", "P"],
            "conclusion": "Q",
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["result"]["valid"])

        # Grade syllogism deterministically
        res_syl = self.client.post("/api/logic/grade", json={
            "op": "syllogism",
            "form": "AAA-1",
        })
        self.assertEqual(res_syl.status_code, 200)
        syl_data = res_syl.json()
        self.assertTrue(syl_data["ok"])
        self.assertEqual(syl_data["result"]["name"], "Barbara")
        self.assertTrue(syl_data["result"]["valid"])

    def test_workspace_guessing_philosophy_priority(self):
        # Stoic ethics must resolve to philosophy
        self.assertEqual(server.guess_workspace("Stoic Ethics and Virtue"), "philosophy")
        self.assertEqual(server.guess_workspace("Epistemology and Truth"), "philosophy")
        self.assertEqual(server.guess_workspace("Kant's Moral Philosophy"), "philosophy")
        # Stoichiometry must resolve to lab (chemistry), not philosophy!
        self.assertEqual(server.guess_workspace("Stoichiometry and Chemical Equations"), "lab")
        # Python still takes priority for code
        self.assertEqual(server.guess_workspace("Python for Ethics Research"), "code")


class TestPhilosophyMCPTools(unittest.TestCase):
    def test_unit_creation_offline(self):
        unit = mcp_tools_philosophy.philosophy_unit_topic({
            "title": "Categorical Logic and Syllogisms",
            "summary": "Introduction to categorical propositions and traditional syllogistic forms.",
            "exercises": [
                {"type": "syllogism", "form": "AAA-1", "prompt": "Evaluate Barbara"},
                {"type": "truth_table", "formulas": ["P -> Q"], "prompt": "Complete table"},
            ],
            "flashcards": [
                {"front": "Major Term", "back": "The predicate of the conclusion."},
                {"front": "Minor Term", "back": "The subject of the conclusion."},
            ],
        })
        self.assertEqual(unit["workspace"], "philosophy")
        self.assertEqual(len(unit["practice"]), 2)
        self.assertEqual(unit["practice"][0]["type"], "syllogism")
        self.assertEqual(unit["practice"][0]["name"], "Barbara")
        self.assertEqual(len(unit["flashcards"]), 2)


if __name__ == "__main__":
    unittest.main()
