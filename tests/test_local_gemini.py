"""Accounts on this computer, phase 3 (docs/plans/ACCOUNTS.md): every model call spends the key of the signed-in account
(or of the job's owner), with cooldowns, grounding pause, invalid flag and daily budget per key; jobs hold a lease on
their owner's key, so a lock mid-job finishes on it within the grace; nothing resumes at boot until its owner signs in;
a missing key answers with a JSON `code`."""
from test_lab import LOCAL, TestClient, server, db, engage  # noqa: F401  (sets up the temp content dir first)

import asyncio
import threading
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from google.genai.errors import ClientError

import userkeys
from local_accounts import LocalAccountsCase, local_account

INVALID = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                     "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}
QUOTA = {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}}


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    engage.init()


class FakeClient:
    """A Gemini client for one key: answers "ok:<key>" unless `fail` (a ClientError body and code) is set."""
    def __init__(self, key):
        self.key, self.calls, self.fail = key, [], None
        self.models = SimpleNamespace(generate_content=self.generate_content)

    def generate_content(self, model, contents, **kw):
        self.calls.append(model)
        if self.fail:
            raise ClientError(*self.fail)
        return SimpleNamespace(text=f"ok:{self.key}")


class LocalGeminiBase(LocalAccountsCase):
    def setUp(self):
        super().setUp()
        self.clients = {}
        userkeys.client_factory = lambda key: self.clients.setdefault(key, FakeClient(key))
        # the env key's client and state must never be touched in local mode
        self.env = mock.patch.multiple(server, client=None, MODEL_COOLDOWN={}, GROUNDING_PAUSED_UNTIL=0.0,
                                       GEMINI_KEY_INVALID=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.tag = uuid.uuid4().hex[:6]
        self.alice_h, self.alice = local_account(f"Alice {self.tag}")
        self.bob_h, self.bob = local_account(f"Bob {self.tag}")
        self.unlock(self.alice, f"alice-key-{self.tag}")
        self.unlock(self.bob, f"bob-key-{self.tag}")

    def unlock(self, uid, key):
        """The account's key stored (device mode) and unlocked, as after a sign-in."""
        server._store_key(uid, key, "device", None, key[-4:])
        server._unlock_entry(uid, None)["key"] = key
        userkeys.handle_for(uid)

    def call(self, uid):
        token = server.CURRENT_USER.set(db.get_user(uid))
        try:
            return server._real_call_gemini("Hello", role="lesson")
        except Exception as e:  # noqa: BLE001
            return e
        finally:
            server.CURRENT_USER.reset(token)

    def state(self, uid):
        return userkeys.KEY_STATE[userkeys.handle_for(uid).key_id]

    def assert_env_untouched(self):
        self.assertIsNone(server.client)
        self.assertEqual((server.MODEL_COOLDOWN, server.GROUNDING_PAUSED_UNTIL, server.GEMINI_KEY_INVALID), ({}, 0.0, False))


class PerKeyCalls(LocalGeminiBase):
    def test_each_account_calls_with_its_own_client(self):
        with mock.patch.dict(server.os.environ, {"GEMINI_API_KEY": "env-key"}):
            self.assertEqual(self.call(self.alice).text, f"ok:alice-key-{self.tag}")
            self.assertEqual(self.call(self.bob).text, f"ok:bob-key-{self.tag}")
        self.assertEqual(set(self.clients), {f"alice-key-{self.tag}", f"bob-key-{self.tag}"})
        self.assert_env_untouched()  # trap 2: the env key is never read in local mode

    def test_no_unlocked_key_is_no_gemini_key(self):
        userkeys.forget(self.alice)
        self.assertIsInstance(self.call(self.alice), userkeys.NoGeminiKey)
        self.assertEqual(server.friendly_ai_error(userkeys.NoGeminiKey()), "Add your Gemini key in the account menu.")
        self.assertEqual(server.friendly_ai_error(userkeys.KeyLocked()), "Sign in again to continue.")

    def test_cooldown_and_grounding_pause_are_per_key(self):
        self.call(self.bob)
        self.clients[f"alice-key-{self.tag}"].fail = (429, QUOTA)
        self.assertIsInstance(self.call(self.alice), ClientError)
        alice, bob = self.state(self.alice), self.state(self.bob)
        self.assertTrue(alice["cooldown"])
        self.assertGreater(alice["grounding_paused_until"], time.time())
        self.assertEqual((bob["cooldown"], bob["grounding_paused_until"]), ({}, 0.0))
        self.assertEqual(self.call(self.bob).text, f"ok:bob-key-{self.tag}")
        self.assert_env_untouched()

    def test_rejected_key_is_per_key_and_its_event_goes_to_the_owner_only(self):
        self.clients[f"alice-key-{self.tag}"].fail = (400, INVALID)
        seq = server._event_seq
        err = self.call(self.alice)
        self.assertIn("rejected the Gemini API key", str(err))
        self.assertEqual(len(self.clients[f"alice-key-{self.tag}"].calls), 1)  # no fallback models
        self.assertEqual(server.friendly_ai_error(err), "Google rejected your Gemini key. Add a working key in the account menu.")
        self.assertTrue(self.state(self.alice)["invalid"])
        self.assertEqual(self.call(self.bob).text, f"ok:bob-key-{self.tag}")
        self.assertFalse(self.state(self.bob)["invalid"])
        events = [e for e in server.ui_events_queue if e["seq"] > seq and e["type"] == "GEMINI_KEY_INVALID"]
        self.assertEqual([e["owner"] for e in events], [self.alice])
        self.assert_env_untouched()
        with TestClient(server.app, base_url=LOCAL) as c:
            seen = {who: [e["type"] for e in c.get(f"/api/agy/events?since={seq}", headers=h).json()["events"]]
                    for who, h in (("alice", self.alice_h), ("bob", self.bob_h))}
            me = c.get("/api/auth/me", headers=self.alice_h).json()
            status = c.get("/api/status").json()
        self.assertIn("GEMINI_KEY_INVALID", seen["alice"])
        self.assertNotIn("GEMINI_KEY_INVALID", seen["bob"])
        self.assertEqual((me["keyState"], me["keyInvalid"]), ("ok", True))
        self.assertEqual((status["gemini_configured"], status["gemini_key_invalid"]), (False, False))  # trap 6

    def test_daily_budget_is_per_key(self):
        env_used = dict(server._budget)
        with mock.patch.object(server, "DAILY_MODEL_CALLS", 2):
            self.call(self.alice), self.call(self.alice)
            self.assertIn("Daily model budget reached", str(self.call(self.alice)))
            self.assertEqual(self.call(self.bob).text, f"ok:bob-key-{self.tag}")
        self.assertEqual(self.state(self.alice)["budget"]["used"], 2)
        self.assertEqual(server._budget, env_used)

    def test_two_accounts_with_the_same_key_share_its_state(self):
        self.unlock(self.bob, f"alice-key-{self.tag}")
        self.call(self.alice)
        self.assertIs(self.state(self.alice), self.state(self.bob))
        self.clients[f"alice-key-{self.tag}"].fail = (400, INVALID)
        seq = server._event_seq
        self.call(self.alice)
        owners = {e["owner"] for e in server.ui_events_queue if e["seq"] > seq and e["type"] == "GEMINI_KEY_INVALID"}
        self.assertEqual(owners, {self.alice, self.bob})  # everyone holding the key is asked for a new one

    def test_missing_key_answers_json_with_a_code(self):
        server.save_json_file(server.topic_path(f"local-gemini-{self.tag}"),
                              {"id": f"local-gemini-{self.tag}", "title": "Waves", "category": "Physics",
                               "markdownContent": "# Waves"})
        userkeys.forget(self.alice)
        with mock.patch.object(server, "call_gemini", server._real_call_gemini), \
                TestClient(server.app, base_url=LOCAL) as c:
            r = c.post("/api/tutor/lesson", json={"topicId": f"local-gemini-{self.tag}", "message": "hi", "mode": "brief"},
                       headers=self.alice_h)
            self.assertEqual((r.status_code, r.json()), (409, {"detail": "Add your Gemini key in the account menu.",
                                                               "code": "gemini_key_missing"}))
            r = c.post("/api/tutor/lesson", json={"topicId": f"local-gemini-{self.tag}", "message": "hi", "mode": "brief"},
                       headers=self.bob_h)
            self.assertEqual((r.status_code, r.json()["reply"]), (200, f"ok:bob-key-{self.tag}"))


class KeyErrorsReachTheUI(LocalGeminiBase):
    """Endpoints that fall back to canned answers when the model fails still answer a missing key with the 409 code."""
    BODIES = {
        "/api/tutor-brief": {"problem": {"title": "Loops", "description": "Sum a list"}},
        "/api/tutor/explain-answer": {"question": "2+2?", "student_answer": "5", "correct_answer": "4"},
        "/api/language/roleplay": {"scenario": "cafe", "target_lang": "de", "user_message": "Hallo"},
    }

    def test_missing_key_is_not_swallowed_by_fallbacks(self):
        userkeys.forget(self.alice)
        with mock.patch.object(server, "call_gemini", server._real_call_gemini), \
                TestClient(server.app, base_url=LOCAL) as c:
            for path, body in self.BODIES.items():
                with self.subTest(path=path):
                    r = c.post(path, json=body, headers=self.alice_h)
                    self.assertEqual((r.status_code, r.json().get("code")), (409, "gemini_key_missing"), r.text)
                    r = c.post(path, json=body, headers=self.bob_h)
                    self.assertEqual(r.status_code, 200, r.text)  # with a key, the same request works
            me = c.get("/api/auth/me", headers=self.bob_h).json()
            status = c.get("/api/status").json()
        self.assertGreater(len(self.clients[f"bob-key-{self.tag}"].calls), 0)
        self.assertEqual(me["modelCallsLeft"], server.DAILY_MODEL_CALLS - len(self.clients[f"bob-key-{self.tag}"].calls))
        self.assertIsNone(status["model_calls_left_today"])


class JobLeases(LocalGeminiBase):
    async def wait(self, job, timeout=5.0):
        end = time.time() + timeout
        while job["status"] not in ("done", "error"):
            if time.time() > end:
                raise AssertionError(f"job still {job['status']}")
            await asyncio.sleep(0.01)
        return job

    def run_job(self, owner, lock_mid_job=False, then_job=False, meanwhile=None):
        """Starts a job for `owner` that waits, then calls the model; locks the account meanwhile if asked (or runs
        `meanwhile()` as the owner). With then_job, the job's `then` queues a second one (as the course loop's
        requeue does)."""
        jobs = []

        async def scenario():
            gate = asyncio.Event()

            async def work(job):
                await gate.wait()
                return server._real_call_gemini("Hello").text

            async def second(job):
                return server._real_call_gemini("Again").text

            server.CURRENT_USER.set(db.get_user(owner))  # asyncio.run's own context: nothing leaks out
            jobs.append(server.start_job("test", "Lease test", work,
                                         then=(lambda: jobs.append(server.start_job("test", "Chained", second))) if then_job else None))
            await asyncio.sleep(0)
            if lock_mid_job:
                server.lock_account(owner)
            if meanwhile:
                meanwhile()
            gate.set()
            await self.wait(jobs[0])
            if then_job:
                await asyncio.sleep(0)
                await self.wait(jobs[1])
        asyncio.run(scenario())
        self.addCleanup(lambda: [server.JOBS.pop(j["id"], None) for j in jobs])
        return jobs

    def test_a_job_runs_on_its_owners_key(self):
        job, = self.run_job(self.alice, lock_mid_job=False)
        self.assertEqual((job["status"], job["result"]), ("done", f"ok:alice-key-{self.tag}"))

    def test_lock_mid_job_finishes_on_the_lease(self):
        handle = userkeys.handle_for(self.alice)
        job, = self.run_job(self.alice, lock_mid_job=True)
        self.assertEqual((job["status"], job["result"]), ("done", f"ok:alice-key-{self.tag}"))
        self.assertNotIn(self.alice, userkeys.UNLOCKED)
        self.assertIsNotNone(handle.revoked_at)

    def test_after_the_grace_the_job_fails_with_key_locked(self):
        with mock.patch.object(userkeys, "KEY_LEASE_GRACE_S", -1):
            job, = self.run_job(self.alice, lock_mid_job=True)
        self.assertEqual((job["status"], job["error"]), ("error", "Sign in again to continue."))

    def test_signing_in_again_lets_a_locked_job_go_on_with_the_fresh_key(self):
        handle = userkeys.handle_for(self.alice)
        userkeys.forget(self.alice)
        handle.revoked_at = time.time() - userkeys.KEY_LEASE_GRACE_S - 1
        self.assertRaises(userkeys.KeyLocked, userkeys.usable, handle)
        self.unlock(self.alice, f"alice-key-{self.tag}")
        self.assertEqual(userkeys.usable(handle).key_id, handle.key_id)

    def test_chained_job_uses_the_owners_key_after_a_lock(self):
        first, chained = self.run_job(self.alice, lock_mid_job=True, then_job=True)
        self.assertEqual(first["result"], f"ok:alice-key-{self.tag}")
        self.assertEqual((chained["status"], chained["owner"], chained["result"]),
                         ("done", self.alice, f"ok:alice-key-{self.tag}"))
        self.assertEqual(len(self.clients[f"alice-key-{self.tag}"].calls), 2)
        self.assertEqual(self.clients[f"bob-key-{self.tag}"].calls, [])  # bob's key never came into it

    def test_deleting_the_key_mid_job_stops_it_at_the_next_call(self):
        job, = self.run_job(self.alice, meanwhile=server.delete_my_gemini_key)
        self.assertEqual((job["status"], job["error"]), ("error", "Add your Gemini key in the account menu."))
        self.assertEqual(self.clients[f"alice-key-{self.tag}"].calls, [])

    def test_deleting_the_account_mid_job_stops_it_at_the_next_call(self):
        job, = self.run_job(self.alice, meanwhile=lambda: userkeys.forget(self.alice, hard=True))
        self.assertEqual(job["status"], "error")
        self.assertEqual(self.clients[f"alice-key-{self.tag}"].calls, [])

    def test_a_replaced_key_mid_job_carries_on_with_the_new_key(self):
        def replace():
            with mock.patch.object(userkeys, "check_key", return_value="ok"):
                server.put_my_gemini_key(server.GeminiKeyRequest(key=f"alice-new-key-{self.tag}"))
        job, = self.run_job(self.alice, meanwhile=replace)
        self.assertEqual((job["status"], job["result"]), ("done", f"ok:alice-new-key-{self.tag}"))
        self.assertEqual(self.clients[f"alice-key-{self.tag}"].calls, [])

    def test_job_without_a_key_fails_with_the_key_message(self):
        userkeys.forget(self.alice)
        job, = self.run_job(self.alice, lock_mid_job=False)
        self.assertEqual((job["status"], job["error"]), ("error", "Add your Gemini key in the account menu."))


class ResumeAtSignIn(LocalAccountsCase):
    def setUp(self):
        super().setUp()
        self.tag = uuid.uuid4().hex[:6]
        self.users = {}
        for who in ("Ann", "Ben"):
            user = db.create_local_account(f"{who} {self.tag}", None)
            server._store_key(user["id"], f"{who}-key-{self.tag}", "device", None, "1234")
            planning = db.create_course(user["id"], "Planning", "goal", "materials", [], "learn")
            db.update_course(planning["id"], status="planning")
            pending = db.create_course(user["id"], "Pending", "goal", "materials", [], "learn")
            db.replace_classes(pending["id"], [{"title": "Class 1"}])
            db.update_course(pending["id"], status="generating")
            self.users[who] = (user["id"], planning["id"], pending["id"])
        self.addCleanup(lambda: [db.delete_course(cid) for _, *cids in self.users.values() for cid in cids])
        self.plan = mock.patch.object(server, "start_plan_job")
        self.queue = mock.patch.object(server, "queue_course_generation")
        self.started, self.queued = self.plan.start(), self.queue.start()
        self.addCleanup(self.plan.stop)
        self.addCleanup(self.queue.stop)

    def test_nothing_resumes_at_boot_until_its_owner_signs_in(self):
        with TestClient(server.app, base_url=LOCAL) as c:  # the lifespan runs resume_course_generation
            self.started.assert_not_called()
            self.queued.assert_not_called()
            r = c.post("/api/auth/login", json={"name": f"Ann {self.tag}"})
            self.assertEqual((r.status_code, r.json()["keyState"]), (200, "ok"))
        ann, planning, pending = self.users["Ann"]
        self.assertEqual([call.args[0] for call in self.started.call_args_list], [planning])
        self.assertEqual([call.args[0] for call in self.queued.call_args_list], [pending])

    def test_server_mode_still_resumes_everything_at_boot(self):
        server.LOCAL_ACCOUNTS = False
        with TestClient(server.app, base_url=LOCAL):
            pass
        started = {call.args[0] for call in self.started.call_args_list}
        queued = {call.args[0] for call in self.queued.call_args_list}
        for _, planning, pending in self.users.values():
            self.assertIn(planning, started)
            self.assertIn(pending, queued)

    def test_courses_that_failed_for_want_of_a_key_resume_at_sign_in(self):
        ann = self.users["Ann"][0]
        no_key = db.create_course(ann, "No key", "goal", "materials for a course", [], "learn")
        db.update_course(no_key["id"], status="error", error=server.NO_KEY_TEXT)
        quota = db.create_course(ann, "Quota", "goal", "materials for a course", [], "learn")
        db.update_course(quota["id"], status="error", error="Gemini quota exhausted for every fallback model.")
        self.addCleanup(lambda: [db.delete_course(c["id"]) for c in (no_key, quota)])
        with TestClient(server.app, base_url=LOCAL) as c:
            self.assertEqual(c.post("/api/auth/login", json={"name": f"Ann {self.tag}"}).status_code, 200)
        started = {call.args[0] for call in self.started.call_args_list}
        self.assertIn(no_key["id"], started)
        self.assertNotIn(quota["id"], started)

    def test_signing_in_again_keeps_the_open_key(self):
        ann = self.users["Ann"][0]
        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/auth/login", json={"name": f"Ann {self.tag}"})
            handle = userkeys.handle_for(ann)
            c.post("/api/auth/login", json={"name": f"Ann {self.tag}"})
        self.assertIs(userkeys.handle_for(ann), handle)
        self.assertIsNone(handle.revoked_at)

    def test_db_filters_by_user(self):
        ann, planning, pending = self.users["Ann"]
        self.assertEqual([c["id"] for c in db.interrupted_planning(user_id=ann)], [planning])
        self.assertEqual(db.courses_with_pending_classes(user_id=ann), [pending])
        everyone = db.courses_with_pending_classes()
        self.assertTrue({p for _, _, p in self.users.values()} <= set(everyone))


class ResumeStartsOnce(LocalGeminiBase):
    """Two sign-ins at once (two windows) start one planning job per course, not two."""
    def test_concurrent_resumes_start_one_plan_job(self):
        course = db.create_course(self.alice, "Planning", "goal", "materials for a course", [], "learn")
        db.update_course(course["id"], status="planning")
        self.addCleanup(db.delete_course, course["id"])
        release, calls = threading.Event(), []

        def model(*args, **kwargs):  # the plan's first model call waits until both resumes are done
            calls.append(1)
            release.wait(5)
            raise RuntimeError("model unavailable in this test")
        loop = asyncio.new_event_loop()
        runner = threading.Thread(target=loop.run_forever, daemon=True)
        runner.start()
        self.addCleanup(lambda: (loop.call_soon_threadsafe(loop.stop), runner.join(5), loop.close()))
        before = set(server.JOBS)
        with mock.patch.object(server, "MAIN_LOOP", loop), mock.patch.object(server, "call_gemini", model):
            barrier = threading.Barrier(2)

            def sign_in():
                barrier.wait()
                server.resume_for_user(self.alice)
            threads = [threading.Thread(target=sign_in) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(5)
            plan_jobs = [server.JOBS[j] for j in set(server.JOBS) - before if server.JOBS[j]["kind"] == "plan"]
            release.set()
            end = time.time() + 5
            while any(j["status"] in ("queued", "running") for j in plan_jobs) and time.time() < end:
                time.sleep(0.01)
        self.addCleanup(lambda: [server.JOBS.pop(j["id"], None) for j in plan_jobs])
        self.assertEqual(len(plan_jobs), 1)
        self.assertEqual(plan_jobs[0]["owner"], self.alice)
        self.assertLessEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
