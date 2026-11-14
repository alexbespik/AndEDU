"""
Unit tests for Liberal Arts Kits v2:
- logic_ast singular terms and Calgary Fitch first-order translations
- logic_syllogism singular import existential fallacy exemption
- logic_argmap check_humes_guillotine (Prior's paradox, unbridged predicates)
- philin inspect_quote_context (bidirectional clause-bounded negation, German clause-final negation)
- Epistemic firewall prompt & thick concept rules
- Client redaction without stripping legacy practice answers
- All 24 practice normalizers and graders across 6 new modules
- Decision tree engine (fog-of-war, stated premises, axiomatic weights, neutral consistency tracking)
- Server API endpoints: POST /api/practice/grade and POST /api/decision-tree/step
"""
import os
import sys
import unittest
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(__file__))
from test_lab import LOCAL, TestClient

import db

import decision_tree_engine
import logic_argmap
import logic_ast
import logic_syllogism
import philin
import practice_art_history
import practice_classics
import practice_literature
import practice_music
import practice_polity
import practice_rhetoric
import server


class TestLogicASTAndSyllogism(unittest.TestCase):
    def test_singular_terms_heuristics(self):
        self.assertTrue(logic_ast.is_singular_term("Sherlock"))
        self.assertTrue(logic_ast.is_singular_term("Socrates"))
        self.assertTrue(logic_ast.is_singular_term("This apple"))
        self.assertFalse(logic_ast.is_singular_term("cat"))
        self.assertFalse(logic_ast.is_singular_term("S"))
        self.assertFalse(logic_ast.is_singular_term("All"))

    def test_categorical_to_calgary_fol(self):
        # Universal with singular term: "Sherlock is a cat" -> Cat(sherlock)
        node_sing = logic_ast.CategoricalNode("A", logic_ast.Term("Sherlock"), logic_ast.Term("cat"))
        self.assertEqual(node_sing.to_calgary_fol(), "Cat(sherlock)")

        node_sing_neg = logic_ast.CategoricalNode("E", logic_ast.Term("Sherlock"), logic_ast.Term("cat"))
        self.assertEqual(node_sing_neg.to_calgary_fol(), "~Cat(sherlock)")

        # Standard categorical propositions
        node_a = logic_ast.CategoricalNode("A", logic_ast.Term("S"), logic_ast.Term("P"))
        self.assertEqual(node_a.to_calgary_fol(), "forall x (S(x) -> P(x))")

        node_e = logic_ast.CategoricalNode("E", logic_ast.Term("S"), logic_ast.Term("P"))
        self.assertEqual(node_e.to_calgary_fol(), "forall x (S(x) -> ~P(x))")

        node_i = logic_ast.CategoricalNode("I", logic_ast.Term("S"), logic_ast.Term("P"))
        self.assertEqual(node_i.to_calgary_fol(), "exists x (S(x) & P(x))")

        node_o = logic_ast.CategoricalNode("O", logic_ast.Term("S"), logic_ast.Term("P"))
        self.assertEqual(node_o.to_calgary_fol(), "exists x (S(x) & ~P(x))")

    def test_existential_fallacy_exemption_with_singular_terms(self):
        # Standard boolean reading flags existential fallacy on universal premises with particular conclusion
        v_bool = logic_syllogism.violations("AAI", 1, reading="boolean", singular_import=False)
        self.assertIn("existential_fallacy", v_bool)

        # When singular import is True, existential fallacy is exempted
        v_sing = logic_syllogism.violations("AAI", 1, reading="boolean", singular_import=True)
        self.assertNotIn("existential_fallacy", v_sing)

        # Check through parse_spec with singular term (Socrates)
        spec = {
            "major": {"type": "A", "subject": "men", "predicate": "mortal"},
            "minor": {"type": "A", "subject": "Socrates", "predicate": "men"},
            "conclusion": {"type": "I", "subject": "Socrates", "predicate": "mortal"},
        }
        res = logic_syllogism.check_syllogism(spec, reading="boolean")
        violation_codes = [v["rule"] for v in res["violations"]]
        self.assertNotIn("existential_fallacy", violation_codes)


