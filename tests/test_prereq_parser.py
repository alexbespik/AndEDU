"""The prerequisite parser on real W&M PATH wording: parentheses, comma lists, test-score alternatives,
"may be taken concurrently" markers, corequisites and self-references. Offline."""
import unittest

from test_lab import server  # noqa: F401  (sets up the temp data dir first)

import advisor

P = advisor.parse_prereq_cnf


class PrereqParser(unittest.TestCase):
    def test_or_inside_parentheses_with_concurrent_markers(self):
        text = ("(PHYS 101, minimum score of 1 in 'Physics 101 Equivalent', PHYS 101H or 101P) and "
                "(MATH 112 * , 132 * or minimum score of 1 in 'Mathematics 112 Equivalent').\n * May be taken concurrently.\n"
                "A minimum grade of D- is required in PHYS 101, PHYS 101H, PHYS 101P, MATH 112 and MATH 132.\nCorequisite(s): PHYS 102P")
        self.assertEqual(P(text, self_code="PHYS 102"), [["PHYS 101", "PHYS 101H", "PHYS 101P"], ["MATH 112", "MATH 132"]])
        self.assertNotIn("PHYS 102P", advisor.prereq_codes_of(text, "PHYS 102"))

    def test_single_or_list(self):
        text = "(CSCI 141 * , minimum score of 1 in 'CSCI 141 Equivalent', CSCI 142 * , 140 * , DATA 140 * or 141 * ).\n * May be taken concurrently."
        self.assertEqual(P(text), [["CSCI 140", "CSCI 141", "CSCI 142", "DATA 140", "DATA 141"]])

    def test_and_of_groups_and_plain_and(self):
        text = "(PSYC 301 or minimum score of 1 in 'Psychology 301 Equivalent') and PSYC 302 and (PSYC 313, NSCI 305 or 306)."
        self.assertEqual(P(text), [["PSYC 301"], ["PSYC 302"], ["NSCI 305", "NSCI 306", "PSYC 313"]])

    def test_course_never_requires_itself_and_quoted_names_are_not_courses(self):
        text = "RUSN 102, minimum score of 1 in 'RUSN 102 Equiv-Place in 201' or minimum score of 1 in 'RUSN 201 Equiv-Place in 202'."
        self.assertEqual(P(text, self_code="RUSN 201"), [["RUSN 102"]])
        self.assertEqual(advisor.prereq_codes_of(text, "RUSN 201"), ["RUSN 102"])

    def test_or_of_and_distributes(self):
        self.assertEqual(P("MATH 211 or (MATH 112 and CSCI 141)"), [["MATH 112", "MATH 211"], ["CSCI 141", "MATH 211"]])

    def test_bare_comma_list_means_all(self):
        self.assertEqual(P("ECON 101 , ECON 102 An analysis of the monetary system"), [["ECON 101"], ["ECON 102"]])

    def test_long_shorthand_lists_and_or_of_and(self):
        nums = [340, 350, 351, 352, 362, 370, 371, 375, 377, 378, 380, 390]
        text = "(HISP " + ", ".join(map(str, nums)) + " or 389) or (HISP 360, 374 or 391)."
        self.assertEqual(P(text), [sorted({f"HISP {n}" for n in nums + [389, 360, 374, 391]})])
        self.assertEqual(P("(BIOL 220 and 221) or BIOL 204."), [["BIOL 204", "BIOL 220"], ["BIOL 204", "BIOL 221"]])
        self.assertEqual(P("ECON 101 - ECON 102"), [["ECON 101"], ["ECON 102"]])

    def test_prose_and_examples(self):
        self.assertEqual(P("ITAL 103 (or ITAL 102 ) This course covers the material of ITAL 201 and ITAL 202 in one semester"),
                         [["ITAL 102", "ITAL 103"]])
        self.assertEqual(P("AFST 205 and one AFST course at the 300 or 400 level"), [["AFST 205"]])
        self.assertEqual(P("9 hours of French (generally FREN 305 , FREN 314 , FREN 315 , and higher)"),
                         [["FREN 305", "FREN 314", "FREN 315"]])

    def test_only_a_test_score_or_consent_requires_nothing(self):
        self.assertEqual(P("Instructor Approval required to register."), [])
        self.assertEqual(P("minimum score of 4 in 'AP Calculus BC'"), [])


