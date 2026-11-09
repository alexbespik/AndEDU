"""W&M next-term logic, the CS / Data Science program data, and where the advisor context puts them. Never calls Gemini."""
import unittest
import uuid
from datetime import date

from test_lab import LOCAL, server  # noqa: E402  (sets up the temporary data folder and offline Gemini)
import advisor  # noqa: E402
import advisor_chat  # noqa: E402
import wm_advising as w  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TODAY = date(2026, 11, 7)


class NextTerm(unittest.TestCase):
    def test_spring_2027_until_its_add_drop_closes(self):
        for d in (TODAY, date(2027, 1, 20), date(2027, 2, 5)):
            self.assertEqual(w.next_term(d), "202720", d)

    def test_falls_back_to_academic_year_codes(self):
        self.assertEqual(w.next_term(date(2027, 2, 6)), "202810")  # Fall 2027, never Summer 2027
        self.assertEqual(w.next_term(date(2027, 2, 9)), "202810")  # Spring 2027 is in the calendar and closed
        self.assertEqual(w.next_term(date(2027, 8, 10)), "202810")  # Fall 2027 add/drop not over yet
        self.assertEqual(w.next_term(date(2027, 9, 20)), "202820")  # Spring 2028
        self.assertEqual(w.next_term(date(2028, 1, 10)), "202820")  # Spring 2028 add/drop still open
        self.assertEqual(w.term_name("202810"), "Fall 2027")
        self.assertEqual(w.term_name("202630"), "Summer 2026")

    def test_term_context_lists_dates_or_says_none_loaded(self):
        ctx = w.term_context(TODAY)
        self.assertIn("Spring 2027 (term code 202720)", ctx)
        self.assertIn("Feb 5", ctx)
        self.assertIn("Withdrawal", ctx)
        self.assertIn("subject to change", ctx)
        later = w.term_context(date(2027, 3, 1))
        self.assertIn("Fall 2027", later)
        self.assertIn("not loaded", later)
        self.assertNotIn("Feb 5", later)


class Programs(unittest.TestCase):
    def test_data_is_complete(self):
        ids = {p["id"] for p in w.WM_PROGRAMS}
        self.assertEqual(ids, {"cs_bs", "cs_ba", "cs_minor", "data_bs", "data_minor"})
        for p in w.WM_PROGRAMS:
            self.assertTrue(p["source"].startswith("https://catalog.wm.edu/programs/"), p["id"])
            self.assertTrue(p["requirements"] and p["differences"], p["id"])
        self.assertEqual(len(next(p for p in w.WM_PROGRAMS if p["id"] == "cs_bs")["tracks"]), 3)
        self.assertEqual(len(next(p for p in w.WM_PROGRAMS if p["id"] == "data_bs")["tracks"]), 4)
        for code in w.WM_CALENDAR:
            date.fromisoformat(w.WM_CALENDAR[code]["last_add_drop"])

    def test_every_track_and_difference_renders_under_the_cap(self):
        ctx = w.programs_context("How do the CS concentrations and data science tracks differ?", [])
        for name in ("General", "Artificial Intelligence/Machine Learning", "Cybersecurity", "Artificial Intelligence",
                     "Algorithms", "Data Application", "Spatial Data Analytics", "B.A.", "minor"):
            self.assertIn(name, ctx)
        self.assertEqual(ctx.count("How the options differ"), len(w.WM_PROGRAMS))
        self.assertNotIn("omitted for length", ctx)
        self.assertLessEqual(len(ctx), w.PROGRAMS_MAX)
        self.assertIn(w.CATALOG_YEAR, ctx)

    def test_marks_completed_courses_and_stays_quiet_when_unrelated(self):
        ctx = w.programs_context("which track?", [{"code": "CSCI 241"}])
        self.assertIn("CSCI 241 [done]", ctx)
        self.assertNotIn("CSCI 303 [done]", ctx)
        self.assertEqual(w.programs_context("what time is lunch", []), "")
        self.assertEqual(w.programs_context("should I declare a history major?", [{"code": "HIST 101"}]), "")
        self.assertTrue(w.programs_context("what should I take", [{"code": "DATA 201"}]))  # DATA student, broad question

    def test_corrected_facts(self):
        cs = w.MAJOR_ROADMAPS["computer_science"]["guidelines"]
        self.assertIn("Modern Programming Fundamentals", cs)
        self.assertIn("MATH 109", cs)
        self.assertNotIn("Computational Problem Solving", cs)
        self.assertNotIn("10th class day", w.WM_CORE_POLICIES)
        self.assertNotIn("DATA 141", w.MAJOR_ROADMAPS["data_science"]["guidelines"])


