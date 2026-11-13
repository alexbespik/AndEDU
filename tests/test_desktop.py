"""Desktop app launch contract: SCIEDU_ENV_FILE, the stdin settings line (desktop_main.py), instance_id in /api/status,
and the shell's own sources (desktop/main.cjs, preload.cjs, electron-builder.yml)."""
from test_lab import LOCAL, TestClient, server  # noqa: F401  (sets up the temp content dir first)

import base64
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_main
import userkeys

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
    """The stdin line carries the device key and the old computer-wide key into userkeys, never into os.environ."""
    DEVICE = bytes(range(32))

    def setUp(self):
        saved = (userkeys.DEVICE_KEY, userkeys.LEGACY_KEY)
        self.addCleanup(lambda: (setattr(userkeys, "DEVICE_KEY", saved[0]), setattr(userkeys, "LEGACY_KEY", saved[1])))

    def read(self, line):
        before = dict(os.environ)
        desktop_main.read_launch_settings(io.StringIO(line))
        return before

    def test_keys_from_the_settings_line_go_into_userkeys(self):
        line = json.dumps({"device_key": base64.b64encode(self.DEVICE).decode(), "legacy_gemini_key": " AIza-old-key-1234 "})
        with mock.patch.dict(os.environ, {"api_KEY": "outside", "GEMINI_API_KEY": "outside"}, clear=False):
            before = self.read(line + "\n")
            self.assertNotIn("api_KEY", os.environ)
            self.assertNotIn("GEMINI_API_KEY", os.environ)
            self.assertEqual({k: v for k, v in before.items() if k not in ("api_KEY", "GEMINI_API_KEY")}, dict(os.environ))
            self.assertNotIn("AIza-old-key-1234", "".join(os.environ.values()))
        self.assertEqual(userkeys.DEVICE_KEY, self.DEVICE)
        self.assertEqual(userkeys.LEGACY_KEY, "AIza-old-key-1234")

    def test_no_key_or_a_broken_line_means_no_key(self):
        good = base64.b64encode(self.DEVICE).decode()
        for line in ("{}\n", "not json\n", "", '["x"]\n', '{"device_key": 5, "legacy_gemini_key": 5}\n',
                     json.dumps({"device_key": base64.b64encode(b"short").decode()}) + "\n",
                     json.dumps({"device_key": good[:-4] + "!!!!"}) + "\n",
                     json.dumps({"legacy_gemini_key": "has spaces in it"}) + "\n",
                     json.dumps({"legacy_gemini_key": "short"}) + "\n",
                     '{"gemini_key": "AIza-the-old-contract-1234"}\n'):
            userkeys.DEVICE_KEY, userkeys.LEGACY_KEY = b"stale", "stale"
            with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "stale"}, clear=False):
                self.read(line)
                self.assertNotIn("GEMINI_API_KEY", os.environ, line)
            self.assertIsNone(userkeys.DEVICE_KEY, line)
            self.assertIsNone(userkeys.LEGACY_KEY, line)

    def test_server_run_by_desktop_main_sees_the_same_userkeys(self):
        # desktop_main imports userkeys before runpy runs server.py, whose `import userkeys` then finds it in sys.modules
        source = (ROOT / "desktop_main.py").read_text()
        self.assertLess(source.index("read_launch_settings(sys.stdin)"), source.index("runpy.run_path"))
        self.assertLess(source.index("sys.path.insert(0, str(HERE))"), source.index("read_launch_settings(sys.stdin)"))
        self.assertIs(server.userkeys, userkeys)