S = advisor.parse_prereq_scores


def options(rules):
    """{group key: [(test, min, kind), ...]} for the OR-clauses of parse_prereq_scores()."""
    return {key: [tuple(o) for o in opts] for key, opts in rules.groups}


class ScoreAlternatives(unittest.TestCase):
    """parse_prereq_scores keeps what parse_prereq_cnf drops: the test scores, equivalencies and admissions
    that can stand in for a course (no student score is stored, so these are only ever shown, never judged met)."""

    def test_ap_alternative_belongs_to_its_group(self):
        text = "MATH 111 or MATH 131 or minimum score of 4 in 'AP Calculus BC'."
        self.assertEqual(P(text), [["MATH 111", "MATH 131"]])  # unchanged
        self.assertEqual(options(S(text)), {("MATH 111", "MATH 131"): [("AP Calculus BC", 4, "test")]})
        self.assertEqual(S(text).required_alts, ())

    def test_or_of_and_gives_every_distributed_group_the_option(self):
        text = "(CSCI 141 and MATH 111) or minimum score of 5 in 'AP Computer Science A'"
        self.assertEqual(P(text), [["CSCI 141"], ["MATH 111"]])
        self.assertEqual(options(S(text)), {("CSCI 141",): [("AP Computer Science A", 5, "test")],
                                            ("MATH 111",): [("AP Computer Science A", 5, "test")]})

    def test_many_alternatives_make_no_fake_codes(self):
        names = [f"Test {n} Equivalent" for n in range(12)]
        text = "BIOL 203, " + ", ".join(f"minimum score of 1 in '{n}'" for n in names) + " or BIOL 225."
        self.assertEqual(advisor.prereq_codes_of(text), ["BIOL 203", "BIOL 225"])
        self.assertEqual(P(text), [["BIOL 203", "BIOL 225"]])
        self.assertEqual([o.test for o in S(text).groups[0][1]], names)

    def test_equivalent_kind_and_lowest_minimum(self):
        text = ("BIOL 203, minimum score of 1 in 'Intro to Biology Equivalent', minimum score of 5 in 'Intro to Biology "
                "Equivalent', BIOL 225 or minimum score of 5 in 'AP Biology'.")
        self.assertEqual(options(S(text)), {("BIOL 203", "BIOL 225"): [("Intro to Biology Equivalent", 1, "equivalent"),
                                                                       ("AP Biology", 5, "test")]})
        self.assertEqual(S("ART 211 or minimum score of 1 in 'Art 211 Exemption'.").groups[0][1][0].kind, "equivalent")
        self.assertEqual(S("HISP 202 or minimum score of 1 in 'HISP 202 Equiv-Place > 202/203'.").groups[0][1][0].test,
                         "HISP 202 Equiv-Place > 202/203")

    def test_and_level_admission_is_required(self):
        text = "minimum score of 1 in 'Admitted to SOE-Secondary', EDUC 301 and 310."
        self.assertEqual(P(text, self_code="EDUC 311"), [["EDUC 301"], ["EDUC 310"]])
        rules = S(text, "EDUC 311")
        self.assertEqual(rules.groups, ((("EDUC 301",), ()), (("EDUC 310",), ())))
        self.assertEqual([tuple(o) for o in rules.required_alts], [("Admitted to SOE-Secondary", 1, "admission")])

    def test_collapsed_rule_has_no_options(self):
        pairs = " or ".join(f"(QZ {100 + 2 * n} and QZ {101 + 2 * n})" for n in range(7))  # 2^7 = 128 clauses
        text = pairs + " or minimum score of 4 in 'AP Physics C'"
        self.assertEqual(len(P(text)), 1)  # the "any one of these courses" fallback
        self.assertEqual(S(text).groups, ())

    def test_results_are_immutable_and_cached(self):
        text = "ECON 101 or minimum score of 1 in 'ECON101 Equivalent'."
        first = S(text)
        with self.assertRaises((TypeError, AttributeError)):
            first.groups[0][1][0].min = 9  # a NamedTuple field can't be set
        with self.assertRaises(TypeError):
            first.groups[0] = ((), ())
        self.assertIs(S(text), first)
        self.assertEqual(S(text).groups[0][1][0].min, 1)

    def test_statement_is_unchanged(self):
        text = "(ECON 101 or minimum score of 1 in 'ECON101 Course Taken Elsewhere') and (ECON 102 or 'x')."
        self.assertEqual(advisor.prereq_statement(text), "(ECON 101 or  ALT ) and (ECON 102 or  ALT ).")
        self.assertEqual([o.min for _, opts in S(text).groups for o in opts], [1, None])  # a bare quoted name has no score

    def test_parse_is_unchanged_on_real_wording(self):
        """parse_prereq_cnf must give the trees stored in every database (no migration): real PATH texts."""
        cases = {
            "APSC 351": ("(MATH 111 * , minimum score of 1 in 'Mathematics 111 Equivalent' or MATH 131 * ) and (BIOL 203 * , "
                         "minimum score of 5 in 'AP Biology' or BIOL 225 * ) and BIOL 345.\n * May be taken concurrently.\n"
                         "Or consent of instructor.",
                         [["MATH 111", "MATH 131"], ["BIOL 203", "BIOL 225"], ["BIOL 345"]]),
            "ART 313": ("(ART 211 or minimum score of 1 in 'Art 211 Exemption') or (ART 212 or minimum score of 1 in 'Art 212 Exemption').",
                        [["ART 211", "ART 212"]]),
            "CHEM 309": ("(CHEM 205, 208, minimum score of 5 in 'AP Chemistry' or minimum score of 1 in 'Chemistry 208 Equivalent') "
                         "and (CHEM 207 or 209) and (CHEM 254, 256 or minimum score of 5 in 'AP Chemistry') and CHEM 253.",
                         [["CHEM 205", "CHEM 208"], ["CHEM 207", "CHEM 209"], ["CHEM 254", "CHEM 256"], ["CHEM 253"]]),
        }
        for code, (text, tree) in cases.items():
            self.assertEqual(P(text, self_code=code), tree, code)
        chem = options(S(cases["CHEM 309"][0], "CHEM 309"))
        self.assertEqual(chem[("CHEM 205", "CHEM 208")], [("AP Chemistry", 5, "test"), ("Chemistry 208 Equivalent", 1, "equivalent")])
        self.assertEqual(chem[("CHEM 207", "CHEM 209")], [])


