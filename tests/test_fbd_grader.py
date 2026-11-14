"""
Unit and integration tests for fbd_grader and Gemini Vision drawing checks.
Offline: runs with test_lab harness, zero external network calls.
"""
import base64
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fbd_grader
from test_lab import LOCAL, TestClient, server


class TestFBDGraderMath(unittest.TestCase):
    def test_cartesian_angle(self):
        # In SVG, y increases downwards.
        # Right: dx > 0, dy = 0 => 0 deg
        self.assertAlmostEqual(fbd_grader.cartesian_angle(500, 300, 600, 300), 0.0, places=2)
        # Up: dx = 0, y2 < y1 => dy_math > 0 => 90 deg
        self.assertAlmostEqual(fbd_grader.cartesian_angle(500, 300, 500, 200), 90.0, places=2)
        # Left: x2 < x1, dy = 0 => 180 deg
        self.assertAlmostEqual(fbd_grader.cartesian_angle(500, 300, 400, 300), 180.0, places=2)
        # Down: dx = 0, y2 > y1 => dy_math < 0 => 270 deg
        self.assertAlmostEqual(fbd_grader.cartesian_angle(500, 300, 500, 400), 270.0, places=2)

    def test_angle_diff(self):
        self.assertAlmostEqual(fbd_grader.angle_diff(0, 10), 10.0, places=2)
        self.assertAlmostEqual(fbd_grader.angle_diff(355, 5), 10.0, places=2)
        self.assertAlmostEqual(fbd_grader.angle_diff(270, 90), 180.0, places=2)

    def test_normalize_label(self):
        self.assertEqual(fbd_grader.normalize_label("F_{net}"), "fnet")
        self.assertEqual(fbd_grader.normalize_label("$\\vec{N}$"), "n")
        self.assertEqual(fbd_grader.normalize_label("m \\cdot g"), "mg")


class TestFBDGraderLogic(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "body_origin": [500.0, 300.0],
            "origin_tol_px": 40.0,
            "targets": [
                {"name": "gravity", "aliases": ["mg", "w", "fg"], "angle_deg": 270.0, "angle_tol_deg": 5.0, "required": True},
                {"name": "normal", "aliases": ["n", "fn"], "angle_deg": 90.0, "angle_tol_deg": 5.0, "required": True}
            ],
            "magnitude_comparisons": [
                {"vector_a": "normal", "op": "eq", "vector_b": "gravity", "ratio_tol": 0.25}
            ],
            "forbidden_forces": ["centrifugal", "ma", "motion"]
        }

    def test_perfect_horizontal_fbd(self):
        shapes = [
            {"id": 1, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 420},  # Down: gravity (120px)
            {"id": 2, "type": "text", "x1": 510, "y1": 425, "text": "mg"},
            {"id": 3, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 180},  # Up: normal (120px)
            {"id": 4, "type": "text", "x1": 510, "y1": 175, "text": "N"},
        ]
        res = fbd_grader.grade_fbd(shapes, self.spec)
        self.assertTrue(res["passed"])
        self.assertEqual(res["score"], 1.0)
        self.assertTrue(res["deterministic"])
        self.assertIn("accurately balance", res["feedback"])

    def test_forbidden_force_rejected(self):
        shapes = [
            {"id": 1, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 420},
            {"id": 2, "type": "text", "x1": 510, "y1": 425, "text": "mg"},
            {"id": 3, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 180},
            {"id": 4, "type": "text", "x1": 510, "y1": 175, "text": "N"},
            {"id": 5, "type": "text", "x1": 550, "y1": 300, "text": "F_centrifugal"},  # Forbidden
        ]
        res = fbd_grader.grade_fbd(shapes, self.spec)
        self.assertFalse(res["passed"])
        forb_crit = next((c for c in res["criteria"] if "pseudo-forces" in c["criterion"]), None)
        self.assertIsNotNone(forb_crit)
        self.assertFalse(forb_crit["met"])
        self.assertIn("Forbidden force detected", forb_crit["comment"])

    def test_detached_origin_penalized(self):
        shapes = [
            {"id": 1, "type": "arrow", "x1": 650, "y1": 300, "x2": 650, "y2": 420},  # x1=650 is 150px away from 500
            {"id": 2, "type": "text", "x1": 660, "y1": 425, "text": "mg"},
            {"id": 3, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 180},
            {"id": 4, "type": "text", "x1": 510, "y1": 175, "text": "N"},
        ]
        res = fbd_grader.grade_fbd(shapes, self.spec)
        origin_crit = next((c for c in res["criteria"] if "body center/origin" in c["criterion"]), None)
        self.assertIsNotNone(origin_crit)
        self.assertFalse(origin_crit["met"])

    def test_magnitude_inequality_failure(self):
        shapes = [
            {"id": 1, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 450},  # Down: gravity (150px)
            {"id": 2, "type": "text", "x1": 510, "y1": 455, "text": "mg"},
            {"id": 3, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 260},  # Up: normal (40px, > 25% difference)
            {"id": 4, "type": "text", "x1": 510, "y1": 255, "text": "N"},
        ]
        res = fbd_grader.grade_fbd(shapes, self.spec)
        mag_crit = next((c for c in res["criteria"] if "Relative magnitude" in c["criterion"]), None)
        self.assertIsNotNone(mag_crit)
        self.assertFalse(mag_crit["met"])


