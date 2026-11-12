"""Backend entry point for the desktop app (desktop/main.cjs spawns it with the bundled Python).

Launch contract:
- The first line on stdin is JSON, {"gemini_key": "..."} or {}. The key goes into this process's environment
  only after start, so it is not in the startup environment other processes can read (ps -E).
- Stdin stays open while the app runs; end of file means the app is gone, so the backend exits.
- Everything else (port, data folder, SCIEDU_ENV_FILE=none, AGY_CLI=0) comes from the app's allowlisted env.
"""
import json
import os
import runpy
import signal
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_launch_settings(stream):
    """Applies the settings line from the app; a missing or broken line just means no key."""
    line = stream.readline()
    try:
        settings = json.loads(line) if line.strip() else {}
    except ValueError:
        settings = {}
    os.environ.pop("api_KEY", None)  # server.py prefers api_KEY: never let one in from outside
    key = settings.get("gemini_key") if isinstance(settings, dict) else None
    if isinstance(key, str) and key.strip():
        os.environ["GEMINI_API_KEY"] = key.strip()
    else:
        os.environ.pop("GEMINI_API_KEY", None)


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