class AdvisorContext(unittest.TestCase):
    def setUp(self):
        self.ctx = TestClient(server.app, base_url=LOCAL)
        c = self.c = self.ctx.__enter__()
        user = c.post("/api/users", json={"name": f"Terms {uuid.uuid4().hex[:6]}"}).json()
        self.uid = user.get("id") or user["user"]["id"]

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def test_term_context_comes_first_and_next_term_sections_lead(self):
        advisor.upsert_courses([{"code": "ZQTP 101", "title": "Term Probe", "credits": "3"}], "test")
        advisor.upsert_sections([
            {"school": "wm", "term": "202620", "term_name": "Spring 2026", "crn": "91001", "code": "ZQTP 101",
             "section": "01", "title": "Term Probe", "instructor": "Old", "meets": "MWF 9-9:50a", "credits": "3", "status": "A"},
            {"school": "wm", "term": "202720", "term_name": "Spring 2027", "crn": "91002", "code": "ZQTP 101",
             "section": "01", "title": "Term Probe", "instructor": "New", "meets": "TR 2-3:20p", "credits": "3", "status": "A"},
        ])
        ctx = advisor_chat.build_context(self.uid, "Can I take ZQTP 101 next semester for my data science track?", today=TODAY)
        self.assertLess(ctx.index("TERM CONTEXT"), ctx.index("COMPLETED COURSES"))
        self.assertIn("W&M PROGRAMS", ctx)
        self.assertIn("Spring 2027 sections: sec 01 TR 2-3:20p (New)", ctx)
        self.assertNotIn("(Old)", ctx)  # a past section is never listed as a section
        self.assertIn("other terms it ran (history only, not Spring 2027): Spring 2026", ctx)
        long_ctx = advisor_chat.build_context(self.uid, "data " * 1500, today=TODAY)
        self.assertIn("TERM CONTEXT", long_ctx)

    def test_course_without_next_term_sections_is_not_offered(self):
        # like CSCI 150: one Fall 2026 section, nothing in Spring 2027
        advisor.upsert_courses([{"code": "ZQTN 150", "title": "Fall Only Seminar", "credits": "4"}], "test")
        advisor.upsert_sections([
            {"school": "wm", "term": "202710", "term_name": "Fall 2026", "crn": "91414", "code": "ZQTN 150",
             "section": "01", "title": "Fall Only Seminar", "instructor": "Prof", "meets": "MW 2-3:20p", "credits": "4", "status": "F"},
        ])
        line = advisor_chat._sections("ZQTN 150", "202720")
        self.assertIn("NOT offered in Spring 2027", line)
        self.assertIn("Fall 2026", line)
        self.assertNotIn("sec 01", line)
        self.assertNotIn("91414", line)
        info = advisor_chat.section_summary("ZQTN 150", "202720")
        self.assertEqual((info["next_term_sections"], info["other_terms"], info["later_terms"]), ([], ["Fall 2026"], []))
        # a term after the next one is "later", never history
        later = advisor_chat.section_summary("ZQTN 150", "202630")
        self.assertEqual((later["later_terms"], later["other_terms"]), (["Fall 2026"], []))

        r = self.c.get("/api/advisor/catalog/ZQTN 150/sections").json()
        self.assertEqual(r["next_term"], w.next_term())  # follows today's date, so no hardcoded term here
        self.assertEqual(r["next_term_name"], w.term_name(w.next_term()))
        self.assertIn("other_terms", r)
        self.assertEqual(len(r["sections"]), 1)  # the all-terms list is unchanged for older clients

    def test_section_search_next_term_by_default_for_the_companion(self):
        from unittest import mock
        import mcp_server
        nxt = w.next_term()
        advisor.upsert_sections([
            {"school": "wm", "term": nxt, "term_name": w.term_name(nxt), "crn": "92001", "code": "ZQTS 410",
             "section": "01", "title": "Search Probe", "instructor": "Now", "meets": "MWF 9-9:50a", "credits": "3", "status": "A"},
            {"school": "wm", "term": "202230", "term_name": "Summer 2022", "crn": "92002", "code": "ZQTS 410",
             "section": "01", "title": "Search Probe", "instructor": "Then", "meets": "TBD", "credits": "3", "status": "A"},
        ])
        r = self.c.get("/api/advisor/sections?q=ZQTS 410&term=next").json()
        self.assertEqual([s["crn"] for s in r["sections"]], ["92001"])
        self.assertNotIn("note", r)
        r_all = self.c.get("/api/advisor/sections?q=ZQTS 410&term=all").json()
        self.assertEqual({s["crn"] for s in r_all["sections"]}, {"92001", "92002"})
        self.assertIn("not limited to", r_all["note"])
        self.assertIn("note", self.c.get("/api/advisor/sections?q=ZQTS 410").json())  # old default: every term, flagged
        empty = self.c.get("/api/advisor/sections?q=ZQTS 999&term=NEXT").json()
        self.assertEqual(empty["sections"], [])
        self.assertIn("term=all", empty["note"])

        with mock.patch.object(mcp_server, "call", return_value={}) as call:
            mcp_server.BY_NAME["search_sections"][2]({"query": "CSCI 150"})
            self.assertIn("term=next", call.call_args.args[1])
            mcp_server.BY_NAME["search_sections"][2]({"query": "CSCI 150", "term": "all"})
            self.assertIn("term=all", call.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
