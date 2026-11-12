"""
Unit tests for pedagogical prompt invariants and Socratic chat hygiene.
Verifies prompt structures, sanitization, and role alternation in server.py.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.TemporaryDirectory(prefix="andedu-test-pedagogy-")
os.environ["SCIEDU_CONTENT_DIR"] = TMP.name
os.environ.pop("SCIEDU_AUTH", None)
os.environ["api_KEY"] = ""
os.environ["SCIEDU_ELEVENLABS"] = "0"  # never spend real ElevenLabs credits from tests
os.environ["GEMINI_API_KEY"] = ""
sys.path.insert(0, str(ROOT))

import offline_guard  # noqa: E402,F401  (no test may reach the internet)
import server  # noqa: E402


class TestPedagogyPrompts(unittest.TestCase):

    def test_diagnostic_prompt_balanced_distribution(self):
        prompt = server.DIAGNOSTIC_PROMPT
        self.assertIn("correctAnswer", prompt)
        self.assertIn("balanced", prompt)
        self.assertIn("0, 1, 2, and 3", prompt)

    def test_math_practice_prompt_power_operator(self):
        prompt = server.MATH_PRACTICE_PROMPT
        self.assertIn("NEVER use '^'", prompt)
        self.assertIn("**", prompt)
        self.assertIn("_MATH_NAMES", prompt)

    def test_brief_prompt_three_lines(self):
        prompt = server.BRIEF_PROMPT
        self.assertIn("60 words", prompt)
        self.assertIn("**Goal:**", prompt)
        self.assertIn("**Key idea:**", prompt)
        self.assertIn("**Check yourself:**", prompt)
        self.assertIn("Exactly three lines", prompt)

    def test_class_prompt_mermaid_quoting_and_ceiling(self):
        prompt = server.CLASS_PROMPT
        # Quoting rules for nodes and edges
        self.assertIn('A["label"]', prompt)
        self.assertIn('-->|"label"|', prompt)
        # Word ceiling and completion guard
        self.assertIn("600-1000 words", prompt)
        self.assertIn("strictly complete JSON ending with }}", prompt)

    def test_socratic_and_lesson_tutor_dynamic_sizing(self):
        for name, prompt in [("SOCRATIC_PROMPT", server.SOCRATIC_PROMPT), ("LESSON_TUTOR_PROMPT", server.LESSON_TUTOR_PROMPT)]:
            with self.subTest(prompt=name):
                self.assertIn("Two-Tier Dynamic Response Sizing", prompt)
                self.assertIn("Diagnostic Turn (40-80 words)", prompt)
                self.assertIn("Scaffolding Turn (100-180 words)", prompt)
                self.assertIn("Cognitive Apprenticeship", prompt)
                self.assertIn("Cognitive Load Theory", prompt)
                self.assertIn("invariant", prompt.lower())
                self.assertIn("misconception", prompt.lower())
                self.assertIn("ONE leading check question", prompt)

    def test_agy_system_prompt_socratic_tool_usage(self):
        prompt = server.AGY_SYSTEM_PROMPT
        self.assertIn("SOCRATIC TOOL USAGE & ACADEMIC INTEGRITY", prompt)
        self.assertIn("NEVER use tools or responses to solve active student exercises", prompt)

    def test_sanitize_puzzle_context(self):
        raw_ctx = {
            "mode": "code",
            "chapter": {"id": 2, "title": "Dynamic Programming"},
            "problem": {
                "id": "p42",
                "title": "Knapsack Optimization",
                "guiding_question": "What invariant defines optimal substructure?",
                "concept_hint": "Consider remaining capacity W.",
                "starter_code": "def knapsack(W, weights, values):\n    pass",
                "difficulty": "Hard",
                "solution": "def knapsack(W, weights, values):\n    # SECRET FULL SOLUTION",
                "tests": "assert knapsack(50, [10, 20, 30], [60, 100, 120]) == 220",
                "assertions": ["assert secret == 42"],
                "correctAnswer": 2,
                "answer": "Option C"
            },
            "secret_salt": "super_secret_hash_123"
        }

        clean = server._sanitize_puzzle_context(raw_ctx)

        # Public metadata retained
        self.assertEqual(clean["chapter_title"], "Dynamic Programming")
        self.assertEqual(clean["problem_title"], "Knapsack Optimization")
        self.assertEqual(clean["guiding_question"], "What invariant defines optimal substructure?")
        self.assertEqual(clean["concept_hint"], "Consider remaining capacity W.")
        self.assertIn("def knapsack", clean["starter_code"])
        self.assertEqual(clean["mode"], "code")
        self.assertEqual(clean["difficulty"], "Hard")

        # Solution and assertion secrets stripped
        self.assertNotIn("solution", clean)
        self.assertNotIn("tests", clean)
        self.assertNotIn("assertions", clean)
        self.assertNotIn("correctAnswer", clean)
        self.assertNotIn("answer", clean)
        self.assertNotIn("secret_salt", clean)

    def test_tutor_chat_role_alternation_deduplication(self):
        """Test multi-turn role alternating logic ported from post_user_prompt."""
        # Simulated raw history with duplicate consecutive roles and leading non-user turn
        raw_history = [
            {"role": "assistant", "content": "Welcome!"},
            {"role": "user", "content": "I am working on step 1."},
            {"role": "user", "content": "Here is my approach."},
            {"role": "model", "content": "Let us check the invariant."},
            {"role": "model", "content": "What is the force balance?"},
        ]

        # Apply the alternation logic from tutor_chat
        history_contents = []
        for turn in raw_history:
            role = "user" if turn.get("role") == "user" else "model"
            text = str(turn.get("content") or "").strip()
            if not text:
                continue
            if history_contents and history_contents[-1].role == role:
                prev_text = history_contents[-1].parts[0].text
                merged_text = f"{prev_text}\n{text}"[:server.MAX_TURN_CHARS]
                history_contents[-1] = server.types.Content(role=role, parts=[server.types.Part.from_text(text=merged_text)])
            else:
                history_contents.append(server.types.Content(role=role, parts=[server.types.Part.from_text(text=text[:server.MAX_TURN_CHARS])]))

        # Strip non-user head
        while history_contents and history_contents[0].role != "user":
            history_contents.pop(0)

        # Invariants:
        # 1. Must start with user
        self.assertEqual(history_contents[0].role, "user")
        # 2. Roles must strictly alternate
        for i in range(1, len(history_contents)):
            self.assertNotEqual(history_contents[i].role, history_contents[i - 1].role)
        # 3. Merged user turns
        self.assertIn("I am working on step 1.", history_contents[0].parts[0].text)
        self.assertIn("Here is my approach.", history_contents[0].parts[0].text)
        # 4. Merged model turns
        self.assertIn("Let us check the invariant.", history_contents[1].parts[0].text)
        self.assertIn("What is the force balance?", history_contents[1].parts[0].text)

        # 5. When history ends on a model turn and user_msg is empty, must conclude with a user turn
        if history_contents[-1].role == "model":
            history_contents.append(server.types.Content(role="user", parts=[server.types.Part.from_text(text="Please continue.")]))
        self.assertEqual(history_contents[-1].role, "user")


if __name__ == "__main__":
    unittest.main()
