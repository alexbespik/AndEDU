"""Desktop app launch contract: SCIEDU_ENV_FILE, the stdin settings line (desktop_main.py), instance_id in /api/status."""
from test_lab import LOCAL, TestClient, server  # noqa: F401  (sets up the temp content dir first)

import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_main

ROOT = Path(__file__).resolve().parent.parent


def import_server(extra_env, probe):
    """Imports server.py in a fresh interpreter with a clean key environment and prints `probe`."""
    with tempfile.TemporaryDirectory() as content:
        env = {k: v for k, v in os.environ.items() if k not in ("api_KEY", "GEMINI_API_KEY", "SCIEDU_ENV_FILE")}
        env.update({"SCIEDU_CONTENT_DIR": content, "SCIEDU_ELEVENLABS": "0"}, **extra_env)
        out = subprocess.run([sys.executable, "-c", f"import server; print({probe})"], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise AssertionError(out.stderr[-2000:])
    return out.stdout.strip().splitlines()[-1]


class EnvFileTests(unittest.TestCase):
    def test_unset_keeps_the_file_beside_server(self):
        self.assertEqual(import_server({}, "server.ENV_FILE"), str(ROOT / ".env"))

    def test_path_loads_only_that_file(self):
        with tempfile.TemporaryDirectory() as d:
            env_file = Path(d) / "desktop.env"
            env_file.write_text("GEMINI_API_KEY=test-key-from-file\n")
            self.assertEqual(import_server({"SCIEDU_ENV_FILE": str(env_file)}, "server.api_key"), "test-key-from-file")

    def test_none_loads_nothing(self):
        self.assertEqual(import_server({"SCIEDU_ENV_FILE": "none"}, "server.api_key"), "None")


class LaunchSettingsTests(unittest.TestCase):
    def test_key_from_the_settings_line(self):
        with mock.patch.dict(os.environ, {"api_KEY": "outside"}, clear=False):
            desktop_main.read_launch_settings(io.StringIO('{"gemini_key": " abc123 "}\n'))
            self.assertEqual(os.environ.get("GEMINI_API_KEY"), "abc123")
            self.assertNotIn("api_KEY", os.environ)

    def test_no_key_or_a_broken_line_means_no_key(self):
        for line in ("{}\n", "not json\n", "", '["x"]\n', '{"gemini_key": 5}\n'):
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "stale"}, clear=False):
                desktop_main.read_launch_settings(io.StringIO(line))
                self.assertNotIn("GEMINI_API_KEY", os.environ, line)


class StatusTests(unittest.TestCase):
    def test_instance_id_in_status(self):
        with mock.patch.dict(os.environ, {"SCIEDU_INSTANCE_ID": "launch-42"}):
            body = TestClient(server.app, base_url=LOCAL).get("/api/status").json()
        self.assertEqual(body["instance_id"], "launch-42")


if __name__ == "__main__":
    unittest.main()
