"""SimSpec geometry: segment dashed/arrow, dimension offset, wall hatch, wedge angle."""
import unittest

import simspec


def clean(bodies=None, elements=None):
    spec = {"kind": "geometry", "params": [{"name": "theta", "min": 0, "max": 90, "value": 30}],
            "bodies": bodies or [], "elements": elements or []}
    out, errors = simspec.validate_spec(spec)
    return out, errors


class GeometryFields(unittest.TestCase):
    def test_segment_keeps_dashed_and_arrow(self):
        out, errors = clean(elements=[{"type": "segment", "x1": 0, "y1": 0, "x2": 2, "y2": 1, "dashed": True, "arrow": True}])
        self.assertEqual(errors, [])
        el = out["elements"][0]
        self.assertTrue(el["dashed"] and el["arrow"])

    def test_dimension_offset_is_capped(self):
        out, errors = clean(elements=[{"type": "dimension", "x1": 0, "y1": 0, "x2": 2, "y2": 0, "offset": 999}])
        self.assertEqual(errors, [])
        self.assertEqual(out["elements"][0]["offset"], 20.0)
        out, _ = clean(elements=[{"type": "dimension", "x1": 0, "y1": 0, "x2": 2, "y2": 0, "offset": "x"}])
        self.assertEqual(out["elements"][0]["offset"], 0.0)

    def test_wall_hatch_bool(self):
        out, errors = clean(bodies=[{"id": "w", "type": "wall", "x1": 0, "y1": 0, "x2": 0, "y2": 3, "hatch": False},
                                    {"id": "s", "type": "surface", "x1": 0, "y1": 0, "x2": 3, "y2": 0}])
        self.assertEqual(errors, [])
        self.assertIs(out["bodies"][0]["hatch"], False)
        self.assertIs(out["bodies"][1]["hatch"], True)

    def test_wedge_angle_number_capped_and_expression_kept(self):
        out, errors = clean(bodies=[{"id": "a", "type": "wedge", "x": 0, "y": 0, "width": 3, "height": 2, "angle": 9000},
                                    {"id": "b", "type": "wedge", "x": 0, "y": 0, "width": 3, "height": 2, "angle": "theta"}])
        self.assertEqual(errors, [])
        self.assertEqual(out["bodies"][0]["angle"], 360.0)
        self.assertEqual(out["bodies"][1]["angle"], "theta")


if __name__ == "__main__":
    unittest.main()
