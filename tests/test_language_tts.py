"""Language TTS (language_tts.py): cached ElevenLabs clips, fallbacks to the browser voice, caps and accounts mode.
Offline: httpx.post is stubbed in every test; shares test_lab's temporary data folder."""
import os
import shutil
import time
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from test_lab import LOCAL, TestClient, server  # noqa: F401  (sets up the temp data dir first)

import db
import language_tts

ON = {"SCIEDU_ELEVENLABS": "1", "ELEVENLABS_API_KEY": "server-key", "SCIEDU_TTS_DAILY_CHARS": "20000"}


def ok_audio(*args, **kwargs):
    return SimpleNamespace(status_code=200, content=b"ID3fake-mp3")


class LanguageTts(unittest.TestCase):
    def setUp(self):
        server.AUTH_REQUIRED = False
        shutil.rmtree(language_tts.cache_dir(), ignore_errors=True)
        language_tts._usage.update(day="", chars=0)
        for k in [k for k in server._rate_hits if k[0] == "language_tts"]:
            server._rate_hits.pop(k)
        self.env = mock.patch.dict(os.environ, ON)
        self.env.start()
        for k in ("ELEVEN_LABS_API_KEY", "XI_API_KEY", "ELEVENLABS_GERMAN_VOICE_ID"):
            os.environ.pop(k, None)
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        self.env.stop()
        server.AUTH_REQUIRED = False

    def tts(self, **body):
        return self.c.post("/api/language/tts", json={"text": "Guten Morgen", "lang": "de", **body})

    def test_miss_calls_once_then_hits_cache(self):
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            first = self.tts().json()
            second = self.tts().json()
            third = self.c.post("/api/language/tts", json={"text": "  Guten Morgen ", "lang": "de"}).json()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(first["source"], "elevenlabs")
        self.assertEqual(second["source"], "cache")
        self.assertEqual(third["url"], first["url"])  # same key: trimmed text, and slow playback never asks again
        args, kwargs = post.call_args
        self.assertEqual(kwargs["json"]["model_id"], "eleven_multilingual_v2")
        self.assertEqual(kwargs["headers"]["xi-api-key"], "server-key")
        self.assertEqual(kwargs["timeout"], 15.0)
        r = self.c.get(first["url"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"ID3fake-mp3")
        self.assertEqual(r.headers["content-type"], "audio/mpeg")
        self.assertIn("immutable", r.headers["cache-control"])
        self.assertEqual(list(language_tts.cache_dir().glob("*.tmp")), [])

    def test_key_ignores_slow_and_depends_on_voice_lang_text(self):
        k = language_tts.cache_key("Hallo", "de", "JBFqnCBsd6RMkjVDRZzb")
        self.assertEqual(k, language_tts.cache_key(" Hallo ", "de", "JBFqnCBsd6RMkjVDRZzb"))
        self.assertEqual(k, language_tts.cache_key("Hallo", "de", "JBFqnCBsd6RMkjVDRZzb"))
        self.assertNotEqual(k, language_tts.cache_key("Hallo", "en", "JBFqnCBsd6RMkjVDRZzb"))
        self.assertNotEqual(k, language_tts.cache_key("Hallo", "de", "onwK4e9ZLuTAKqWW03F9"))
        # NFC: a decomposed ü is the same word
        self.assertEqual(language_tts.cache_key("Tschüss", "de", "x" * 20), language_tts.cache_key("Tschüss", "de", "x" * 20))
        self.assertEqual(self.c.post("/api/language/tts", json={"text": "Hallo", "lang": "de", "slow": True}).status_code, 422)

    def test_validation(self):
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            self.assertEqual(self.tts(text="a" * 301).status_code, 400)
            self.assertEqual(self.tts(text="   ").status_code, 400)
            self.assertEqual(self.tts(voice="../../etc").status_code, 400)
            self.assertEqual(self.tts(voice="short").status_code, 400)
            self.assertEqual(self.tts(lang="xx").status_code, 400)
        post.assert_not_called()

    def test_bad_hash_is_404(self):
        for path in ("/api/language/tts/abc.mp3", "/api/language/tts/" + "g" * 64 + ".mp3",
                     "/api/language/tts/..%2F..%2Fedu_studio.db.mp3", "/api/language/tts/..mp3",
                     "/api/language/tts/" + "a" * 64 + ".mp3"):
            self.assertEqual(self.c.get(path).status_code, 404, path)

    def test_disabled_answers_browser(self):
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            os.environ["SCIEDU_ELEVENLABS"] = ""
            self.assertEqual(self.tts().json(), {"url": None, "source": "browser", "reason": "disabled"})
            os.environ["SCIEDU_ELEVENLABS"] = "1"
            os.environ["ELEVENLABS_API_KEY"] = ""
            self.assertEqual(self.tts().json()["source"], "browser")
        post.assert_not_called()

    def test_upstream_error_answers_browser(self):
        with mock.patch.object(language_tts.httpx, "post", return_value=SimpleNamespace(status_code=401, content=b"no")):
            r = self.tts()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["source"], "browser")
        with mock.patch.object(language_tts.httpx, "post", side_effect=language_tts.httpx.ConnectTimeout("slow")):
            self.assertEqual(self.tts().json()["source"], "browser")
        self.assertEqual(list(language_tts.cache_dir().glob("*")) if language_tts.cache_dir().exists() else [], [])
        self.assertEqual(language_tts._usage["chars"], 0)  # failed calls are not counted

    def test_daily_char_cap(self):
        os.environ["SCIEDU_TTS_DAILY_CHARS"] = "20"
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            self.assertEqual(self.tts(text="Guten Morgen").json()["source"], "elevenlabs")  # 12 chars
            self.assertEqual(self.tts(text="Guten Abend").json(), {"url": None, "source": "browser", "reason": "daily_cap"})
            self.assertEqual(self.tts(text="Guten Morgen").json()["source"], "cache")  # hits cost nothing
        self.assertEqual(post.call_count, 1)

    def test_refund_skipped_after_the_day_changed(self):
        day = language_tts._reserve_chars(10)
        self.assertTrue(day)
        self.assertEqual(language_tts._usage["chars"], 10)
        language_tts._usage.update(day="2000-01-01", chars=4)  # the counter rolled over while the request ran
        language_tts._refund_chars(10, "language", day)
        self.assertEqual(language_tts._usage, {"day": "2000-01-01", "chars": 4})
        language_tts._usage.update(day=day, chars=10)
        language_tts._refund_chars(10, "language", day)
        self.assertEqual(language_tts._usage["chars"], 0)

    def test_failed_write_refunds_and_answers_browser(self):
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio), \
                mock.patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")):
            r = self.tts()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"url": None, "source": "browser", "reason": "upstream_error"})
        self.assertEqual(language_tts._usage["chars"], 0)
        d = language_tts.cache_dir()
        self.assertEqual(list(d.glob("*")) if d.exists() else [], [])

    def test_rate_limit_on_misses_falls_back(self):
        old = server.RATE_LIMITS["language_tts"]
        server.RATE_LIMITS["language_tts"] = 1
        try:
            with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio):
                self.assertEqual(self.tts(text="eins").json()["source"], "elevenlabs")
                self.assertEqual(self.tts(text="eins").json()["source"], "cache")
                self.assertEqual(self.tts(text="zwei").json()["reason"], "rate_limited")
        finally:
            server.RATE_LIMITS["language_tts"] = old

    def test_sweep_deletes_oldest(self):
        d = language_tts.cache_dir()
        d.mkdir(parents=True, exist_ok=True)
        now = time.time()
        names = []
        for i in range(4):
            p = d / f"{uuid.uuid4().hex * 2}.mp3"
            p.write_bytes(b"x" * 100)
            os.utime(p, (now - 100 + i, now - 100 + i))
            names.append(p)
        language_tts.sweep(limit_bytes=250)
        self.assertEqual([p.exists() for p in names], [False, False, True, True])

    def test_no_client_key_accepted(self):
        os.environ["ELEVENLABS_API_KEY"] = ""
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            r = self.tts(api_key="client-key")
            self.assertEqual(r.status_code, 422)
            r = self.tts()
        self.assertEqual(r.json()["source"], "browser")
        post.assert_not_called()

    def test_german_voice_env(self):
        os.environ["ELEVENLABS_GERMAN_VOICE_ID"] = "AbCdEfGhIjKlMnOp1234"
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            self.tts()
        self.assertIn("AbCdEfGhIjKlMnOp1234", post.call_args[0][0])

    def test_accounts_mode_needs_sign_in(self):
        server.AUTH_REQUIRED = True
        server._rate_hits.pop(("auth", "testclient"), None)
        with mock.patch.object(language_tts.httpx, "post", side_effect=ok_audio) as post:
            self.assertEqual(self.tts().status_code, 401)
            reg = self.c.post("/api/auth/register", json={"name": f"Tts {uuid.uuid4().hex[:6]}", "password": "password123",
                                                         "adult": True, "privacy": True}).json()
            h = {"Authorization": f"Bearer {reg['token']}"}
            r = self.c.post("/api/language/tts", json={"text": "Hallo", "lang": "de"}, headers=h).json()
            self.assertEqual(r["source"], "elevenlabs")
            self.assertEqual(self.c.get(r["url"]).status_code, 401)
            got = self.c.get(r["url"], headers=h)
            self.assertEqual(got.status_code, 200)
            self.assertTrue(got.headers["cache-control"].startswith("private"))
        self.assertEqual(post.call_count, 1)
        db.close_all()


if __name__ == "__main__":
    unittest.main()
