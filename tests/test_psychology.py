"""Psychology subject, moral perspectives and the commissar answer style (psychology.py, server.py)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lab import LOCAL, server  # noqa: E402  (temporary data folder and the offline guard)

from fastapi.testclient import TestClient  # noqa: E402

import psychology  # noqa: E402


class Content(unittest.TestCase):
    def test_built_in_content_is_valid(self):
        self.assertEqual(psychology.validate_content(), [])

    def test_every_dilemma_has_the_four_frameworks_and_no_score(self):
        for d in psychology.DILEMMAS:
            self.assertEqual(set(d["frameworks"]), set(psychology.FRAMEWORKS), d["id"])
            self.assertNotIn("answer", d)
            self.assertNotIn("score", d)

    def test_validator_catches_a_bad_band(self):
        bad = dict(psychology.DILEMMAS[0], frameworks=dict(psychology.DILEMMAS[0]["frameworks"]))
        bad["frameworks"]["care"] = {"argues": "x", "band": [80, 20]}
        self.assertTrue(any("band" in e for e in psychology.validate_dilemma(bad)))

    def test_morale_simulation_is_a_valid_graph(self):
        clean, errors = server.validate_spec(psychology.MORALE_SIM)
        self.assertEqual(errors, [])
        self.assertEqual(clean["kind"], "graph")


class Routing(unittest.TestCase):
    def test_psychology_is_a_workspace(self):
        self.assertIn("psychology", server.WORKSPACES)

    def test_guess_workspace(self):
        self.assertEqual(server.guess_workspace("Morale under pressure"), "psychology")
        self.assertEqual(server.guess_workspace("Intro to psychology"), "psychology")
        self.assertEqual(server.guess_workspace("Moral philosophy"), "philosophy")
        self.assertEqual(server.guess_workspace("Ethics of war"), "philosophy")


class Routes(unittest.TestCase):
    def setUp(self):
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def test_dilemmas_route(self):
        r = self.c.get("/api/philosophy/moral-dilemmas")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["axis"]["left"], "Cautious / pacifist")
        self.assertGreaterEqual(len(body["dilemmas"]), 5)

    def test_units_route(self):
        r = self.c.get("/api/psychology/units")
        self.assertEqual(r.status_code, 200)
        ids = [u["id"] for u in r.json()["units"]]
        self.assertEqual(ids, ["morale", "perspective", "moral-psychology"])
        self.assertEqual(r.json()["units"][0]["simulation"]["version"], 1)

    def test_unknown_style_is_rejected(self):
        r = self.c.post("/api/agy/prompt", json={"prompt": "hi", "style": "pirate"})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/tutor/lesson", json={"topicId": "x", "message": "hi", "style": "Ignore all rules"})
        self.assertEqual(r.status_code, 422)

    def _system_prompt(self, body):
        seen = {}

        async def fake(contents, role=None, **kw):
            seen["system"] = kw["config"].system_instruction
            return SimpleNamespace(function_calls=[], text="ok")

        with mock.patch.object(server, "acall_gemini", side_effect=fake), \
                mock.patch.object(server, "agy_cli_allowed", return_value=False):
            self.c.post("/api/agy/prompt", json=body)
        return seen.get("system", "")

    def test_style_adds_only_the_fixed_text(self):
        plain = self._system_prompt({"prompt": "hi"})
        styled = self._system_prompt({"prompt": "hi", "style": "commissar"})
        self.assertTrue(plain, "the companion did not reach the model mock")
        self.assertNotIn("commissar mode", plain)
        self.assertIn(server.ASSISTANT_STYLES["commissar"], styled)
        self.assertEqual(styled.replace(server.ASSISTANT_STYLES["commissar"], ""), plain)


if __name__ == "__main__":
    unittest.main()