class ShellSourceTests(unittest.TestCase):
    """desktop/main.cjs: accounts on, secrets on stdin only, and the old computer-wide key path is gone."""
    MAIN = (ROOT / "desktop" / "main.cjs").read_text()
    PRELOAD = (ROOT / "desktop" / "preload.cjs").read_text()

    def test_local_accounts_on_and_the_old_key_ipc_gone(self):
        self.assertIn("SCIEDU_LOCAL_ACCOUNTS: '1'", self.MAIN)
        for gone in ("saveKey", "hasKey", "clearKey", "keycheck", "gemini_key:", "GEMINI_API_KEY", "api_KEY"):
            self.assertNotIn(gone, self.MAIN, gone)
            self.assertNotIn(gone, self.PRELOAD, gone)
        self.assertFalse((ROOT / "desktop" / "keycheck.cjs").exists())
        self.assertIn("removeLegacyKey: () => ipcRenderer.invoke('sciedu:removeLegacyKey')", self.PRELOAD)

    def test_every_ipc_handler_checks_its_sender(self):
        handlers = re.findall(r"ipcMain\.handle\('([\w:]+)', (?:async )?\(event\) => \{\n\s+if \(!fromBackend\(event\)\)", self.MAIN)
        self.assertEqual(handlers, ["sciedu:removeLegacyKey"])
        self.assertEqual(self.MAIN.count("ipcMain.handle("), 1)

    def test_device_key_kept_with_safe_storage_and_sent_on_stdin(self):
        self.assertIn("path.join(dataDir, 'secrets', 'device.key.enc')", self.MAIN)
        self.assertIn("crypto.randomBytes(32)", self.MAIN)
        self.assertIn("settings.device_key = deviceKey", self.MAIN)
        self.assertIn("settings.legacy_gemini_key = legacyKey", self.MAIN)
        self.assertIn("child.stdin.write(JSON.stringify(settings)", self.MAIN)
        load = self.MAIN[self.MAIN.index("function loadDeviceKey"):self.MAIN.index("function loadLegacyKey")]
        self.assertIn("if (!secureStoreOk()) return '';", load)  # no keyring (Linux basic_text): no device key
        self.assertIn("if (err.code !== 'ENOENT') return '';", load)  # a file that does not open is never replaced
        env = self.MAIN[self.MAIN.index("function backendEnv"):self.MAIN.index("async function startBackend")]
        self.assertNotIn("Key", env)
        self.assertNotIn("KEY", env)

    def test_old_key_file_goes_only_when_the_backend_says_it_was_answered(self):
        ipc = self.MAIN[self.MAIN.index("ipcMain.handle('sciedu:removeLegacyKey'"):]
        ipc = ipc[:ipc.index("\n  });\n")]
        self.assertIn("/api/status", ipc)
        self.assertIn("st.instance_id !== b.instanceId || st.legacy_key_pending !== false) return { ok: false }", ipc)
        self.assertLess(ipc.index("legacy_key_pending"), ipc.index("fs.rmSync(legacyKeyPath"))
        self.assertIn("catch {\n      return { ok: false };", ipc)  # no answer from the backend: the file stays

    def test_builder_does_not_package_the_key_check(self):
        self.assertNotIn("keycheck", (ROOT / "electron-builder.yml").read_text())


class StatusTests(unittest.TestCase):
    def test_instance_id_in_status(self):
        with mock.patch.dict(os.environ, {"SCIEDU_INSTANCE_ID": "launch-42"}):
            body = TestClient(server.app, base_url=LOCAL).get("/api/status").json()
        self.assertEqual(body["instance_id"], "launch-42")


class KeyStateTests(unittest.TestCase):
    """A key Google rejects stops the model fallback and shows in /api/status. Bodies match tests/test_userkeys.py."""

    INVALID = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                         "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}}
    LEAKED = {"error": {"code": 403, "message": "Your API key was reported as leaked. Please use another API key.",
                        "status": "PERMISSION_DENIED"}}
    QUOTA = {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}}
    PLAIN_400 = {"error": {"code": 400, "message": "Invalid JSON payload received.", "status": "INVALID_ARGUMENT"}}

    def setUp(self):
        server.GEMINI_KEY_INVALID = False
        server.GROUNDING_PAUSED_UNTIL = 0.0  # a quota error pauses search grounding; start each test with it on
        self.addCleanup(setattr, server, "GEMINI_KEY_INVALID", False)
        self.addCleanup(setattr, server, "GROUNDING_PAUSED_UNTIL", 0.0)

    def call(self, generate):
        from types import SimpleNamespace
        calls = []

        def counted(model, contents, **kw):
            calls.append(model)
            return generate(model, contents, **kw)

        mock_client = SimpleNamespace(models=SimpleNamespace(generate_content=counted))
        real_fn = getattr(server, "_real_call_gemini", server.call_gemini)
        with mock.patch.object(server, "client", mock_client), \
             mock.patch.object(server, "spend_model_call", return_value=None), \
             mock.patch.object(server, "MODEL_COOLDOWN", {}):
            try:
                return real_fn("Test prompt", role="planner"), calls
            except Exception as e:  # noqa: BLE001
                return e, calls

    def status(self):
        return TestClient(server.app, base_url=LOCAL).get("/api/status").json()

    def test_rejected_key_stops_at_the_first_call_and_shows_in_status(self):
        from google.genai.errors import ClientError
        grounded = []

        def bad(model, contents, **kw):
            grounded.append(any(getattr(t, "google_search", None) is not None for t in (getattr(kw.get("config"), "tools", None) or [])))
            raise ClientError(400, self.INVALID)

        err, calls = self.call(bad)
        self.assertEqual(grounded, [True])  # the call carried search, so the grounding retry was in reach
        self.assertIsInstance(err, RuntimeError)
        self.assertIn("rejected the Gemini API key", str(err))
        self.assertEqual(len(calls), 1)  # no grounding retry, no fallback models
        self.assertEqual(server.GROUNDING_PAUSED_UNTIL, 0.0)  # a bad key doesn't pause grounding
        self.assertTrue(self.status()["gemini_key_invalid"])

    def test_leaked_key_counts_as_rejected(self):
        from google.genai.errors import ClientError

        def leaked(model, contents, **kw):
            raise ClientError(403, self.LEAKED)

        err, calls = self.call(leaked)
        self.assertIsInstance(err, RuntimeError)
        self.assertEqual(len(calls), 1)
        self.assertTrue(server.GEMINI_KEY_INVALID)

    def test_quota_and_other_400s_are_not_a_bad_key(self):
        from google.genai.errors import ClientError
        for body, code in ((self.QUOTA, 429), (self.PLAIN_400, 400)):
            def failing(model, contents, **kw):
                raise ClientError(code, body)
            self.call(failing)
            self.assertFalse(server.GEMINI_KEY_INVALID, code)
            self.assertFalse(self.status()["gemini_key_invalid"])

    def test_a_working_call_clears_the_flag(self):
        from types import SimpleNamespace
        server.GEMINI_KEY_INVALID = True
        resp, _ = self.call(lambda model, contents, **kw: SimpleNamespace(text="ok"))
        self.assertEqual(resp.text, "ok")
        self.assertFalse(server.GEMINI_KEY_INVALID)

    def test_hidden_in_accounts_mode(self):
        server.GEMINI_KEY_INVALID = True
        with mock.patch.object(server, "AUTH_REQUIRED", True):
            body = TestClient(server.app, base_url=LOCAL).get("/api/status").json()
        self.assertFalse(body["gemini_key_invalid"])


