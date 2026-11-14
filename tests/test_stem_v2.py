"""
Unit test suite for STEM V2 upgrades:
- 5 new practice domains (EE, AI, Systems, Stats, Bio)
- Normalizer validation and drop rules
- Deterministic grading and feedback scores
- Secret field redaction
- Sandbox preamble PEP 578 audit hooks
- Polyprotic acid titration bisection solver
"""
import unittest
import math
import chemspec
import practice_ee
import practice_ai
import practice_systems
import practice_stats
import practice_bio
import advisor_rules


class TestStemV2Upgrades(unittest.TestCase):

    def test_chemspec_polyprotic_titration(self):
        # Monoprotic weak acid: acetic acid (pKa = 4.75) at half-equivalence (Vb = 12.5) -> pH ~ 4.75
        ph_half = chemspec.solve_titration_ph(4.75, 25.0, 0.1, 0.1, 12.5)
        self.assertAlmostEqual(ph_half, 4.75, delta=0.05)

        # Monoprotic at equivalence (Vb = 25.0) -> pH > 7.0 (around 8.72)
        ph_eq = chemspec.solve_titration_ph(4.75, 25.0, 0.1, 0.1, 25.0)
        self.assertGreater(ph_eq, 8.0)
        self.assertLess(ph_eq, 9.5)

        # Diprotic acid (pKa1 = 2.0, pKa2 = 6.0) at first equivalence (Vb = 25.0) -> pH ~ (2+6)/2 = 4.0
        ph_diprotic = chemspec.solve_titration_ph([2.0, 6.0], 25.0, 0.1, 0.1, 25.0)
        self.assertAlmostEqual(ph_diprotic, 4.04, delta=0.1)

        # Triprotic acid (phosphoric acid: 2.15, 7.20, 12.35)
        ph_triprotic = chemspec.solve_titration_ph([2.15, 7.20, 12.35], 25.0, 0.1, 0.1, 25.0)
        self.assertAlmostEqual(ph_triprotic, 4.70, delta=0.1)

    def test_practice_ee_circuit_kcl_kvl(self):
        base = {"id": "ee-1", "type": "circuit_kcl_kvl", "prompt": "Find V1", "explanation": "", "concept": "Circuits"}
        norm = practice_ee.NORMALIZERS["circuit_kcl_kvl"]({"solution": 12.5, "unit": "V", "tolerance": 0.05}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["solution"], 12.5)

        grader = practice_ee.GRADERS["circuit_kcl_kvl"]
        res = grader(norm, {"value": 12.5})
        self.assertTrue(res["ok"])
        self.assertEqual(res["score"], 1.0)

        res_close = grader(norm, {"value": 12.6})
        self.assertTrue(res_close["ok"])

        res_wrong = grader(norm, {"value": 24.0})
        self.assertFalse(res_wrong["ok"])

    def test_practice_ee_opamp_gain_calc(self):
        base = {"id": "ee-2", "type": "opamp_gain_calc", "prompt": "Find Vout", "explanation": "", "concept": "OpAmps"}
        # Inverting: gain = -10, Vin = 1.0 -> Vout = -10.0 (within -15 to +15 rails)
        norm = practice_ee.NORMALIZERS["opamp_gain_calc"]({"topology": "inverting", "R1": 1000, "Rf": 10000, "Vin": 1.0, "Vsat_pos": 15, "Vsat_neg": -15}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["vout_expected"], -10.0)

        grader = practice_ee.GRADERS["opamp_gain_calc"]
        res = grader(norm, {"vout": -10.0})
        self.assertTrue(res["ok"])

        # Rail saturation: Vin = 2.0 -> ideal -20 -> clamped to -15
        norm_sat = practice_ee.NORMALIZERS["opamp_gain_calc"]({"topology": "inverting", "R1": 1000, "Rf": 10000, "Vin": 2.0, "Vsat_pos": 15, "Vsat_neg": -15}, base)
        self.assertEqual(norm_sat["vout_expected"], -15.0)

    def test_practice_ai_backprop_layer_step(self):
        base = {"id": "ai-1", "type": "backprop_layer_step", "prompt": "Step", "explanation": "", "concept": "ML"}
        norm = practice_ai.NORMALIZERS["backprop_layer_step"]({"X": [1.0, 2.0], "delta": [0.5, -0.5]}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["grad_W"], [[0.5, 1.0], [-0.5, -1.0]])

        grader = practice_ai.GRADERS["backprop_layer_step"]
        res = grader(norm, {"grad_W": [[0.5, 1.0], [-0.5, -1.0]], "grad_b": [0.5, -0.5]})
        self.assertTrue(res["ok"])
        self.assertEqual(res["score"], 1.0)

    def test_practice_ai_confusion_matrix(self):
        base = {"id": "ai-2", "type": "confusion_matrix_metrics", "prompt": "Metrics", "explanation": "", "concept": "ML"}
        norm = practice_ai.NORMALIZERS["confusion_matrix_metrics"]({"TP": 80, "FP": 20, "FN": 10, "TN": 90}, base)
        self.assertIsNotNone(norm)
        # Precision: 80 / 100 = 0.8; Recall: 80 / 90 = 0.8889
        self.assertAlmostEqual(norm["metrics"]["precision"], 0.8, places=2)
        self.assertAlmostEqual(norm["metrics"]["recall"], 0.8889, places=2)

        grader = practice_ai.GRADERS["confusion_matrix_metrics"]
        res = grader(norm, {"precision": 0.8, "recall": 0.89, "f1": 0.84, "specificity": 0.82})
        self.assertTrue(res["ok"])

    def test_practice_systems_page_table_walk(self):
        base = {"id": "os-1", "type": "page_table_walk", "prompt": "Translate", "explanation": "", "concept": "OS"}
        # VA = 0x1234, page_size = 4096 (0x1000). VPN = 1, Offset = 0x234. Let PPN = 5 -> PA = 0x5234
        norm = practice_systems.NORMALIZERS["page_table_walk"]({"virtual_address": "0x1234", "page_size_bytes": 4096, "ppn": 5}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["physical_address"], "0x5234")

        grader = practice_systems.GRADERS["page_table_walk"]
        res = grader(norm, {"physical_address": "0x5234"})
        self.assertTrue(res["ok"])

    def test_practice_systems_cache_geometry(self):
        base = {"id": "os-2", "type": "cache_tag_index_offset", "prompt": "Bits", "explanation": "", "concept": "Arch"}
        # 32KB cache, 64B blocks, 4-way associative -> 512 blocks / 4 = 128 sets.
        # offset = log2(64) = 6 bits, index = log2(128) = 7 bits, tag = 32 - 13 = 19 bits.
        norm = practice_systems.NORMALIZERS["cache_tag_index_offset"]({"address_bits": 32, "cache_size_bytes": 32768, "block_size_bytes": 64, "associativity_ways": 4}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["expected_bits"], {"tag": 19, "index": 7, "offset": 6})

        grader = practice_systems.GRADERS["cache_tag_index_offset"]
        res = grader(norm, {"tag": 19, "index": 7, "offset": 6})
        self.assertTrue(res["ok"])

    def test_practice_stats_bayes(self):
        base = {"id": "st-1", "type": "bayes_posterior_update", "prompt": "Posterior", "explanation": "", "concept": "Stats"}
        # Prior = 0.01, sensitivity = 0.95, FPR = 0.05
        # num = 0.0095, denom = 0.0095 + 0.05 * 0.99 = 0.0590 -> P(H|E) ~ 0.1610
        norm = practice_stats.NORMALIZERS["bayes_posterior_update"]({"prior": 0.01, "sensitivity": 0.95, "false_positive_rate": 0.05}, base)
        self.assertIsNotNone(norm)
        self.assertAlmostEqual(norm["posterior_expected"], 0.1610, places=3)

        grader = practice_stats.GRADERS["bayes_posterior_update"]
        res = grader(norm, {"posterior": 0.161})
        self.assertTrue(res["ok"])

    def test_practice_bio_orf_translate(self):
        base = {"id": "bio-1", "type": "orf_finder_translate", "prompt": "Translate", "explanation": "", "concept": "Bio"}
        # ATG CCA GGT TAA -> M P G Stop
        norm = practice_bio.NORMALIZERS["orf_finder_translate"]({"dna_sequence": "CCATGCCAGGTTAACC"}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["protein_sequence"], "MPG")

        grader = practice_bio.GRADERS["orf_finder_translate"]
        res = grader(norm, {"protein": "MPG"})
        self.assertTrue(res["ok"])

    def test_practice_bio_restriction_digest(self):
        base = {"id": "bio-2", "type": "restriction_digest_mapper", "prompt": "Fragments", "explanation": "", "concept": "Bio"}
        # Circular plasmid 4000 bp with sites at 1000 and 3000 -> fragments: 2000, 2000
        norm = practice_bio.NORMALIZERS["restriction_digest_mapper"]({"total_length_bp": 4000, "circular": True, "cleavage_sites": [1000, 3000]}, base)
        self.assertIsNotNone(norm)
        self.assertEqual(norm["fragment_sizes"], [2000, 2000])

        grader = practice_bio.GRADERS["restriction_digest_mapper"]
        res = grader(norm, {"fragments": [2000, 2000]})
        self.assertTrue(res["ok"])

    def test_advisor_rules_cardinality_and_columbia(self):
        recs = [
            {"code": "MATH 111", "grade": "A", "credits": 4},
            {"code": "MATH 112", "grade": "B+", "credits": 4},
            {"code": "MATH 212", "grade": "A-", "credits": 4},
            {"code": "MATH 211", "grade": "B", "credits": 3},
            {"code": "MATH 302", "grade": "A", "credits": 3},
            {"code": "PHYS 101", "grade": "A", "credits": 3},
            {"code": "PHYS 101L", "grade": "A", "credits": 1},
            {"code": "PHYS 102", "grade": "B+", "credits": 3},
            {"code": "PHYS 102L", "grade": "A", "credits": 1},
            {"code": "CHEM 103", "grade": "B", "credits": 3},
            {"code": "CHEM 103L", "grade": "A", "credits": 1},
            {"code": "CSCI 141", "grade": "A", "credits": 4},
            {"code": "ECON 101", "grade": "A", "credits": 3},
            {"code": "COLL 150", "grade": "A", "credits": 4},
        ]
        audit = advisor_rules.audit_columbia_3_2(recs)
        self.assertTrue(audit["eligible"])
        self.assertTrue(audit["courses_met"])
        self.assertTrue(audit["gpa_met"])
        self.assertGreaterEqual(audit["stem_gpa"], 3.30)
        self.assertEqual(audit["missing_courses"], [])

        # Cardinality test: 2-of-3
        k_req = {
            "type": "k_of_n",
            "k": 2,
            "children": [
                {"type": "course", "code": "CSCI 241"},
                {"type": "course", "code": "CSCI 243"},
                {"type": "course", "code": "MATH 211"},
            ],
        }
        res_fail = advisor_rules.evaluate_req_node(k_req, [{"code": "MATH 211", "grade": "A"}])
        self.assertFalse(res_fail["met"])

        res_pass = advisor_rules.evaluate_req_node(k_req, [
            {"code": "MATH 211", "grade": "A"},
            {"code": "CSCI 241", "grade": "B"},
        ])
        self.assertTrue(res_pass["met"])

    def test_secret_fields_coverage(self):
        # All secret fields must be non-empty and encompass answer keys
        for mod, name in [
            (practice_ee, "EE"),
            (practice_ai, "AI"),
            (practice_systems, "Systems"),
            (practice_stats, "Stats"),
            (practice_bio, "Bio"),
        ]:
            self.assertTrue(hasattr(mod, "SECRET_FIELDS"), f"{name} lacks SECRET_FIELDS")
            self.assertGreater(len(mod.SECRET_FIELDS), 3, f"{name} SECRET_FIELDS too small")
            self.assertIn("solution", mod.SECRET_FIELDS)

        self.assertIn("grad_expected", practice_ai.SECRET_FIELDS)
        self.assertIn("merged_pair", practice_bio.SECRET_FIELDS)
        self.assertIn("gain_expected", practice_ee.SECRET_FIELDS)
        self.assertIn("is_safe", practice_systems.SECRET_FIELDS)

    def test_sandbox_audit_hooks(self):
        import sandbox_preamble
        # Test socket block
        with self.assertRaises(PermissionError):
            sandbox_preamble._audit_hook("socket.connect", ("127.0.0.1", 8090))
        with self.assertRaises(PermissionError):
            sandbox_preamble._audit_hook("socket.getaddrinfo", ("google.com", 80))

        # Test subprocess block
        with self.assertRaises(PermissionError):
            sandbox_preamble._audit_hook("subprocess.Popen", (["sh", "-c", "whoami"],))

        # Test protected file block
        with self.assertRaises(PermissionError):
            sandbox_preamble._audit_hook("open", ("content/edu_studio.db", "rb"))
        with self.assertRaises(PermissionError):
            sandbox_preamble._audit_hook("open", ("/Users/user/.ssh/id_rsa", "r"))


if __name__ == "__main__":
    unittest.main()
