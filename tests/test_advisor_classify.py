"""Tests for course classification, hash matching, whitelist filtering, and degree audit earned vs likely separation."""
import asyncio
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from test_lab import LOCAL, server  # sets up temporary data folder and offline mode
import advisor
import advisor_classifier
import db
from fastapi.testclient import TestClient


class AdvisorClassify(unittest.TestCase):
    def setUp(self):
        db.init_db()
        advisor.init()
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()
        self.user = self.c.post("/api/users", json={"name": f"Auditor {uuid.uuid4().hex[:6]}"}).json()
        self.uid = self.user.get("id") or self.user["user"]["id"]

    def tearDown(self):
        server.AUTH_REQUIRED = False
        self.ctx.__exit__(None, None, None)

    def test_db_migration_and_schema_columns(self):
        cols = {r["name"] for r in db.conn().execute("PRAGMA table_info(catalog_courses)")}
        self.assertIn("inferred_attributes", cols)
        self.assertIn("inferred_hash", cols)

    def test_upsert_courses_preserves_inferred_tags(self):
        code = f"HIST {200 + (abs(hash(uuid.uuid4().hex)) % 500)}"
        advisor.upsert_courses([{"code": code, "title": "Initial History", "credits": "3"}], "test")
        advisor.save_inferred_attributes([{"code": code, "inferred_attributes": ["CSI", "COLL 200"], "inferred_hash": "hash123"}])

        c1 = advisor.get_course(code)
        self.assertIsNotNone(c1)
        self.assertEqual(c1["inferred_attributes"], ["CSI", "COLL 200"])
        self.assertEqual(c1["inferred_hash"], "hash123")

        # Now upsert official catalog update without inferred attributes
        advisor.upsert_courses([{"code": code, "title": "Updated History Title", "credits": "4"}], "official_import")

        c2 = advisor.get_course(code)
        self.assertIsNotNone(c2)
        self.assertEqual(c2["title"], "Updated History Title")
        self.assertEqual(c2["credits"], "4")
        self.assertEqual(c2["inferred_attributes"], ["CSI", "COLL 200"])
        self.assertEqual(c2["inferred_hash"], "hash123")

    def test_effective_attributes(self):
        c = {
            "code": "HIST S150",
            "title": "Freshman Seminar",
            "attributes": ["CSI"],
            "inferred_attributes": ["ALV"],
        }
        eff = advisor.effective_attributes(c)
        self.assertEqual(eff["official"], ["CSI"])
        self.assertEqual(eff["by_number"], ["COLL 150"])
        self.assertEqual(eff["ai"], ["ALV"])

    def test_hash_matching_and_filtering(self):
        course = {"code": "DATA 101", "title": "Intro to Data", "description": "Basics", "prereqs": "None"}
        h1 = advisor.compute_course_content_hash(course)
        course_changed = {"code": "DATA 101", "title": "Intro to Data Science", "description": "Basics", "prereqs": "None"}
        h2 = advisor.compute_course_content_hash(course_changed)
        self.assertNotEqual(h1, h2)

        advisor.upsert_courses([{"code": "DATA 101", "title": "Intro to Data", "description": "Basics", "prereqs": "None"}], "test")
        advisor.save_inferred_attributes([{"code": "DATA 101", "inferred_attributes": ["NQR"], "inferred_hash": h1}])

        # Should skip DATA 101 since hash matches
        candidates = advisor_classifier.get_courses_to_classify(depts=["DATA"], limit=10, force=False)
        self.assertNotIn("DATA 101", [c["code"] for c in candidates])

        # Should include DATA 101 when force=True
        candidates_forced = advisor_classifier.get_courses_to_classify(depts=["DATA"], limit=10, force=True)
        self.assertIn("DATA 101", [c["code"] for c in candidates_forced])

    def test_whitelist_filtering(self):
        self.assertEqual(advisor_classifier.ALLOWED_ATTRIBUTES, {"ALV", "CSI", "NQR", "COLL 200", "COLL 300", "MATH", "ARTS"})
        code = f"SOC {200 + (abs(hash(uuid.uuid4().hex)) % 500)}"
        advisor.upsert_courses([{"code": code, "title": "Sociology Topic", "description": "Study of society"}], "test")

        async def fake_model(prompt):
            return [{"code": code, "attributes": ["CSI", "COLL 200", "BOGUS_ATTRIBUTE", "INVALID"]}]

        res = asyncio.run(advisor_classifier.classify_catalog_courses(
            depts=[code.split()[0]],
            dry_run=False,
            call_json_fn=fake_model,
        ))
        saved = advisor.get_course(code)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["inferred_attributes"], ["CSI", "COLL 200"])
        self.assertNotIn("BOGUS_ATTRIBUTE", saved["inferred_attributes"])

    def test_dry_run_behavior(self):
        code = f"CSCI {200 + (abs(hash(uuid.uuid4().hex)) % 500)}"
        advisor.upsert_courses([{"code": code, "title": "Graphics"}], "test")

        async def fake_model(prompt):
            return [{"code": code, "attributes": ["NQR"]}]

        # dry_run = True -> returns update, but does NOT write to database
        res_dry = asyncio.run(advisor_classifier.classify_catalog_courses(
            depts=[code.split()[0]],
            dry_run=True,
            call_json_fn=fake_model,
        ))
        self.assertTrue(res_dry["dry_run"])
        c_after_dry = advisor.get_course(code)
        self.assertIsNotNone(c_after_dry)
        self.assertEqual(c_after_dry["inferred_attributes"], [])

        # dry_run = False -> writes to database
        res_live = asyncio.run(advisor_classifier.classify_catalog_courses(
            depts=[code.split()[0]],
            dry_run=False,
            call_json_fn=fake_model,
        ))
        self.assertFalse(res_live["dry_run"])
        c_after_live = advisor.get_course(code)
        self.assertIsNotNone(c_after_live)
        self.assertEqual(c_after_live["inferred_attributes"], ["NQR"])

    def test_degree_audit_separation_earned_vs_likely(self):
        soc_code = f"SOC {200 + (abs(hash(uuid.uuid4().hex)) % 500)}"
        advisor.upsert_courses([
            {"code": soc_code, "title": "Social Inquiry", "credits": "3"},
            {"code": "HIST 100", "title": "History Seminar", "credits": "4"},
        ], "test")
        advisor.save_inferred_attributes([{"code": soc_code, "inferred_attributes": ["COLL 200", "CSI"], "inferred_hash": "hash"}])

        advisor.add_completed(self.uid, [
            {"code": soc_code, "grade": "A"},
            {"code": "HIST 100", "grade": "A"},
        ], "test")

        audit = advisor.degree_audit(self.uid)

        # COLL 100 met via official by-number
        self.assertEqual(audit["coll"]["coll100"]["earned"], 4.0)
        self.assertTrue(audit["coll"]["coll100"]["met"])
        self.assertEqual(audit["coll"]["coll100"]["likely"], 0)

        # COLL 200: earned is 0, met is False, but likely is 3.0 and likely_courses contains soc_code
        self.assertEqual(audit["coll"]["coll200"]["earned"], 0.0)
        self.assertFalse(audit["coll"]["coll200"]["met"])
        self.assertEqual(audit["coll"]["coll200"]["likely"], 3.0)
        self.assertEqual(audit["coll"]["coll200"]["likely_courses"], [soc_code])
        self.assertFalse(audit["all_coll_met"])

    def test_classify_and_chat_endpoints(self):
        # Classify endpoint
        r = self.c.post("/api/advisor/classify", json={"dry_run": True, "limit": 10})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "started")
        self.assertTrue(r.json()["dry_run"])

        r_cat = self.c.post("/api/advisor/catalog/classify", json={"dry_run": True, "limit": 10})
        self.assertEqual(r_cat.status_code, 200)

        # Chat alias and suggested_courses
        advisor.upsert_courses([{"code": "CSCI 241", "title": "Data Structures", "credits": "3"}], "test")

        async def fake_gemini(contents, role=None, **kw):
            return SimpleNamespace(text="You should take CSCI 241 next semester.")

        with mock.patch.object(server, "acall_gemini", side_effect=fake_gemini):
            r_chat = self.c.post(f"/api/advisor/{self.uid}/chat", json={"message": "What should I take?"})
            self.assertEqual(r_chat.status_code, 200)
            data = r_chat.json()
            self.assertIn("CSCI 241", data["courses"])
            self.assertEqual(len(data["suggested_courses"]), 1)
            self.assertEqual(data["suggested_courses"][0]["code"], "CSCI 241")
            self.assertEqual(data["suggested_courses"][0]["title"], "Data Structures")


    def test_prereq_cnf_minimum_grade_clause(self):
        cnf = advisor.parse_prereq_cnf("CSCI 141 (A minimum grade of C-) and (MATH 111 or MATH 131)")
        self.assertEqual(len(cnf), 2)
        self.assertIn(["CSCI 141"], cnf)
        self.assertIn(["MATH 111", "MATH 131"], cnf)

    def test_classify_deduplication(self):
        server.JOBS["test-classify-job"] = {
            "id": "test-classify-job",
            "kind": "classify_catalog",
            "status": "running",
            "created": 123456789.0,
        }
        try:
            r = self.c.post("/api/advisor/classify", json={"dry_run": True, "limit": 10})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["job_id"], "test-classify-job")
            self.assertIn("already in progress", r.json().get("message", ""))
        finally:
            server.JOBS.pop("test-classify-job", None)


if __name__ == "__main__":
    unittest.main()