class TestHumesGuillotineAndPriorParadox(unittest.TestCase):
    def test_is_ought_gap_pure_factual_to_normative(self):
        # Conclusion is normative, but premises are purely empirical/factual
        claims = [
            {"id": "c1", "text": "Drinking tea is widespread.", "kind": "empirical"},
            {"id": "c2", "text": "One ought to drink tea.", "kind": "normative", "role": "conclusion",
             "predicates": ["ought", "drink_tea"]},
        ]
        edges = [{"from": "c1", "to": "c2", "type": "supports"}]
        violations = logic_argmap.check_humes_guillotine(claims, edges)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["code"], "is_ought_gap")
        self.assertIn("drink_tea", violations[0]["is_ought_unbridged_predicates"])

    def test_prior_paradox_irrelevant_dummy_normative_premise(self):
        # Prior's paradox: Adding an irrelevant normative premise (e.g. "Honesty is noble")
        # to bridge a factual premise to an unrelated moral conclusion ("One ought to steal")
        claims = [
            {"id": "c1", "text": "The apple is in the store.", "kind": "empirical"},
            {"id": "c2", "text": "Honesty is noble.", "kind": "normative", "predicates": ["honesty", "noble"]},
            {"id": "c3", "text": "One ought to steal the apple.", "kind": "normative", "role": "conclusion",
             "predicates": ["ought", "steal", "apple"]},
        ]
        edges = [{"from": ["c1", "c2"], "to": "c3", "type": "supports"}]
        violations = logic_argmap.check_humes_guillotine(claims, edges)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["code"], "is_ought_gap")
        # Unbridged predicates should include 'steal' or 'ought'
        self.assertTrue(any(p in violations[0]["is_ought_unbridged_predicates"] for p in ("steal", "apple", "ought")))

    def test_valid_bridged_normative_argument(self):
        # Valid bridge: Normative premise shares deontic predicates with conclusion
        claims = [
            {"id": "c1", "text": "Action A causes severe suffering.", "kind": "empirical"},
            {"id": "c2", "text": "Actions causing severe suffering are impermissible.", "kind": "normative",
             "predicates": ["impermissible", "suffering"]},
            {"id": "c3", "text": "Action A is impermissible.", "kind": "normative", "role": "conclusion",
             "predicates": ["impermissible", "action_a"]},
        ]
        edges = [{"from": ["c1", "c2"], "to": "c3", "type": "supports"}]
        violations = logic_argmap.check_humes_guillotine(claims, edges)
        self.assertEqual(len(violations), 0)


