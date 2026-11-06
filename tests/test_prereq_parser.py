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