class ScoreStatus(unittest.TestCase):
    """rule_status: "check" when only a score/equivalency/admission (not stored, so not verified) would satisfy it."""

    def rule(self, text, code="QZS 300"):
        return {"basis": "course", "text": text, "cnf": P(text, self_code=code), "concurrent_ok": [], "note": ""}

    def status(self, text, have=(), code="QZS 300"):
        return advisor.rule_status({"code": code, "prereqs": text}, self.rule(text, code), set(have))

    def test_score_alternative_is_check_not_met(self):
        st = self.status("MATH 111 or MATH 131 or minimum score of 4 in 'AP Calculus BC'.")
        self.assertEqual((st["status"], st["met"]), ("check", False))
        self.assertEqual(st["score_options"], [{"group": "MATH 111 or MATH 131",
                                                "options": [{"test": "AP Calculus BC", "min": 4, "kind": "test"}]}])
        self.assertEqual(self.status("MATH 111 or minimum score of 4 in 'AP Calculus BC'.", {"MATH 111"})["status"], "met")

    def test_a_group_without_options_is_missing(self):
        st = self.status("(MATH 111 or minimum score of 4 in 'AP Calculus BC') and CSCI 141.")
        self.assertEqual(st["status"], "missing")
        self.assertEqual([o["group"] for o in st["score_options"]], ["MATH 111"])
        self.assertEqual(self.status("(MATH 111 or minimum score of 4 in 'AP Calculus BC') and CSCI 141.", {"CSCI 141"})["status"], "check")

    def test_required_admission_is_check(self):
        text = "minimum score of 1 in 'Admitted to SOE-Secondary', EDUC 301 and 310."
        st = self.status(text, {"EDUC 301", "EDUC 310"}, code="EDUC 311")
        self.assertEqual((st["status"], st["met"], st["missing"]), ("check", False, []))
        self.assertEqual(st["required_alts"], [{"test": "Admitted to SOE-Secondary", "min": 1, "kind": "admission"}])
        self.assertEqual(self.status(text, {"EDUC 301"}, code="EDUC 311")["status"], "missing")

    def test_stored_tree_that_differs_falls_back_to_missing(self):
        rule = {**self.rule("MATH 111 or minimum score of 4 in 'AP Calculus BC'."), "cnf": [["MATH 112"]]}
        st = advisor.rule_status({"code": "QZS 300", "prereqs": rule["text"]}, rule, set())
        self.assertEqual((st["status"], st["score_options"]), ("missing", []))

    def test_plain_rules_keep_their_status(self):
        st = self.status("MATH 111 or MATH 131.")
        self.assertEqual((st["status"], st["score_options"], st["required_alts"]), ("missing", [], []))
        self.assertEqual(self.status("Instructor Approval required to register.", code="QZS 100")["status"], "none")
        self.assertEqual(self.status("", code="QZS 400")["status"], "unknown")


