"""Chem titration: polyprotic pKa lists in the solver and the schema."""
import unittest

import chemspec


class Solver(unittest.TestCase):
    def test_diprotic_half_equivalence_points(self):
        pka = [3.0, 8.0]
        # 25 mL of 0.1 M H2A with 0.1 M base: first equivalence at 25 mL
        ph1 = chemspec.solve_titration_ph(pka, 25.0, 0.1, 0.1, 12.5)
        ph2 = chemspec.solve_titration_ph(pka, 25.0, 0.1, 0.1, 37.5)
        self.assertAlmostEqual(ph1, 3.0, delta=0.15)
        self.assertAlmostEqual(ph2, 8.0, delta=0.15)

    def test_monoprotic_number_unchanged(self):
        self.assertAlmostEqual(chemspec.solve_titration_ph(4.75, 25.0, 0.1, 0.1, 12.5), 4.75, delta=0.1)


class Schema(unittest.TestCase):
    def check(self, pka):
        return chemspec.validate_chem({"kind": "chem", "widget": "titration", "pKa": pka})

    def test_accepts_number_and_lists(self):
        for pka in (4.75, [4.2], [2.15, 7.2], [2.15, 7.2, 12.35]):
            clean, errors = self.check(pka)
            self.assertEqual(errors, [], pka)
            self.assertEqual(clean["pKa"], pka)

    def test_rejects_bad_lists(self):
        for pka in ([], [1, 2, 3, 4], [7.2, 2.1], [3, 3], ["a", 5], [True, 5], [99]):
            _, errors = self.check(pka)
            self.assertTrue(errors, pka)


if __name__ == "__main__":
    unittest.main()
