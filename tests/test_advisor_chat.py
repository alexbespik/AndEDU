"""Advisor: COLL 100/150 by course number, and the advisor chat (context and route). Never calls Gemini."""
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from test_lab import LOCAL, server  # noqa: E402  (sets up the temporary data folder and offline Gemini)
import advisor  # noqa: E402
import advisor_chat  # noqa: E402
import wm_advising  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class CollByNumber(unittest.TestCase):
    def test_100_and_150_count_with_suffixes(self):
        self.assertEqual(advisor.coll_by_number("HIST 150W"), "COLL 150")
        self.assertEqual(advisor.coll_by_number("BIOL 100"), "COLL 100")
        for code in ("COLL 150", "ZQTS 241", "MATH 1500", "ENGL 200"):
            self.assertIsNone(advisor.coll_by_number(code), code)

    def test_degree_audit_counts_them_once(self):
        user = server.db.get_or_create_user(f"Coll {uuid.uuid4().hex[:6]}")["id"]
        advisor.upsert_courses([{"code": "HIST 150W", "title": "First-Year Seminar", "credits": "4", "attributes": ["COLL 150"]},
                                {"code": "BIOL 100", "title": "Big Ideas in Biology", "credits": "4"}], "test")
        advisor.add_completed(user, [{"code": "HIST 150W", "grade": "A"}, {"code": "BIOL 100", "grade": "B"}], "test")
        audit = advisor.degree_audit(user)
        self.assertEqual((audit["coll"]["coll150"]["earned"], audit["coll"]["coll150"]["met"]), (4.0, True))
        self.assertEqual((audit["coll"]["coll100"]["earned"], audit["coll"]["coll100"]["courses"]), (4.0, ["BIOL 100"]))


