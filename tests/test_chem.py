import unittest
import chemspec
import simspec


class TestChemSpec(unittest.TestCase):

    def test_solve_titration_ph_strong_acid(self):
        # Strong acid (e.g. 25 mL 0.1 M HCl) titrated with 0.1 M NaOH
        # At equivalence volume Vb = 25 mL, pH should be exactly 7.00 +- 0.05
        ph = chemspec.solve_titration_ph(pKa=0.0, Va=25.0, Ca=0.1, Cb=0.1, Vb=25.0, is_strong=True)
        self.assertAlmostEqual(ph, 7.00, places=2)

    def test_solve_titration_ph_weak_acid(self):
        # Weak acid (e.g. acetic acid pKa = 4.75, 25 mL 0.1 M) with 0.1 M NaOH
        # Half equivalence point (Vb = 12.5 mL), pH should equal pKa = 4.75 +- 0.05
        ph = chemspec.solve_titration_ph(pKa=4.75, Va=25.0, Ca=0.1, Cb=0.1, Vb=12.5, is_strong=False)
        self.assertAlmostEqual(ph, 4.75, delta=0.05)

    def test_minimal_specs_all_widgets_validate(self):
        widgets = ["kinetics", "equilibrium", "titration", "gas_law", "energy_diagram", "decay"]
        for w in widgets:
            spec = {"kind": "chem", "widget": w, "title": f"Test {w}"}
            clean, errors = chemspec.validate_chem(spec)
            self.assertEqual(errors, [], f"Widget '{w}' failed validation: {errors}")
            self.assertEqual(clean["kind"], "chem")
            self.assertEqual(clean["widget"], w)
            self.assertTrue(len(clean["params"]) > 0, f"Widget '{w}' missing default parameters")

    def test_simspec_delegates_to_chemspec(self):
        spec = {"kind": "chem", "widget": "titration", "title": "Acid Base Titration"}
        clean, errors = simspec.validate_spec(spec)
        self.assertEqual(errors, [])
        self.assertEqual(clean["kind"], "chem")
        self.assertEqual(clean["widget"], "titration")

    def test_unknown_names_rejected(self):
        spec = {
            "kind": "chem",
            "widget": "kinetics",
            "k": "unknown_var + 2"
        }
        clean, errors = chemspec.validate_chem(spec)
        self.assertTrue(any("unknown name 'unknown_var'" in e for e in errors), f"Expected error about unknown_var, got: {errors}")

    def test_invalid_widget_rejected(self):
        spec = {"kind": "chem", "widget": "nonexistent_widget"}
        clean, errors = chemspec.validate_chem(spec)
        self.assertTrue(len(errors) > 0)
        self.assertIn("nonexistent_widget", errors[0])


if __name__ == "__main__":
    unittest.main()