class TestPhilinQuoteContextAndEpistemicFirewall(unittest.TestCase):
    def test_bidirectional_polarity_parity(self):
        # Odd negation count inverts polarity -> context severed
        text = "It is not the case that the policy was effective."
        span = (24, 48)  # "the policy was effective"
        res = philin.inspect_quote_context(text, span)
        self.assertTrue(res["context_severed"])
        self.assertEqual(res["polarity"], "inverted")

        # Even negation count (double negative) -> preserved polarity
        text_dn = "It is not untrue that the policy was effective."
        res_dn = philin.inspect_quote_context(text_dn, span)
        self.assertEqual(res_dn["negation_count"], 2)
        self.assertEqual(res_dn["polarity"], "preserved")

    def test_german_clause_final_negation(self):
        # In German, negation frequently occurs at the end of the subordinate or main clause
        text_de = "Dass die Massnahme funktionierte, bestreitet der Autor nicht."
        # Quote: "die Massnahme funktionierte"
        start = text_de.index("die Massnahme funktionierte")
        end = start + len("die Massnahme funktionierte")
        res = philin.inspect_quote_context(text_de, (start, end))
        self.assertTrue(res["context_severed"])
        self.assertIn("nicht", res["negations"])

        # Test "keineswegs" after span
        text_de2 = "Der Minister erklaerte, die Krise sei beendet, was keineswegs zutrifft."
        start2 = text_de2.index("die Krise sei beendet")
        end2 = start2 + len("die Krise sei beendet")
        res2 = philin.inspect_quote_context(text_de2, (start2, end2))
        self.assertTrue(res2["context_severed"])
        self.assertIn("keineswegs", res2["negations"])

    def test_clause_boundary_isolation(self):
        # Negation outside clause delimiter should NOT sever the quote
        text = "We did not arrive early. The experiment was completely successful."
        start = text.index("The experiment was completely successful")
        end = start + len("The experiment was completely successful")
        res = philin.inspect_quote_context(text, (start, end))
        self.assertFalse(res["context_severed"])
        self.assertEqual(res["negation_count"], 0)

    def test_epistemic_firewall_prompt_exists(self):
        self.assertIn("Three-Rule Epistemic Firewall", philin.PHILIN_TRANSCRIBE_PROMPT)
        self.assertIn("Decompose thick ethical concepts", philin.PHILIN_TRANSCRIBE_PROMPT)
        self.assertIn("predicates: List[str]", philin.PHILIN_TRANSCRIBE_PROMPT)


class TestClientRedaction(unittest.TestCase):
    def test_redact_server_graded_without_stripping_legacy_answer(self):
        topic = {
            "id": "test-topic",
            "title": "Test Topic",
            "practice": [
                # Legacy client-side items: MUST retain "answer"
                {"id": "p1", "type": "true_false", "prompt": "Is snow white?", "answer": True, "explanation": "It is."},
                {"id": "p2", "type": "fill_blank", "prompt": "Paris is the capital of ___", "answer": "France", "options": ["France", "Spain"]},
                {"id": "p3", "type": "order_steps", "prompt": "Order steps", "steps": ["1", "2"]},
                {"id": "p4", "type": "numeric", "prompt": "2 + 2", "answer": 4, "tolerance": 0.01},
                # Server-graded items: secret keys MUST be stripped
                {"id": "p5", "type": "scansion", "line": "Shall I compare thee to a summer's day?", "stress_pattern": "0 1 0 1 0 1 0 1 0 1", "meter": "iambic pentameter"},
                {"id": "p6", "type": "compute_dhondt", "votes": {"A": 100, "B": 50}, "seats": 3, "solution": {"A": 2, "B": 1}},
            ],
        }

        redacted = server.redact_for_client(topic)
        p_map = {item["id"]: item for item in redacted["practice"]}

        # Legacy items keep "answer"
        self.assertEqual(p_map["p1"].get("answer"), True)
        self.assertEqual(p_map["p2"].get("answer"), "France")
        self.assertEqual(p_map["p4"].get("answer"), 4)

        # Server-graded items have solution keys stripped
        self.assertNotIn("stress_pattern", p_map["p5"])
        self.assertEqual(p_map["p5"]["meter"], "iambic pentameter")
        self.assertNotIn("solution", p_map["p6"])
        self.assertEqual(p_map["p6"]["seats"], 3)


