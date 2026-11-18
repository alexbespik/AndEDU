"""Local voice packs (voice_packs.py): only manifest-listed audio files inside the pack folder are served, and
nothing at all with server accounts on."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lab import LOCAL, server  # noqa: E402  (temporary data folder and the offline guard)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import voice_packs  # noqa: E402

MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 64


class VoicePacks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        pack = self.root / "commissar"
        pack.mkdir()
        (pack / "on-1.mp3").write_bytes(MP3)
        (pack / "tab-1.mp3").write_bytes(MP3)
        (pack / "notes.txt").write_text("not audio")
        (self.root / "secret.mp3").write_bytes(MP3)  # outside the pack
        (pack / "manifest.json").write_text(json.dumps({"name": "Test pack", "events": {
            "on": ["on-1.mp3", "missing.mp3", "../secret.mp3", "notes.txt"],
            "tab": ["tab-1.mp3"],
            "bogus": ["tab-1.mp3"],
        }}))
        self.enabled = True
        app = FastAPI()
        app.include_router(voice_packs.build_router(root=lambda: self.root, enabled=lambda: self.enabled,
                                                    rate_limit=lambda _b: None))
        self.c = TestClient(app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pack_lists_only_real_clips_and_known_events(self):
        packs = self.c.get("/api/voice-packs").json()["packs"]
        self.assertEqual(len(packs), 1)
        self.assertEqual(packs[0]["events"], {"on": ["on-1.mp3"], "tab": ["tab-1.mp3"]})
        self.assertEqual(packs[0]["name"], "Test pack")

    def test_quiz_session_events_are_known(self):
        """A quiz's start, result and walk-out are pack events, and the browser lines cover every pack event."""
        manifest = self.root / "commissar" / "manifest.json"
        events = {"quizStart": ["on-1.mp3"], "quizWin": ["tab-1.mp3"], "quizLose": ["tab-1.mp3"], "desert": ["on-1.mp3"]}
        manifest.write_text(json.dumps({"name": "Test pack", "events": events}))
        self.assertEqual(self.c.get("/api/voice-packs").json()["packs"][0]["events"], events)
        lines = json.loads((Path(__file__).resolve().parent.parent / "src/lib/commissarLines.json").read_text())
        self.assertEqual(set(lines), set(voice_packs.EVENTS))
        self.assertTrue(all(lines[e] for e in voice_packs.EVENTS))

    def test_pack_summon_word(self):
        """A pack may name its own console word; console commands, yarrik and odd words are refused."""
        manifest = self.root / "commissar" / "manifest.json"
        for word, expected in (("sergeant", "sergeant"), ("yarrik", None), ("help", None), ("Bad", None), ("ab", None), (5, None)):
            manifest.write_text(json.dumps({"events": {"on": ["on-1.mp3"]}, "summon": word}))
            self.assertEqual(self.c.get("/api/voice-packs").json()["packs"][0].get("summon"), expected, word)

    def test_clip_is_served_as_audio(self):
        r = self.c.get("/api/voice-packs/commissar/on-1.mp3")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "audio/mpeg")
        self.assertEqual(r.headers["x-content-type-options"], "nosniff")

    def test_unlisted_outside_and_odd_names_are_refused(self):
        for path in ("/api/voice-packs/commissar/notes.txt", "/api/voice-packs/commissar/manifest.json",
                     "/api/voice-packs/commissar/..%2Fsecret.mp3", "/api/voice-packs/commissar/secret.mp3",
                     "/api/voice-packs/..%2Fcommissar/on-1.mp3", "/api/voice-packs/Commissar/on-1.mp3",
                     "/api/voice-packs/nope/on-1.mp3"):
            self.assertEqual(self.c.get(path).status_code, 404, path)

    def test_symlinked_clip_is_refused(self):
        link = self.root / "commissar" / "link.mp3"
        try:
            os.symlink(self.root / "secret.mp3", link)
        except OSError:
            self.skipTest("symlinks not available")
        manifest = self.root / "commissar" / "manifest.json"
        data = json.loads(manifest.read_text())
        data["events"]["reward"] = ["link.mp3"]
        manifest.write_text(json.dumps(data))
        self.assertNotIn("reward", voice_packs.load_pack(self.root, "commissar")["events"])
        self.assertEqual(self.c.get("/api/voice-packs/commissar/link.mp3").status_code, 404)

    def test_broken_manifest_means_no_pack(self):
        (self.root / "commissar" / "manifest.json").write_text("{not json")
        self.assertEqual(self.c.get("/api/voice-packs").json()["packs"], [])

    def test_off_with_server_accounts(self):
        self.enabled = False
        self.assertEqual(self.c.get("/api/voice-packs").status_code, 404)
        self.assertEqual(self.c.get("/api/voice-packs/commissar/on-1.mp3").status_code, 404)

    def test_server_mounts_the_routes_local_only(self):
        with TestClient(server.app, base_url=LOCAL) as c:
            self.assertEqual(c.get("/api/voice-packs").status_code, 200)
        self.assertTrue(server.voice_packs_enabled())


if __name__ == "__main__":
    unittest.main()