class AdvisorChat(unittest.TestCase):
    def setUp(self):
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        self.user = self.c.post("/api/users", json={"name": f"Chat {uuid.uuid4().hex[:6]}"}).json()
        self.uid = self.user.get("id") or self.user["user"]["id"]
        advisor.upsert_courses([{"code": "ZQTS 303", "title": "Algorithms", "credits": "3", "prereqs": "ZQTS 241"},
                                {"code": "ZQTS 241", "title": "Data Structures", "credits": "3"}], "test")
        advisor.add_completed(self.uid, [{"code": "ZQTS 241", "grade": "B"}], "test")

    def tearDown(self):
        server.AUTH_REQUIRED = False
        self.ctx.__exit__(None, None, None)

    def test_context_holds_record_audit_and_asked_course(self):
        ctx = advisor_chat.build_context(self.uid, "Can I take ZQTS 303 next fall?")
        self.assertIn("ZQTS 241", ctx)
        self.assertIn("DEGREE AUDIT", ctx)
        self.assertIn("ZQTS 303: Algorithms", ctx)
        self.assertIn("student's prerequisites: met", ctx)
        self.assertIn("WILLIAM & MARY ACADEMIC REGULATIONS & ADVISING POLICIES", ctx)
        self.assertIn("14–16 credits", ctx)
        self.assertIn("COLL 100 in one semester and COLL 150 in the other", ctx)
        self.assertIn("39 earned credits", ctx)
        self.assertLessEqual(len(advisor_chat.build_context(self.uid, "x " * 5000)), advisor_chat.MAX_CONTEXT + 40)

    def test_advising_major_roadmaps_and_milestones(self):
        import wm_advising
        audit = {"total_credits": 15.0, "coll": {"coll100": {"met": False}, "coll150": {"met": False}}, "proficiencies": {}}
        ctx_freshman = wm_advising.get_relevant_advising_context(self.uid, audit, "How do I plan for a computer science major?")
        self.assertIn("Year 1 Status", ctx_freshman)
        self.assertIn("Computer Science (B.S.)", ctx_freshman)
        self.assertIn("CSCI 141", ctx_freshman)
        self.assertIn("CSCI 241", ctx_freshman)

        audit_sophomore = {"total_credits": 42.0, "coll": {"coll100": {"met": True}, "coll150": {"met": True}}, "proficiencies": {"math": {"met": False}}}
        ctx_soph = wm_advising.get_relevant_advising_context(self.uid, audit_sophomore, "Can I apply to the business school?")
        self.assertIn("Sophomore Status", ctx_soph)
        self.assertIn("Business (Mason School of Business B.B.A.)", ctx_soph)
        self.assertIn("BUAD 203", ctx_soph)
        self.assertIn("Mathematics Proficiency Warning", ctx_soph)

        ctx_premed = wm_advising.get_relevant_advising_context(self.uid, audit, "What classes should I take for pre-med?")
        self.assertIn("Pre-Med / Pre-Health Pathway", ctx_premed)
        self.assertIn("CHEM 103", ctx_premed)
        self.assertIn("BIOL 203", ctx_premed)

    def test_route_sends_data_as_system_prompt_and_returns_reply(self):
        seen = {}

        async def fake(contents, role=None, **kw):
            seen["system"], seen["role"], seen["turns"] = kw["config"].system_instruction, role, len(contents)
            return SimpleNamespace(text="Yes: you have ZQTS 241, so ZQTS 303 is open to you.")

        with mock.patch.object(server, "acall_gemini", side_effect=fake):
            r = self.c.post(f"/api/advisor/{self.uid}/ask", json={
                "message": "Can I take ZQTS 303?", "history": [{"role": "user", "content": "hi"}, {"role": "advisor", "content": "Hello"}]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["courses"], ["ZQTS 241", "ZQTS 303"])
        self.assertIn("<<<DATA", seen["system"])
        self.assertIn("ZQTS 303: Algorithms", seen["system"])
        self.assertEqual((seen["role"], seen["turns"]), ("planner", 3))

    def test_errors_are_reported_not_empty(self):
        self.assertEqual(self.c.post(f"/api/advisor/{self.uid}/ask", json={"message": "  "}).status_code, 400)
        r = self.c.post(f"/api/advisor/{self.uid}/ask", json={"message": "What next?"})  # offline model -> 503 with a reason
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.json()["detail"])

    def test_accounts_mode_blocks_other_students_record(self):
        server.AUTH_REQUIRED = True
        tok = self.c.post("/api/auth/register", json={"name": f"Eve {uuid.uuid4().hex[:6]}", "password": "correct horse battery",
                                                       "adult": True, "privacy": True}).json()["token"]
        r = self.c.post(f"/api/advisor/{self.uid}/ask", json={"message": "What did they take?"},
                        headers={"Authorization": f"Bearer {tok}"})
        self.assertEqual(r.status_code, 403)

    def test_max_context_and_syllabus_injection(self):
        self.assertEqual(advisor_chat.MAX_CONTEXT, 60000)
        c = {"code": "MATH 211", "title": "Linear Algebra", "description": "Vectors and matrices.", "syllabus": "Week 1: Systems of equations."}
        full_line = advisor_chat._course_line(c, full=True)
        self.assertIn("syllabus: Week 1: Systems of equations.", full_line)
        self.assertIn("Vectors and matrices.", full_line)
        short_line = advisor_chat._course_line(c, full=False)
        self.assertNotIn("syllabus:", short_line)

    def test_wm_policies_and_expanded_major_roadmaps(self):
        import wm_advising
        for policy in [
            "Academic Continuance",
            "Two-Course Overlap Rule",
            "48-Credit Department Cap",
            "10-Semester Limit",
            "Course Repeat Policy",
            "COLL 200 In-Residence Rule",
        ]:
            self.assertIn(policy, wm_advising.WM_CORE_POLICIES)

        new_majors = [
            "mathematics", "chemistry", "physics", "english",
            "history", "neuroscience", "environmental_science", "public_policy"
        ]
        for m in new_majors:
            self.assertIn(m, wm_advising.MAJOR_ROADMAPS)

        audit = {"total_credits": 20.0, "coll": {}, "proficiencies": {}}
        physics_ctx = wm_advising.get_relevant_advising_context(self.uid, audit, "Tell me about the physics major")
        self.assertIn("Physics (B.S. / B.A.)", physics_ctx)
        self.assertIn("PHYS 101", physics_ctx)

        math_ctx = wm_advising.get_relevant_advising_context(self.uid, audit, "What is the math pathway?")
        self.assertIn("Mathematics (B.S. / B.A.)", math_ctx)
        self.assertIn("MATH 214", math_ctx)

    def test_mcp_advisor_tools_registered(self):
        import mcp_server
        tool_names = set(mcp_server.BY_NAME.keys())
        expected = {
            "search_sections",
            "get_prerequisite_tree",
            "check_major_requirements",
            "get_student_degree_audit",
            "get_student_readiness",
            "list_completed_courses",
            "add_completed_course",
            "ask_advisor",
        }
        self.assertTrue(expected.issubset(tool_names), f"Missing tools: {expected - tool_names}")

    def test_xp_rebalance_and_caps(self):
        import engage
        self.assertEqual(engage.SOURCES["quiz_correct"], (8, "day"))
        self.assertEqual(engage.SOURCES["class_complete"], (25, "ever"))
        self.assertEqual(engage.SOURCES["quiz_perfect"], (15, "ever"))
        self.assertEqual(engage.SOURCES["practice_correct"], (5, ("cap", 20)))
        self.assertEqual(engage.SOURCES["math_correct"], (5, ("cap", 20)))
        self.assertEqual(engage.SOURCES["review_correct"], (8, "day"))
        self.assertEqual(engage.SOURCES["review_session"], (10, ("cap", 2)))
        self.assertEqual(engage.SOURCES["ide_solved"], (20, "ever"))
        self.assertEqual(engage.SOURCES["sim_explored"], (3, ("cap", 5)))
        self.assertEqual(engage.SOURCES["lesson_read"], (2, ("cap", 10)))
        self.assertEqual(engage.SOURCES["quests_bonus"], (20, "day"))
        self.assertEqual(engage.CLIENT_DAILY_CAP, 40)

        # Verify daily cap on practice_correct
        day = "2026-12-01"
        u = server.db.get_or_create_user(f"CapTester-{uuid.uuid4().hex[:6]}")["id"]
        for i in range(20):
            res = engage.award(u, day, "practice_correct", f"q_{i}")
            base_xp = res["xp"] - (engage.SOURCES["quests_bonus"][0] if res.get("questsDone") else 0)
            self.assertEqual(base_xp, 5, f"Expected 5 XP for item {i}")
        # 21st attempt with new ref hits daily cap
        over_cap = engage.award(u, day, "practice_correct", "q_20")
        self.assertEqual(over_cap["xp"], 0)
        # duplicate ref on same day gets 0
        dup = engage.award(u, day, "practice_correct", "q_0")
        self.assertEqual(dup["xp"], 0)

    def test_stoic_topic_expansion_without_cs_dumping(self):
        # Student with CS history asks about Stoic philosophy
        user = server.db.get_or_create_user(f"StoicStudent-{uuid.uuid4().hex[:6]}")["id"]
        advisor.upsert_courses([
            {"code": "CSCI 141", "title": "Modern Programming", "credits": "4"},
            {"code": "CSCI 241", "title": "Data Structures", "credits": "3", "prereqs": "CSCI 141"},
            {"code": "CSCI 243", "title": "Discrete Structures", "credits": "3", "prereqs": "CSCI 141"},
            {"code": "PHIL 231", "title": "Greek Philosophy", "credits": "3", "description": "Ancient Greek and Roman thinkers, Epictetus, Seneca, Stoic philosophy."},
            {"code": "PHIL 303", "title": "Ethics", "credits": "3", "description": "Moral theory, virtue ethics, and stoicism."},
            {"code": "CLCV 208", "title": "Roman Culture", "credits": "3", "description": "Life in ancient Rome, Marcus Aurelius, and stoic principles."},
        ], "test")
        advisor.add_completed(user, [{"code": "CSCI 141", "grade": "A"}, {"code": "CSCI 241", "grade": "A"}], "test")

        # 1. Topic expansions mapping exists
        self.assertIn("stoic", advisor_chat.TARGET_DEPARTMENTS)
        self.assertIn("PHIL", advisor_chat.TARGET_DEPARTMENTS["stoic"])
        self.assertIn("CLCV", advisor_chat.TARGET_DEPARTMENTS["stoic"])

        # 2. Context detects topic interest and injects matching courses
        ctx = advisor_chat.build_context(user, "Are there any courses on Stoic philosophy?")
        self.assertIn("COURSES MATCHING STUDENT'S TOPIC INTEREST:", ctx)
        self.assertTrue("PHIL 231" in ctx or "PHIL 303" in ctx or "CLCV 208" in ctx)

        # 3. De-biased recommend ranks topical courses high instead of drowning in CS continuation
        recs = advisor.recommend(user, "stoic philosophy", limit=5)
        rec_codes = [c["code"] for c in recs]
        self.assertTrue(any(c.startswith("PHIL") or c.startswith("CLCV") for c in rec_codes))
        # Top course should be a philosophy/classics course matching the topic, not CSCI
        self.assertTrue(rec_codes[0].startswith("PHIL") or rec_codes[0].startswith("CLCV"))

    def test_student_notes_persistence_and_context_injection(self):
        user = server.db.get_or_create_user(f"NotesStudent-{uuid.uuid4().hex[:6]}")["id"]
        notes = "Interested in Marcus Aurelius Meditations and Epictetus Enchiridion."
        saved = server.db.save_student_notes(user, notes)
        self.assertEqual(saved["notes_text"], notes)
        self.assertEqual(server.db.get_student_notes(user), notes)

        ctx = advisor_chat.build_context(user, "What should I take?")
        self.assertIn("STUDENT'S WRITTEN NOTES & SCRATCHPAD:", ctx)
        self.assertIn("Marcus Aurelius Meditations", ctx)

    def test_schedule_conflicts_detection(self):
        c1 = {"code": "PHIL 231", "meeting_times": [{"meet_day": "1", "start_time": "1100", "end_time": "1220"}]}
        c2 = {"code": "CSCI 241", "meets": "TR 11:30-12:50p"}
        c3 = {"code": "MATH 111", "meets": "MWF 9-9:50a"}
        conflicts = wm_advising.check_schedule_conflicts([c1, c2, c3])
        self.assertEqual(len(conflicts), 1)
        self.assertTrue(conflicts[0]["conflict"])
        self.assertEqual(conflicts[0]["day"], "T")
        self.assertIn(conflicts[0]["course_a"], ("PHIL 231", "CSCI 241"))
        self.assertIn(conflicts[0]["course_b"], ("PHIL 231", "CSCI 241"))

    def test_launch_course_creates_a_studio_course_and_links_the_cart(self):
        advisor.upsert_courses([{"code": "PHIL 205", "title": "Meaning in Life", "credits": "3", "prereqs": "none"}], "test")
        term = wm_advising.next_term()
        self.assertEqual(self.c.post(f"/api/advisor/{self.uid}/cart", json={"code": "PHIL 205", "term": term}).status_code, 200)
        launch_res = self.c.post(f"/api/advisor/{self.uid}/launch-course", json={"code": "PHIL 205", "term": term})
        self.assertEqual(launch_res.status_code, 200, launch_res.text)
        body = launch_res.json()
        self.assertIn("redirect_url", body)
        self.assertEqual(server.db.get_course(body["course_id"])["user_id"], self.uid)
        self.assertEqual(self.c.get(f"/api/advisor/{self.uid}/semester-plan").status_code, 404)  # the Auto-Plan is gone
        item = self.c.get(f"/api/advisor/{self.uid}/cart?term={term}").json()["items"][0]
        self.assertEqual(item["studio_course_id"], body["course_id"])


if __name__ == "__main__":
    unittest.main()