class PackagingTests(unittest.TestCase):
    """scripts/desktop_stage.sh, the per-target locks and electron-builder.yml agree on the four targets."""

    PLATFORMS = {"mac-arm64": "aarch64-apple-darwin", "mac-x64": "x86_64-apple-darwin",
                 "linux-x64": "x86_64-manylinux_2_28", "linux-arm64": "aarch64-manylinux_2_28"}
    WHEEL_MACHINE = {"mac-arm64": "_arm64", "mac-x64": "_x86_64", "linux-x64": "_x86_64", "linux-arm64": "_aarch64"}

    def test_every_staged_target_has_a_hash_locked_lock_for_its_platform(self):
        script = ROOT / "scripts" / "desktop_stage.sh"
        subprocess.run(["bash", "-n", str(script)], check=True)
        stage = script.read_text()
        for target, platform in self.PLATFORMS.items():
            # the interpreter (triple) and the wheel tags must be for the same machine as the lock
            for field, machine in (("triple", platform.split("-")[0]), ("wheel", self.WHEEL_MACHINE[target])):
                line = next(l for l in stage.splitlines() if l.strip().startswith(f"{target}:{field})"))
                self.assertIn(machine, line, f"{target}:{field}")
            lock = ROOT / "desktop" / f"requirements-{target}.lock"
            text = lock.read_text()
            self.assertIn(f"--python-platform {platform} ", text.splitlines()[1], lock.name)
            pins = [line for line in text.splitlines() if "==" in line and not line.startswith(("#", " "))]
            self.assertGreater(len(pins), 10, lock.name)
            for pin in pins:  # "name==1.2 \" is always followed by its --hash lines
                self.assertTrue(pin.endswith(" \\"), f"{lock.name}: {pin} has no hash")

    def test_builder_bundles_the_python_for_each_os(self):
        builder = (ROOT / "electron-builder.yml").read_text()
        self.assertIn('from: "build/desktop/python-${os}-${arch}"', builder)
        self.assertIn("\nlinux:\n", builder)
        self.assertIn("executableName: sciedu-studio", builder)
        # every file desktop/main.cjs requires must be packaged, or the installed app dies at launch
        main = (ROOT / "desktop" / "main.cjs").read_text()
        for local in re.findall(r"require\('\./([\w.-]+)'\)", main):
            self.assertIn(f"- desktop/{local}", builder, local)


class SandboxRunnerTests(unittest.TestCase):
    def test_resource_limits_still_let_python_start(self):
        # RLIMIT_AS (1 GB) is enforced on Linux; plain Python and a small allocation must still run
        result = server.run_python_sandboxed("x = bytearray(50_000_000)\nprint(len(x))")
        self.assertTrue(result["success"], result["stderr"])
        self.assertEqual(result["stdout"].strip(), "50000000")


if __name__ == "__main__":
    unittest.main()