class TestAll24PracticeModules(unittest.TestCase):
    # Literature
    def test_literature_scansion(self):
        raw = {"type": "scansion", "prompt": "Scan line", "line": "To be or not to be", "stress_pattern": "0 1 0 1 0 1"}
        clean = practice_literature.NORMALIZERS["scansion"](raw, {"id": "p1", "type": "scansion"})
        self.assertIsNotNone(clean)
        self.assertEqual(clean["stress_pattern"], "0 1 0 1 0 1")
        res = practice_literature.GRADERS["scansion"](clean, "0 1 0 1 0 1")
        self.assertTrue(res["ok"])
        self.assertEqual(res["score"], 1.0)

    def test_literature_volta_spot(self):
        raw = {"type": "volta_spot", "prompt": "Find volta", "lines": ["Line 1", "Line 2", "Yet do I marvel"], "target_index": 2}
        clean = practice_literature.NORMALIZERS["volta_spot"](raw, {"id": "p1", "type": "volta_spot"})
        self.assertIsNotNone(clean)
        res = practice_literature.GRADERS["volta_spot"](clean, 2)
        self.assertTrue(res["ok"])

    def test_literature_rhyme_scheme_audit(self):
        raw = {"type": "rhyme_scheme_audit", "prompt": "Audit rhyme", "lines": ["L1", "L2", "L3", "L4"], "rhyme_scheme": "ABAB"}
        clean = practice_literature.NORMALIZERS["rhyme_scheme_audit"](raw, {"id": "p1", "type": "rhyme_scheme_audit"})
        self.assertIsNotNone(clean)
        res = practice_literature.GRADERS["rhyme_scheme_audit"](clean, "ABAB")
        self.assertTrue(res["ok"])

    def test_literature_chronology_unravel(self):
        raw = {"type": "chronology_unravel", "prompt": "Unravel chronology",
               "events": [{"id": "e1", "text": "Discovered secret"}, {"id": "e2", "text": "Fell in love"}],
               "canonical_order": ["e2", "e1"]}
        clean = practice_literature.NORMALIZERS["chronology_unravel"](raw, {"id": "p1", "type": "chronology_unravel"})
        self.assertIsNotNone(clean)
        res = practice_literature.GRADERS["chronology_unravel"](clean, ["e2", "e1"])
        self.assertTrue(res["ok"])

    # Music
    def test_music_satb_progression(self):
        # Parallel fifths between Soprano and Tenor
        c1 = {"s": 67, "a": 64, "t": 60, "b": 48}  # G4, E4, C4, C3
        c2 = {"s": 69, "a": 65, "t": 62, "b": 50}  # A4, F4, D4, D3: S-T is 67-60=7 and 69-62=7
        raw = {"type": "lint_satb_progression", "prompt": "Check SATB", "chords": [c1, c2]}
        clean = practice_music.NORMALIZERS["lint_satb_progression"](raw, {"id": "p1", "type": "lint_satb_progression"})
        self.assertIsNotNone(clean)
        self.assertFalse(clean["valid"])
        self.assertTrue(any("parallel_fifth" in e for e in clean["expected_errors"]))
        # Grader detects correct error
        res = practice_music.GRADERS["lint_satb_progression"](clean, clean["expected_errors"])
        self.assertTrue(res["ok"])

    def test_music_roman_numeral_analysis(self):
        raw = {"type": "roman_numeral_analysis", "prompt": "Analyze chords", "key": "C major", "chords": ["C", "F", "G", "C"], "expected": ["I", "IV", "V", "I"]}
        clean = practice_music.NORMALIZERS["roman_numeral_analysis"](raw, {"id": "p1", "type": "roman_numeral_analysis"})
        self.assertIsNotNone(clean)
        res = practice_music.GRADERS["roman_numeral_analysis"](clean, ["I", "IV", "V", "I"])
        self.assertTrue(res["ok"])

    def test_music_ear_interval_id(self):
        raw = {"type": "ear_interval_id", "prompt": "Identify interval", "semitones": 7, "interval_name": "perfect fifth"}
        clean = practice_music.NORMALIZERS["ear_interval_id"](raw, {"id": "p1", "type": "ear_interval_id"})
        self.assertIsNotNone(clean)
        res = practice_music.GRADERS["ear_interval_id"](clean, 7)
        self.assertTrue(res["ok"])

    def test_music_figured_bass_realize(self):
        raw = {"type": "figured_bass_realize", "prompt": "Realize figured bass", "bass_note": "C3", "figures": "6", "solution": ["E4", "A4"]}
        clean = practice_music.NORMALIZERS["figured_bass_realize"](raw, {"id": "p1", "type": "figured_bass_realize"})
        self.assertIsNotNone(clean)
        res = practice_music.GRADERS["figured_bass_realize"](clean, ["E4", "A4"])
        self.assertTrue(res["ok"])

    # Art History
    def test_art_history_composition_vector(self):
        raw = {"type": "composition_vector", "prompt": "Find vanishing point", "focal_point": {"x": 0.5, "y": 0.5}, "tolerance": 0.035}
        clean = practice_art_history.NORMALIZERS["composition_vector"](raw, {"id": "p1", "type": "composition_vector"})
        self.assertIsNotNone(clean)
        res = practice_art_history.GRADERS["composition_vector"](clean, {"x": 0.51, "y": 0.52})
        self.assertTrue(res["ok"])

    def test_art_history_label_architecture(self):
        raw = {"type": "label_architecture", "prompt": "Match orders", "solution": {"col1": "doric", "col2": "ionic"}}
        clean = practice_art_history.NORMALIZERS["label_architecture"](raw, {"id": "p1", "type": "label_architecture"})
        self.assertIsNotNone(clean)
        res = practice_art_history.GRADERS["label_architecture"](clean, {"col1": "doric", "col2": "ionic"})
        self.assertTrue(res["ok"])

    def test_art_history_iconography_decode(self):
        raw = {"type": "iconography_decode", "prompt": "Decode symbols", "solution": {"wheel": "St. Catherine", "keys": "St. Peter"}}
        clean = practice_art_history.NORMALIZERS["iconography_decode"](raw, {"id": "p1", "type": "iconography_decode"})
        self.assertIsNotNone(clean)
        res = practice_art_history.GRADERS["iconography_decode"](clean, {"wheel": "St. Catherine", "keys": "St. Peter"})
        self.assertTrue(res["ok"])

    def test_art_history_stylistic_taxonomy(self):
        raw = {"type": "stylistic_taxonomy", "prompt": "Identify period", "traits": ["chiaroscuro", "dramatic emotion"], "period": "Baroque"}
        clean = practice_art_history.NORMALIZERS["stylistic_taxonomy"](raw, {"id": "p1", "type": "stylistic_taxonomy"})
        self.assertIsNotNone(clean)
        res = practice_art_history.GRADERS["stylistic_taxonomy"](clean, "Baroque")
        self.assertTrue(res["ok"])

    # Classics
    def test_classics_epigraphy_transcribe(self):
        raw = {"type": "epigraphy_transcribe", "prompt": "Transcribe inscription",
               "inscription_raw": "SENATVSPOPVLVSQVEROMANVS", "transcription": "Senatus Populusque Romanus"}
        clean = practice_classics.NORMALIZERS["epigraphy_transcribe"](raw, {"id": "p1", "type": "epigraphy_transcribe"})
        self.assertIsNotNone(clean)
        res = practice_classics.GRADERS["epigraphy_transcribe"](clean, "senatus populusque romanus")
        self.assertTrue(res["ok"])

    def test_classics_harris_matrix_build(self):
        raw = {"type": "harris_matrix_build", "prompt": "Build stratigraphy",
               "strata": ["1", "2"], "solution": [["1", "2"]]}
        clean = practice_classics.NORMALIZERS["harris_matrix_build"](raw, {"id": "p1", "type": "harris_matrix_build"})
        self.assertIsNotNone(clean)
        res = practice_classics.GRADERS["harris_matrix_build"](clean, [["1", "2"]])
        self.assertTrue(res["ok"])

    def test_classics_cursus_honorum_order(self):
        raw = {"type": "cursus_honorum_order", "prompt": "Order cursus honorum",
               "solution": ["Quaestor", "Aedile", "Praetor", "Consul"]}
        clean = practice_classics.NORMALIZERS["cursus_honorum_order"](raw, {"id": "p1", "type": "cursus_honorum_order"})
        self.assertIsNotNone(clean)
        res = practice_classics.GRADERS["cursus_honorum_order"](clean, ["Quaestor", "Aedile", "Praetor", "Consul"])
        self.assertTrue(res["ok"])

    def test_classics_athenian_sortition_sim(self):
        raw = {"type": "athenian_sortition_sim", "prompt": "Lottery allocation",
               "candidates": {"Erechtheis": ["Kallias", "Perikles", "Diodoros"]},
               "quotas": {"Erechtheis": 2}}
        clean = practice_classics.NORMALIZERS["athenian_sortition_sim"](raw, {"id": "p1", "type": "athenian_sortition_sim"})
        self.assertIsNotNone(clean)
        res = practice_classics.GRADERS["athenian_sortition_sim"](clean, {"Erechtheis": ["Kallias", "Perikles"]})
        self.assertTrue(res["ok"])

    # Rhetoric
    def test_rhetoric_stasis_classify(self):
        raw = {"type": "stasis_classify", "prompt": "Classify stasis", "case": "Did Brutus strike Caesar?", "correct_stasis": "conjecture"}
        clean = practice_rhetoric.NORMALIZERS["stasis_classify"](raw, {"id": "p1", "type": "stasis_classify"})
        self.assertIsNotNone(clean)
        res = practice_rhetoric.GRADERS["stasis_classify"](clean, "conjecture")
        self.assertTrue(res["ok"])

    def test_rhetoric_trope_hunter(self):
        raw = {"type": "trope_hunter", "prompt": "Spot trope", "passage": "Ask not what your country can do for you...", "target_trope": "chiasmus"}
        clean = practice_rhetoric.NORMALIZERS["trope_hunter"](raw, {"id": "p1", "type": "trope_hunter"})
        self.assertIsNotNone(clean)
        res = practice_rhetoric.GRADERS["trope_hunter"](clean, "chiasmus")
        self.assertTrue(res["ok"])

    def test_rhetoric_dispositio_sort(self):
        raw = {"type": "dispositio_sort", "prompt": "Sort oration parts",
               "solution": ["exordium", "narratio", "confirmatio", "refutatio", "peroratio"]}
        clean = practice_rhetoric.NORMALIZERS["dispositio_sort"](raw, {"id": "p1", "type": "dispositio_sort"})
        self.assertIsNotNone(clean)
        res = practice_rhetoric.GRADERS["dispositio_sort"](clean, ["exordium", "narratio", "confirmatio", "refutatio", "peroratio"])
        self.assertTrue(res["ok"])

    def test_rhetoric_enthymeme_excavator(self):
        raw = {"type": "enthymeme_excavator", "prompt": "Excavate unstated premise",
               "stated_premise": "Socrates is human", "conclusion": "Socrates is mortal",
               "options": ["All humans are mortal", "All mortals are humans"], "solution": "All humans are mortal"}
        clean = practice_rhetoric.NORMALIZERS["enthymeme_excavator"](raw, {"id": "p1", "type": "enthymeme_excavator"})
        self.assertIsNotNone(clean)
        res = practice_rhetoric.GRADERS["enthymeme_excavator"](clean, "All humans are mortal")
        self.assertTrue(res["ok"])

    # Polity
    def test_polity_compute_dhondt(self):
        raw = {"type": "compute_dhondt", "prompt": "Calculate seats", "votes": {"A": 100000, "B": 80000, "C": 30000}, "seats": 5}
        clean = practice_polity.NORMALIZERS["compute_dhondt"](raw, {"id": "p1", "type": "compute_dhondt"})
        self.assertIsNotNone(clean)
        # 100k, 80k, 50k (100k/2), 40k (80k/2), 33.3k (100k/3) -> A:3, B:2, C:0
        self.assertEqual(clean["solution"], {"A": 3, "B": 2, "C": 0})
        res = practice_polity.GRADERS["compute_dhondt"](clean, {"A": 3, "B": 2, "C": 0})
        self.assertTrue(res["ok"])

    def test_polity_shapley_shubik(self):
        # Weights A:50, B:49, C:1 with quota 51:
        # A + B = 99 >= 51 (A or B pivot depending on order)
        # A + C = 51 >= 51 (C or A pivot)
        # B + C = 50 < 51 (cannot win alone, needs A)
        raw = {"type": "compute_shapley_shubik_pivotal", "prompt": "Calculate power index",
               "quota": 51, "weights": {"A": 50, "B": 49, "C": 1}}
        clean = practice_polity.NORMALIZERS["compute_shapley_shubik_pivotal"](raw, {"id": "p1", "type": "compute_shapley_shubik_pivotal"})
        self.assertIsNotNone(clean)
        self.assertIn("A", clean["shapley_shubik_index"])
        res = practice_polity.GRADERS["compute_shapley_shubik_pivotal"](clean, clean["shapley_shubik_index"])
        self.assertTrue(res["ok"])

    def test_polity_veto_pipeline(self):
        raw = {"type": "veto_pipeline", "prompt": "Trace veto",
               "veto_players": ["President", "Senate"], "will_pass": False, "blocking_actor": "President"}
        clean = practice_polity.NORMALIZERS["veto_pipeline"](raw, {"id": "p1", "type": "veto_pipeline"})
        self.assertIsNotNone(clean)
        res = practice_polity.GRADERS["veto_pipeline"](clean, {"will_pass": False, "blocking_actor": "President"})
        self.assertTrue(res["ok"])

    def test_polity_instant_runoff_tally(self):
        ballots = [
            ["A", "B", "C"],
            ["A", "C", "B"],
            ["B", "A", "C"],
            ["C", "B", "A"],
        ]
        raw = {"type": "instant_runoff_tally", "prompt": "Compute IRV rounds", "ballots": ballots, "candidates": ["A", "B", "C"]}
        clean = practice_polity.NORMALIZERS["instant_runoff_tally"](raw, {"id": "p1", "type": "instant_runoff_tally"})
        self.assertIsNotNone(clean)
        res = practice_polity.GRADERS["instant_runoff_tally"](clean, {"winner": clean["winner"]})
        self.assertTrue(res["ok"])


