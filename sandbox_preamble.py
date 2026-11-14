# ---------------------------------------------------------------------------
# PEP 578 Audit Hook Sandbox Preamble
# Runs at the start of sandboxed student Python executions to prevent
# socket connections, child subprocesses, signal manipulation, and
# unauthorized file access (e.g. database dumping).
# ---------------------------------------------------------------------------

import sys

def _audit_hook(event, args):
    # 1. Block network / socket creation, connections, and DNS lookups
    if event.startswith("socket."):
        if event in ("socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo", "socket.gethostbyname"):
            raise PermissionError(f"Network access disabled in sandbox: {event}")

    # 2. Block subprocess execution and system commands
    if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "os.exec", "_posixsubprocess.fork_exec", "os.fork"):
        raise PermissionError(f"Subprocess execution disabled in sandbox: {event}")

    # 3. Block process signaling and termination
    if event in ("os.kill", "os.killpg", "signal.pthread_kill"):
        raise PermissionError(f"Signal operations disabled in sandbox: {event}")

    # 4. Block dynamic C-library loading
    if event in ("ctypes.dlopen", "ctypes.dlsym"):
        raise PermissionError(f"Native library loading disabled in sandbox: {event}")

    # 5. File access guard: block attempts to read backend database, credentials, or ssh keys
    if event in ("open", "io.open", "os.open", "os.listdir", "os.walk", "sqlite3.connect"):
        if args and len(args) > 0:
            target = str(args[0]).lower().replace("\\", "/")
            if any(forbidden in target for forbidden in ("edu_studio.db", ".env", "id_rsa", "id_ed25519", ".ssh", "credentials", "config/")):
                raise PermissionError(f"Access to protected resource denied: {args[0]}")

    # 6. Block destructive filesystem modifications
    if event in ("os.remove", "os.unlink", "os.rmdir", "os.rename"):
        raise PermissionError(f"Filesystem modifications disabled in sandbox: {event}")

# Register audit hook permanently in this process
try:
    sys.addaudithook(_audit_hook)
except (AttributeError, RuntimeError):
    pass