class PrereqDisplay(unittest.TestCase):
    def test_shorthand_after_a_star_is_expanded(self):
        text = "Prerequisites: BUAD 231L * and 231.\n * May be taken concurrently."
        self.assertEqual(P(text), [["BUAD 231L"], ["BUAD 231"]])
        self.assertEqual(advisor.prereq_display(text), "BUAD 231L and BUAD 231.")

    def test_quoted_names_and_levels_are_left_alone(self):
        self.assertEqual(advisor.prereq_display("Prerequisites: BUAD 231 and 300-level BUAD"), "BUAD 231 and 300-level BUAD")
        self.assertEqual(advisor.prereq_display("Prerequisites: MATH 111 or 131 or minimum score of 600 in 'SAT 600 or 650'"),
                         "MATH 111 or MATH 131 or minimum score of 600 in 'SAT 600 or 650'")

    def test_a_minimum_of_zero_still_counts_as_an_option(self):
        o = advisor.ScoreOption if hasattr(advisor, "ScoreOption") else None
        if o is None:
            self.skipTest("no ScoreOption type")
        fields = o._fields
        make = lambda m: o(**{f: ("Placement X" if f == "test" else "test" if f == "kind" else m if f == "min" else None) for f in fields})  # noqa: E731
        self.assertEqual(len(advisor._common_options([(make(0),), (make(0),)])), 1)


class UpsertKeepsGoodData(unittest.TestCase):
    def test_placeholder_title_and_corequisites(self):
        advisor.db.init_db(); advisor.init()
        advisor.upsert_courses([{"code": "ZQTS 420", "title": "Special Topics in Testing", "credits": "3"}], "W&M PATH Fall 2026")
        advisor.upsert_courses([{"code": "ZQTS 420", "title": "Varies by section", "prereqs": "ZQTS 101 * .\n * May be taken concurrently.\nCorequisite(s): ZQTS 420L",
                                 "prereq_codes": ["ZQTS 101", "ZQTS 420L"]}], "W&M PATH Spring 2027")
        row = advisor.get_course("ZQTS 420")
        self.assertEqual(row["title"], "Special Topics in Testing")
        self.assertEqual(row["prereq_codes"], ["ZQTS 101"])
        self.assertEqual(row["prereq_tree"], [["ZQTS 101"]])


if __name__ == "__main__":
    unittest.main()
