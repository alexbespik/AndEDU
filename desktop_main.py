"""Backend entry point for the desktop app (desktop/main.cjs spawns it with the bundled Python).

Launch contract:
- The first line on stdin is JSON, {"device_key": "<base64 of 32 bytes>", "legacy_gemini_key": "..."} (either may be
  missing). They go into userkeys (DEVICE_KEY seals the keys of accounts without a password; LEGACY_KEY is the key an
  older version saved on this computer, offered once to an account), never into the environment, so they are not in
  what other processes can read (ps -E) and server.py never builds an install-wide Gemini client from them.
- Stdin stays open while the app runs; end of file means the app is gone, so the backend exits.
- Everything else (port, data folder, SCIEDU_ENV_FILE=none, SCIEDU_LOCAL_ACCOUNTS=1, AGY_CLI=0) comes from the app's
  allowlisted env.
"""
import base64
import json
import os
import runpy
import signal
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_launch_settings(stream):
    """Applies the settings line from the app; a missing or broken line or field just means no key."""
    import userkeys  # after the sys.path insert (python -I leaves out the script's folder); server.py gets this module

    line = stream.readline()
    try:
        settings = json.loads(line) if line.strip() else {}
    except ValueError:
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    for name in ("api_KEY", "GEMINI_API_KEY"):  # one install-wide key from outside would bypass the accounts
        os.environ.pop(name, None)
    userkeys.DEVICE_KEY = _device_key(settings.get("device_key"))
    legacy = settings.get("legacy_gemini_key")
    legacy = legacy.strip() if isinstance(legacy, str) else ""
    userkeys.LEGACY_KEY = legacy if 8 <= len(legacy) <= 200 and not any(ch.isspace() for ch in legacy) else None


def _device_key(value):
    """32 bytes from base64, else None (accounts without a password then cannot store a key)."""
    if not isinstance(value, str):
        return None
    try:
        key = base64.b64decode(value, validate=True)
    except ValueError:  # binascii.Error
        return None
    return key if len(key) == 32 else None


def exit_when_parent_closes(stream):
    while stream.read(4096):
        pass
    os.kill(os.getpid(), signal.SIGTERM)  # the app is gone: shut down like a normal stop (uvicorn handles SIGTERM)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    read_launch_settings(sys.stdin)
    print("[startup] Settings read", flush=True)  # fixed text: the app's start page shows these lines
    threading.Thread(target=exit_when_parent_closes, args=(sys.stdin.buffer,), daemon=True).start()
    code = 1
    try:
        print("[startup] Loading the lesson engine", flush=True)
        runpy.run_path(str(HERE / "server.py"), run_name="__main__")
        code = 0
    except SystemExit as exc:  # uvicorn exits this way when it cannot bind; server.py with a message
        if isinstance(exc.code, int) or exc.code is None:
            code = exc.code or 0
        else:
            print(exc.code, file=sys.stderr)
    except BaseException:
        import traceback
        traceback.print_exc()
    finally:
        db = sys.modules.get("db")  # what atexit would do (os._exit skips it): close the SQLite connections
        if db is not None:
            try:
                db.close_all()
            except Exception:
                pass
        # os._exit, not a normal shutdown: the watchdog thread is blocked reading stdin, and a normal
        # interpreter shutdown aborts on that ("could not acquire lock for <stdin>")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