class TestServerDrawingEndpoint(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(server.app, base_url=LOCAL)
        self.dummy_png = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82").decode("utf-8")

    def test_models_for_vision(self):
        models = server.models_for("vision")
        self.assertTrue(len(models) > 0)
        self.assertIn("gemini-4-flash", models)
        self.assertIn("gemini-4-vision", models)

    def test_deterministic_api_draw_check(self):
        spec = {
            "body_origin": [500.0, 300.0],
            "origin_tol_px": 40.0,
            "targets": [
                {"name": "gravity", "aliases": ["mg"], "angle_deg": 270.0, "angle_tol_deg": 5.0, "required": True},
                {"name": "normal", "aliases": ["N"], "angle_deg": 90.0, "angle_tol_deg": 5.0, "required": True}
            ],
            "magnitude_comparisons": [
                {"vector_a": "normal", "op": "eq", "vector_b": "gravity", "ratio_tol": 0.25}
            ]
        }
        shapes = [
            {"id": 1, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 400},
            {"id": 2, "type": "text", "x1": 510, "y1": 405, "text": "mg"},
            {"id": 3, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 200},
            {"id": 4, "type": "text", "x1": 510, "y1": 195, "text": "N"},
        ]
        payload = {
            "image": self.dummy_png,
            "prompt": "Draw a block in vertical equilibrium",
            "criteria": ["Gravity downward", "Normal upward"],
            "shapes": shapes,
            "fbd_spec": spec
        }
        # Does not call Gemini: graded deterministically by fbd_grader
        r = self.c.post("/api/draw/check", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data.get("deterministic"))
        self.assertTrue(data.get("passed"))
        self.assertEqual(data.get("score"), 1.0)

    def test_fallback_to_gemini_vision(self):
        seen_role = []

        async def fake_acall(contents, role=None, **kwargs):
            seen_role.append(role)
            return SimpleNamespace(text='{"criteria": [{"criterion": "Nucleus in center", "met": true, "comment": "good"}, {"criterion": "Electron rings", "met": true, "comment": "rings drawn"}], "score": 1.0, "feedback": "Nice job", "describe": "A drawing"}')

        payload = {
            "image": self.dummy_png,
            "prompt": "Draw an atom with electron orbitals",
            "criteria": ["Nucleus in center", "Electron rings"],
            # No shapes or fbd_spec provided: routes to Gemini vision model
        }

        with mock.patch.object(server, "acall_gemini", side_effect=fake_acall):
            r = self.c.post("/api/draw/check", json=payload)
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertTrue(data.get("passed"))
            self.assertEqual(seen_role, ["vision"])

    def test_magnitude_inequality_and_missing_required(self):
        # Normal (up, length 100) vs Gravity (down, length 120)
        # Spec says Normal > Gravity (op: gt), which is FALSE.
        spec = {
            "body_origin": [500, 300],
            "targets": [
                {"name": "gravity", "angle_deg": 270, "required": True},
                {"name": "normal", "angle_deg": 90, "required": True},
            ],
            "magnitude_comparisons": [
                {"vector_a": "normal", "vector_b": "gravity", "op": "gt", "ratio_tol": 0.25}
            ]
        }
        shapes = [
            {"type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 420},  # length 120 down
            {"type": "text", "x1": 510, "y1": 415, "text": "mg"},
            {"type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 200},  # length 100 up
            {"type": "text", "x1": 510, "y1": 195, "text": "N"},
        ]
        res = fbd_grader.grade_fbd(shapes, spec)
        # normal (100) > gravity (120) should be False
        gt_criterion = [c for c in res["criteria"] if "Relative magnitude" in c["criterion"]][0]
        self.assertFalse(gt_criterion["met"])

    def test_malformed_spec_and_unidentified_shapes_tolerance(self):
        # Empty / malformed fields should not raise exceptions
        spec = {
            "body_origin": None,
            "origin_tol_px": "bad_tol",
            "forbidden_forces": [123, None, "centrifugal"],
            "targets": None,
            "magnitude_comparisons": None,
        }
        shapes = [
            {"type": "arrow", "x1": "invalid", "y1": 0},
            {"type": "arrow", "x1": 500, "y1": 310, "x2": 500, "y2": 210},  # no id provided
            {"type": "text", "x1": 500, "y1": 210, "text": 456},
        ]
        res = fbd_grader.grade_fbd(shapes, spec)
        self.assertIsInstance(res, dict)
        self.assertIn("score", res)
        self.assertFalse(res["passed"])  # targets is empty, so passed is False


if __name__ == "__main__":
    unittest.main()