class TestDecisionTreeEngine(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "version": 1,
            "kind": "decision_tree",
            "title": "Trolley Dilemma Simulation",
            "description": "Evaluate actions under uncertainty and competing axioms.",
            "initial_node": "switch_point",
            "fog_of_war_hidden_facts": {
                "fact_worker_radio": "The single worker on the side track is wearing noise-canceling headphones.",
            },
            "nodes": {
                "switch_point": {
                    "id": "switch_point",
                    "text": "A runaway trolley approaches 5 workers. You stand near the switch.",
                    "premises": ["Act to minimize catastrophic loss when possible"],
                    "choices": [
                        {
                            "id": "pull_lever",
                            "text": "Pull the lever to divert the trolley onto the side track.",
                            "next_node": "consequence_divert",
                            "axiomatic_weights": {"utilitarian": 1.0, "deontological": -1.0},
                            "reveals_facts": ["fact_worker_radio"],
                            "premises_committed": ["Directing threat away from 5 justifies one bystander loss"],
                        },
                        {
                            "id": "do_nothing",
                            "text": "Do not intervene; let fate take its course.",
                            "next_node": "consequence_inaction",
                            "axiomatic_weights": {"utilitarian": -1.0, "deontological": 1.0},
                            "premises_committed": ["Active causation of harm is strictly impermissible"],
                        },
                    ],
                },
                "consequence_divert": {
                    "id": "consequence_divert",
                    "text": "The trolley diverts. The worker on the side track cannot hear warnings.",
                    "choices": [],
                },
                "consequence_inaction": {
                    "id": "consequence_inaction",
                    "text": "The trolley continues on main track.",
                    "choices": [],
                },
            },
        }

    def test_validation(self):
        clean, errs = decision_tree_engine.validate_decision_tree_spec(self.spec)
        self.assertEqual(errs, [])
        self.assertEqual(clean["kind"], "decision_tree")
        self.assertEqual(clean["initial_node"], "switch_point")

    def test_step_execution_and_fog_of_war(self):
        # Step 1: pull lever
        res = decision_tree_engine.step_decision_tree(self.spec, history=[], choice="pull_lever")
        self.assertTrue(res["ok"])
        self.assertEqual(res["current_node_id"], "consequence_divert")
        self.assertTrue(res["is_terminal"])
        # Fog of war reveals fact_worker_radio
        revealed_ids = [f["id"] for f in res["revealed_facts"]]
        self.assertIn("fact_worker_radio", revealed_ids)
        # Axiomatic weights tracked
        self.assertEqual(res["axiomatic_weights"].get("utilitarian"), 1.0)
        self.assertEqual(res["axiomatic_weights"].get("deontological"), -1.0)
        # Committed premises preserved
        self.assertIn("Directing threat away from 5 justifies one bystander loss", res["stated_premises"])
        # Neutral consistency: no moral wrong grading
        self.assertIsInstance(res["consistency"], float)


class TestServerAPIEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.client = TestClient(server.app, base_url=LOCAL)

    def test_decision_tree_step_api(self):
        spec = {
            "version": 1,
            "kind": "decision_tree",
            "title": "Diplomatic Crisis",
            "initial_node": "start",
            "nodes": {
                "start": {
                    "id": "start",
                    "text": "Crisis begins",
                    "choices": [
                        {"id": "talk", "text": "Initiate talks", "next_node": "talks_held",
                         "axiomatic_weights": {"diplomacy": 1.0}},
                    ],
                },
                "talks_held": {
                    "id": "talks_held",
                    "text": "Talks held peacefully",
                    "choices": [],
                },
            },
        }
        res = self.client.post("/api/decision-tree/step", json={"spec": spec, "history": [], "choice": "talk"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["current_node_id"], "talks_held")
        self.assertEqual(data["axiomatic_weights"]["diplomacy"], 1.0)

    def test_practice_grade_api(self):
        # Save a topic containing a server-graded practice item
        topic_data = {
            "id": "test-grading-topic",
            "title": "Grading API Topic",
            "category": "Literature",
            "markdownContent": "# Scansion Lesson\n\nContent here.",
            "workspace": "literature",
            "practice": [
                {
                    "id": "item1",
                    "type": "scansion",
                    "prompt": "Scan line",
                    "line": "Shall I compare thee to a summer's day?",
                    "stress_pattern": "0 1 0 1 0 1 0 1 0 1",
                    "meter": "iambic pentameter",
                }
            ],
        }
        save_res = self.client.post("/api/topics", json=topic_data)
        self.assertEqual(save_res.status_code, 200)

        # GET /api/topics/{id} must have stress_pattern redacted
        get_res = self.client.get("/api/topics/test-grading-topic")
        self.assertEqual(get_res.status_code, 200)
        p_items = get_res.json().get("practice", [])
        self.assertEqual(len(p_items), 1)
        self.assertNotIn("stress_pattern", p_items[0])

        # POST /api/practice/grade grades it against the unredacted server stored topic
        grade_res = self.client.post("/api/practice/grade", json={
            "topicId": "test-grading-topic",
            "itemId": "item1",
            "submission": "0 1 0 1 0 1 0 1 0 1",
        })
        self.assertEqual(grade_res.status_code, 200)
        grade_data = grade_res.json()
        self.assertTrue(grade_data["ok"])
        self.assertEqual(grade_data["score"], 1.0)


if __name__ == "__main__":
    unittest.main()
