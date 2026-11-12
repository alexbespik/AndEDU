"""
SQLite persistence for &.edu Studio: profiles, courses, the ordered classes in each course,
lesson snapshots and quiz attempts. Uses only the standard library.

Topic JSON files in content/topics stay the live format agents write to; every save is also
recorded in `lessons` so courses keep their history even if a file is edited or removed.
"""
import atexit
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# SCIEDU_CONTENT_DIR moves all data (tests, a server volume); default is ./content next to the code
CONTENT_ROOT = Path(os.environ.get("SCIEDU_CONTENT_DIR") or Path(__file__).parent / "content")
DB_PATH = CONTENT_ROOT / "edu_studio.db"
_local = threading.local()
_open_connections: Dict[sqlite3.Connection, threading.Thread] = {}   # connection -> owning thread
_conn_lock = threading.Lock()

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at  REAL NOT NULL,
    last_seen   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    subject        TEXT NOT NULL DEFAULT '',
    goal           TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL,          -- planning | diagnostic_ready | generating | ready | error | cleared
    materials_text TEXT NOT NULL DEFAULT '',
    filenames      TEXT NOT NULL DEFAULT '[]',
    concepts       TEXT NOT NULL DEFAULT '[]',
    diagnostic     TEXT NOT NULL DEFAULT '[]',
    answers        TEXT NOT NULL DEFAULT '{}',
    mastery        TEXT NOT NULL DEFAULT '{}',
    error          TEXT,
    job_id         TEXT,
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS courses_by_user ON courses(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS classes (
    id          TEXT PRIMARY KEY,
    course_id   TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    title       TEXT NOT NULL,
    objectives  TEXT NOT NULL DEFAULT '[]',
    concepts    TEXT NOT NULL DEFAULT '[]',
    status      TEXT NOT NULL DEFAULT 'pending',   -- planned | pending | generating | ready | error
    topic_id    TEXT,
    error       TEXT,
    score       REAL,                              -- latest fraction correct on this class's quiz
    attempts    INTEGER NOT NULL DEFAULT 0,
    completed   INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL NOT NULL,
    UNIQUE (course_id, seq)
);

CREATE TABLE IF NOT EXISTS lessons (
    topic_id    TEXT PRIMARY KEY,
    course_id   TEXT REFERENCES courses(id) ON DELETE SET NULL,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL,                     -- full topic JSON
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT,
    topic_id    TEXT NOT NULL,
    question_id TEXT NOT NULL,
    selected    INTEGER NOT NULL,
    is_correct  INTEGER NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS attempts_by_topic ON quiz_attempts(topic_id, user_id);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,                  -- sha256 of the bearer token; the token itself is never stored
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  REAL NOT NULL,
    expires_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS lessons_by_course ON lessons(course_id);
CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS student_notes (
    user_id     TEXT PRIMARY KEY,
    notes_text  TEXT NOT NULL DEFAULT '',
    updated_at  REAL NOT NULL
);

"""

JSON_COLUMNS = {"filenames", "concepts", "diagnostic", "answers", "mastery", "objectives", "meta"}
_DICT_COLUMNS = {"answers", "mastery", "meta"}   # JSON objects; the other JSON columns hold lists


def _prune_dead():
    """Closes connections whose owning thread has exited (e.g. finished anyio worker threads)."""
    with _conn_lock:
        dead = [c for c, t in _open_connections.items() if not t.is_alive()]
        for c in dead:
            _open_connections.pop(c, None)
    for c in dead:
        try:
            c.close()
        except Exception:
            pass


def conn() -> sqlite3.Connection:
    """One connection per thread (FastAPI runs sync handlers in a thread pool)."""
    c = getattr(_local, "conn", None)
    if c is not None:
        try:
            c.total_changes      # raises once the connection was closed (close_all from another thread)
        except Exception:
            with _conn_lock:
                _open_connections.pop(c, None)
            c = None
    if c is None:
        _prune_dead()
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False only so close_all/_prune_dead can close it; each thread still uses its own
        c = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        _local.conn = c
        with _conn_lock:
            _open_connections[c] = threading.current_thread()
    return c


def close_conn():
    """Closes the current thread's connection."""
    c = getattr(_local, "conn", None)
    if c is not None:
        try:
            c.close()
        except Exception:
            pass
        with _conn_lock:
            _open_connections.pop(c, None)
        delattr(_local, "conn")


def close_all():
    """Closes all tracked SQLite connections across all threads; each thread reconnects on its next conn()."""
    with _conn_lock:
        conns = list(_open_connections)
        _open_connections.clear()
    for c in conns:
        try:
            c.close()
        except Exception:
            pass
    if hasattr(_local, "conn"):
        delattr(_local, "conn")


atexit.register(close_all)


MIGRATIONS = [
    # (table, column, definition) added after the first release; applied once to existing databases
    ("classes", "instruction", "TEXT"),
    ("classes", "adapted_from", "REAL"),
    ("users", "password_hash", "TEXT"),            # "scrypt$<salt hex>$<hash hex>"; NULL = local name-only profile
    ("courses", "plan_questions", "INTEGER"),      # remembered so interrupted planning can be redone
    ("courses", "plan_classes", "INTEGER"),
    ("classes", "opened_at", "REAL"),              # first time the student opened the lesson
    ("courses", "mode", "TEXT NOT NULL DEFAULT 'learn'"),  # learn | test_prep | readiness | semester | problem_sprint | thematic_reference
    ("courses", "exam_date", "TEXT"),
    ("courses", "workspace", "TEXT"),              # math | code | lab: where its classes open
    ("users", "privacy_version", "TEXT"),          # privacy notice version the user accepted
    ("users", "privacy_accepted_at", "REAL"),
    ("users", "upload_consent_at", "REAL"),        # consent to send uploaded materials to the AI provider
    ("classes", "meta", "TEXT NOT NULL DEFAULT '{}'"),  # semester plan: {week, unit, kind: lesson|review|midterm|final};
                                                        # sprint: {kind: primer|problem, problemIndex, statement, sprint, solved}
    ("courses", "weeks", "INTEGER"),               # semester length the student asked for
    ("courses", "auto_cleanup", "INTEGER NOT NULL DEFAULT 0"),  # problem sprint: cleared once every problem is done
    ("courses", "cleared_at", "REAL"),             # when it was cleared (status 'cleared'); purged after the retention days
]


def init_db():
    c = conn()
    c.executescript(SCHEMA)
    for table, column, definition in MIGRATIONS:
        cols = {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    c.commit()


def next_unstarted_class(course_id: str, after_seq: int) -> Optional[Dict[str, Any]]:
    """The first later class the student hasn't opened a quiz on yet: safe to rewrite."""
    return _row(conn().execute(
        "SELECT * FROM classes WHERE course_id = ? AND seq > ? AND attempts = 0 AND completed = 0 AND opened_at IS NULL "
        "ORDER BY seq LIMIT 1", (course_id, after_seq)).fetchone())


def _row(r: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLUMNS & d.keys():
        try:
            d[k] = json.loads(d[k]) if d[k] else ({} if k in _DICT_COLUMNS else [])
        except (TypeError, json.JSONDecodeError):
            pass
    return d


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ---- users ----
# Columns a user dict may carry out of these helpers (they reach the browser); never password_hash.
# Sign-in code reads the hash with get_user_by_name / get_user_auth.
USER_COLUMNS = "id, name, created_at, last_seen"


def get_or_create_user(name: str) -> Dict[str, Any]:
    now = time.time()
    c = conn()
    row = c.execute(f"SELECT {USER_COLUMNS} FROM users WHERE name = ?", (name,)).fetchone()
    if row:
        c.execute("UPDATE users SET last_seen = ? WHERE id = ?", (now, row["id"]))
        c.commit()
        return {**dict(row), "last_seen": now}
    uid = _new_id("u")
    c.execute("INSERT INTO users (id, name, created_at, last_seen) VALUES (?, ?, ?, ?)", (uid, name, now, now))
    c.commit()
    return {"id": uid, "name": name, "created_at": now, "last_seen": now}


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    return _row(conn().execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone())


def get_user_auth(user_id: str) -> Optional[Dict[str, Any]]:
    """The user row with its password hash, for password checks only; never return it to a client."""
    return _row(conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def list_users() -> List[Dict[str, Any]]:
    rows = conn().execute("""
        SELECT u.id, u.name, u.created_at, u.last_seen, COUNT(c.id) AS course_count FROM users u
        LEFT JOIN courses c ON c.user_id = u.id GROUP BY u.id ORDER BY u.last_seen DESC
    """).fetchall()
    return [dict(r) for r in rows]


# ---- courses ----
def create_course(user_id: str, title: str, goal: str, materials_text: str, filenames: List[str],
                  mode: str = "learn", exam_date: Optional[str] = None) -> Dict[str, Any]:
    now = time.time()
    cid = _new_id("course")
    conn().execute(
        "INSERT INTO courses (id, user_id, title, goal, status, materials_text, filenames, mode, exam_date, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'planning', ?, ?, ?, ?, ?, ?)",
        (cid, user_id, title, goal, materials_text, json.dumps(filenames), mode, exam_date, now, now))
    conn().commit()
    return get_course(cid)


def update_course(course_id: str, **fields):
    if not fields:
        return
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = [json.dumps(v) if k in JSON_COLUMNS else v for k, v in fields.items()]
    conn().execute(f"UPDATE courses SET {cols} WHERE id = ?", (*vals, course_id))
    conn().commit()
    if "status" in fields:
        _forget_cleared()


def get_course(course_id: str) -> Optional[Dict[str, Any]]:
    return _row(conn().execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone())


def list_courses(user_id: str) -> List[Dict[str, Any]]:
    rows = conn().execute("""
        SELECT c.id, c.title, c.subject, c.goal, c.status, c.error, c.job_id, c.mode, c.exam_date, c.workspace, c.auto_cleanup,
               c.created_at, c.updated_at,
               COUNT(k.id) AS class_count,
               SUM(k.status = 'ready') AS ready_count,
               SUM(k.status = 'planned') AS planned_count,
               SUM(k.completed) AS completed_count,
               AVG(k.score) AS avg_score
        FROM courses c LEFT JOIN classes k ON k.course_id = c.id
        WHERE c.user_id = ? AND c.status != 'cleared' GROUP BY c.id ORDER BY c.updated_at DESC
    """, (user_id,)).fetchall()
    return [{**dict(r), "ready_count": r["ready_count"] or 0, "planned_count": r["planned_count"] or 0,
             "completed_count": r["completed_count"] or 0} for r in rows]


def delete_course(course_id: str):
    conn().execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn().commit()
    _forget_cleared()


# ---- problem sprints: soft clear, undo, purge (sprint.py) ----
CLEARED_TTL = 5.0  # seconds; clear/restore/delete drop the cache at once, this only bounds other writers
_cleared_cache: Dict[str, Any] = {"at": 0.0, "ids": frozenset()}
_cleared_lock = threading.Lock()


def _forget_cleared():
    with _cleared_lock:
        _cleared_cache["at"] = 0.0


def cleared_course_ids() -> frozenset:
    """Ids of every cleared course (id column only), cached CLEARED_TTL seconds: topic listings check it per topic."""
    with _cleared_lock:
        if time.monotonic() - _cleared_cache["at"] < CLEARED_TTL:
            return _cleared_cache["ids"]
    ids = frozenset(r["id"] for r in conn().execute("SELECT id FROM courses WHERE status = 'cleared'").fetchall())
    with _cleared_lock:
        _cleared_cache.update(at=time.monotonic(), ids=ids)
    return ids


def course_owner(course_id: str) -> Optional[str]:
    """user_id of a course (None if missing or shared), without reading the rest of the row."""
    row = conn().execute("SELECT user_id FROM courses WHERE id = ?", (course_id,)).fetchone()
    return row["user_id"] if row else None


def clear_course(course_id: str) -> Optional[float]:
    """Hides a finished auto-clean sprint (status 'cleared'); returns cleared_at, or None when it was not cleared
    (already cleared, or kept/restored meanwhile: the check and the write are one statement). Nothing is deleted
    until cleared_due() picks it."""
    now = time.time()
    cur = conn().execute("UPDATE courses SET status = 'cleared', cleared_at = ?, updated_at = ? "
                         "WHERE id = ? AND auto_cleanup = 1 AND status != 'cleared'", (now, now, course_id))
    conn().commit()
    _forget_cleared()
    return now if cur.rowcount else None


def restore_course(course_id: str, only_cleared: bool = False) -> bool:
    """Back from 'cleared' (other statuses stay as they are) with auto-clean off for good, so finishing the last
    step again never re-clears it (keep and undo both land here). only_cleared: change nothing unless it is cleared.
    Returns whether a row changed."""
    cur = conn().execute(f"""
        UPDATE courses SET status = CASE WHEN status = 'cleared' THEN 'ready' ELSE status END, cleared_at = NULL,
               auto_cleanup = 0, updated_at = ? WHERE id = ?{" AND status = 'cleared'" if only_cleared else ""}
    """, (time.time(), course_id))
    conn().commit()
    _forget_cleared()
    return bool(cur.rowcount)


def list_cleared(user_id: str) -> List[Dict[str, Any]]:
    """This user's cleared sprints that can still be restored."""
    rows = conn().execute("SELECT id, title, mode, cleared_at FROM courses WHERE user_id = ? AND status = 'cleared' "
                          "ORDER BY cleared_at DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def cleared_due(cutoff: float) -> List[str]:
    """Course ids to purge: auto-clean problem sprints cleared before `cutoff`. Never any other course."""
    rows = conn().execute("""
        SELECT id FROM courses WHERE mode = 'problem_sprint' AND auto_cleanup = 1 AND status = 'cleared'
          AND cleared_at IS NOT NULL AND cleared_at < ?
    """, (cutoff,)).fetchall()
    return [r["id"] for r in rows]


# ---- classes ----
def _insert_class(c: sqlite3.Connection, course_id: str, seq: int, item: Dict[str, Any], now: float):
    c.execute(
        "INSERT INTO classes (id, course_id, seq, title, objectives, concepts, status, meta, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (_new_id("class"), course_id, seq, item["title"], json.dumps(item.get("objectives", [])),
         json.dumps(item.get("concepts", [])), item.get("status", "pending"), json.dumps(item.get("meta") or {}), now))


def replace_classes(course_id: str, outline: List[Dict[str, Any]]):
    now = time.time()
    c = conn()
    c.execute("DELETE FROM classes WHERE course_id = ?", (course_id,))
    for seq, item in enumerate(outline, start=1):
        _insert_class(c, course_id, seq, item, now)
    c.commit()


def append_classes(course_id: str, outline: List[Dict[str, Any]]) -> int:
    """Adds classes after the last one; returns the first new seq."""
    now = time.time()
    c = conn()
    start = (c.execute("SELECT MAX(seq) FROM classes WHERE course_id = ?", (course_id,)).fetchone()[0] or 0) + 1
    for seq, item in enumerate(outline, start=start):
        _insert_class(c, course_id, seq, item, now)
    c.commit()
    return start


def list_classes(course_id: str) -> List[Dict[str, Any]]:
    rows = conn().execute("SELECT * FROM classes WHERE course_id = ? ORDER BY seq", (course_id,)).fetchall()
    return [_row(r) for r in rows]


def update_class(class_id: str, **fields):
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = [json.dumps(v) if k in JSON_COLUMNS else v for k, v in fields.items()]
    conn().execute(f"UPDATE classes SET {cols} WHERE id = ?", (*vals, class_id))
    conn().commit()


def release_next_planned(course_id: str, max_ahead: Optional[int] = 2) -> bool:
    """Semester courses are written as the student goes: the first 'planned' class becomes 'pending' only when no
    class is pending, being written or failed, and fewer than `max_ahead` written classes are still unfinished
    (None: no limit, "write it now"). One UPDATE, so two concurrent calls never release two classes."""
    ahead = "" if max_ahead is None else \
        "AND (SELECT COUNT(*) FROM classes WHERE course_id = ? AND status = 'ready' AND completed = 0) < ?"
    c = conn()
    cur = c.execute(f"""
        UPDATE classes SET status = 'pending', updated_at = ?
        WHERE id = (SELECT id FROM classes WHERE course_id = ? AND status = 'planned' ORDER BY seq LIMIT 1)
          AND NOT EXISTS (SELECT 1 FROM classes WHERE course_id = ? AND status IN ('pending', 'generating', 'error'))
          {ahead}
    """, (time.time(), course_id, course_id, *(() if max_ahead is None else (course_id, max_ahead))))
    c.commit()
    return cur.rowcount == 1


def class_for_topic(topic_id: str) -> Optional[Dict[str, Any]]:
    return _row(conn().execute("SELECT * FROM classes WHERE topic_id = ?", (topic_id,)).fetchone())


def mark_class_opened(topic_id: str) -> Optional[Dict[str, Any]]:
    klass = class_for_topic(topic_id)
    if klass and not klass.get("opened_at"):
        update_class(klass["id"], opened_at=time.time())
    return klass


def reset_stuck_classes():
    """A class left 'generating' by a crash or restart goes back to 'pending' so it can resume."""
    conn().execute("UPDATE classes SET status = 'pending' WHERE status = 'generating'")
    conn().commit()


def interrupted_planning() -> List[Dict[str, Any]]:
    """Courses whose planning job died with the process; their materials are stored, so they can be re-planned."""
    return [_row(r) for r in conn().execute("SELECT * FROM courses WHERE status = 'planning'").fetchall()]


def courses_with_pending_classes() -> List[str]:
    rows = conn().execute("""
        SELECT DISTINCT c.id FROM courses c JOIN classes k ON k.course_id = c.id
        WHERE c.status = 'generating' AND k.status = 'pending'
    """).fetchall()
    return [r["id"] for r in rows]


# ---- lessons & attempts ----
def upsert_lesson(topic: Dict[str, Any], course_id: Optional[str] = None):
    c = conn()
    existing = c.execute("SELECT course_id FROM lessons WHERE topic_id = ?", (topic["id"],)).fetchone()
    course_id = course_id or (existing["course_id"] if existing else None) or (topic.get("source") or {}).get("courseId")
    if course_id and not c.execute("SELECT 1 FROM courses WHERE id = ?", (course_id,)).fetchone():
        course_id = None
    c.execute("""
        INSERT INTO lessons (topic_id, course_id, title, category, body, updated_at) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(topic_id) DO UPDATE SET course_id = excluded.course_id, title = excluded.title,
            category = excluded.category, body = excluded.body, updated_at = excluded.updated_at
    """, (topic["id"], course_id, topic.get("title", ""), topic.get("category", ""),
          json.dumps(topic, ensure_ascii=False), time.time()))
    c.commit()


def get_lesson(topic_id: str) -> Optional[Dict[str, Any]]:
    r = conn().execute("SELECT body FROM lessons WHERE topic_id = ?", (topic_id,)).fetchone()
    return json.loads(r["body"]) if r else None


def answer_index(q: Any) -> Optional[int]:
    """Same rule as the quiz player's answerIndex(): an integer (or digit string) index into the options, else None."""
    if not isinstance(q, dict):
        return None
    v = q.get("correctAnswer", q.get("correct"))
    if isinstance(v, str) and v.isdigit():
        v = int(v)
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v < len(q.get("options") or []) else None


def _gradable(q: Any) -> bool:
    return answer_index(q) is not None


def reset_class_progress(class_id: str, topic_id: Optional[str]):
    """A rewritten class starts over: its old quiz answers no longer match its questions."""
    c = conn()
    if topic_id:
        c.execute("DELETE FROM quiz_attempts WHERE topic_id = ?", (topic_id,))
    c.execute("UPDATE classes SET completed = 0, attempts = 0, score = NULL, updated_at = ? WHERE id = ?", (time.time(), class_id))
    c.commit()


def record_attempt(user_id: Optional[str], topic_id: str, question_id: str, selected: int, is_correct: bool):
    c = conn()
    c.execute("INSERT INTO quiz_attempts (user_id, topic_id, question_id, selected, is_correct, created_at) "
              "VALUES (?, ?, ?, ?, ?, ?)", (user_id, topic_id, str(question_id), selected, int(is_correct), time.time()))
    c.commit()
    # A class's score is the share of its quiz questions whose LATEST attempt is correct.
    klass = class_for_topic(topic_id)
    if not klass:
        return None
    rows = c.execute("""
        SELECT a.is_correct FROM quiz_attempts a
        JOIN (SELECT question_id, MAX(id) AS last_id FROM quiz_attempts
              WHERE topic_id = ? AND (user_id IS ? OR user_id = ?) GROUP BY question_id) l ON a.id = l.last_id
    """, (topic_id, user_id, user_id)).fetchall()
    lesson = get_lesson(topic_id) or {}
    total = max(sum(map(_gradable, lesson.get("quiz") or [])), len(rows), 1)
    score = sum(r["is_correct"] for r in rows) / total
    completed = int(len(rows) >= total)
    update_class(klass["id"], score=score, attempts=klass["attempts"] + 1, completed=completed)
    return {"classId": klass["id"], "courseId": klass["course_id"], "seq": klass["seq"],
            "score": score, "completed": bool(completed), "justCompleted": bool(completed and not klass["completed"])}


# ---- accounts & sessions (used when SCIEDU_AUTH=1) ----
SESSION_DAYS = 30


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: Optional[str]) -> bool:
    try:
        scheme, salt_hex, digest_hex = (stored or "").split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(digest.hex(), digest_hex)


def get_user_by_name(name: str) -> Optional[Dict[str, Any]]:
    return _row(conn().execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone())


def create_account(name: str, password: str) -> Dict[str, Any]:
    now = time.time()
    uid = _new_id("u")
    conn().execute("INSERT INTO users (id, name, created_at, last_seen, password_hash) VALUES (?, ?, ?, ?, ?)",
                   (uid, name, now, now, hash_password(password)))
    conn().commit()
    return {"id": uid, "name": name}


def set_password(user_id: str, password: str):
    conn().execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    conn().commit()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    c = conn()
    c.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    c.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
              (_token_hash(token), user_id, now, now + SESSION_DAYS * 86400))
    c.execute("UPDATE users SET last_seen = ? WHERE id = ?", (now, user_id))
    c.commit()
    return token


def user_for_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    row = conn().execute(
        "SELECT u.id, u.name FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
        (_token_hash(token), time.time())).fetchone()
    return dict(row) if row else None


def end_session(token: str):
    conn().execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
    conn().commit()


# ---- privacy: consent, export, delete (PRIVACY_AND_DEPLOYMENT.md §3) ----
# Every table keyed by user_id besides users, courses, classes, lessons and sessions. Some are created by
# engage.py and advisor.py in the same database; tables that don't exist yet are skipped.
USER_DATA_TABLES = ("quiz_attempts", "xp_events", "quest_days", "engage_prefs", "freeze_days",
                    "activity_results", "review_items", "completed_courses", "student_notes", "semester_plans",
                    "student_carts", "advisor_prefs")
_SECRET_USER_COLUMNS = ("password", "token", "secret", "hash")


def set_consent(user_id: str, kind: str, version: Optional[str] = None):
    """Records consent: kind "privacy" stores the accepted notice version, "upload" the upload consent time."""
    now = time.time()
    if kind == "privacy":
        conn().execute("UPDATE users SET privacy_version = ?, privacy_accepted_at = ? WHERE id = ?", (version, now, user_id))
    elif kind == "upload":
        conn().execute("UPDATE users SET upload_consent_at = ? WHERE id = ?", (now, user_id))
    else:
        raise ValueError(f"unknown consent kind: {kind!r}")
    conn().commit()


def get_consent(user_id: str) -> Dict[str, Any]:
    r = conn().execute("SELECT privacy_version, privacy_accepted_at, upload_consent_at FROM users WHERE id = ?",
                       (user_id,)).fetchone()
    return {"privacyVersion": r["privacy_version"] if r else None,
            "privacyAcceptedAt": r["privacy_accepted_at"] if r else None,
            "uploadConsentAt": r["upload_consent_at"] if r else None}


def get_student_notes(user_id: str) -> str:
    """Returns the student's written notes/scratchpad text, or empty string."""
    if not user_id:
        return ""
    r = conn().execute("SELECT notes_text FROM student_notes WHERE user_id = ?", (user_id,)).fetchone()
    return r["notes_text"] if r else ""


def save_student_notes(user_id: str, notes_text: str) -> Dict[str, Any]:
    """Persists student notes/scratchpad text."""
    if not user_id:
        raise ValueError("user_id is required")
    now = time.time()
    c = conn()
    c.execute(
        "INSERT INTO student_notes (user_id, notes_text, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET notes_text = excluded.notes_text, updated_at = excluded.updated_at",
        (user_id, notes_text or "", now),
    )
    c.commit()
    return {"user_id": user_id, "notes_text": notes_text or "", "updated_at": now}



def _existing_user_tables(c: sqlite3.Connection) -> List[str]:
    names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return [t for t in USER_DATA_TABLES if t in names]


def _marks(items: List[Any]) -> str:
    return ", ".join("?" * len(items))


def user_course_ids(user_id: str) -> List[str]:
    return [r[0] for r in conn().execute("SELECT id FROM courses WHERE user_id = ?", (user_id,))]


def user_topic_ids(course_ids: List[str]) -> List[str]:
    """Topic ids of these courses: their classes, plus lesson snapshots by course_id or by body source.courseId
    (lessons keep course_id NULL after a course delete, so only the body still links them)."""
    course_ids = list(course_ids)
    if not course_ids:
        return []
    m = _marks(course_ids)
    rows = conn().execute(f"""
        SELECT topic_id FROM classes WHERE course_id IN ({m}) AND topic_id IS NOT NULL
        UNION
        SELECT topic_id FROM lessons WHERE course_id IN ({m})
           OR (CASE WHEN json_valid(body) THEN json_extract(body, '$.source.courseId') END) IN ({m})
    """, (*course_ids, *course_ids, *course_ids)).fetchall()
    return [r[0] for r in rows]


def _delete_lessons(c: sqlite3.Connection, topic_ids: List[str]) -> int:
    topic_ids = list(topic_ids)
    if not topic_ids:
        return 0
    return c.execute(f"DELETE FROM lessons WHERE topic_id IN ({_marks(topic_ids)})", topic_ids).rowcount


def delete_lessons(topic_ids: List[str]) -> int:
    """Deletes these lesson snapshots; returns how many were removed."""
    c = conn()
    with c:
        return _delete_lessons(c, topic_ids)


def export_user(user_id: str) -> Dict[str, Any]:
    """Everything stored about one user, for "Export my data". No password hash, tokens or sessions."""
    c = conn()
    user = get_user_auth(user_id)  # the whole row, consent fields included; secret columns are dropped below
    if user:
        user = {k: v for k, v in user.items() if not any(s in k.lower() for s in _SECRET_USER_COLUMNS)}
    courses = [_row(r) for r in c.execute("SELECT * FROM courses WHERE user_id = ? ORDER BY created_at", (user_id,))]
    for course in courses:
        course["classes"] = list_classes(course["id"])
    topic_ids = user_topic_ids([k["id"] for k in courses])
    lessons = []
    if topic_ids:
        for r in c.execute(f"SELECT * FROM lessons WHERE topic_id IN ({_marks(topic_ids)}) ORDER BY updated_at", topic_ids):
            d = dict(r)
            try:
                d["body"] = json.loads(d["body"])
            except (TypeError, json.JSONDecodeError):
                pass
            lessons.append(d)
    tables = {t: [dict(r) for r in c.execute(f"SELECT * FROM {t} WHERE user_id = ?", (user_id,))]
              for t in _existing_user_tables(c)}
    return {"user": user, "courses": courses, "lessons": lessons, "tables": tables, "consent": get_consent(user_id)}


def delete_user(user_id: str) -> Dict[str, int]:
    """Deletes one user and all their data in a single transaction; returns rows deleted per table.
    Explicit deletes (no reliance on cascades). Rows with user_id NULL (local-mode shared) are never touched.
    Idempotent: a second call deletes nothing."""
    c = conn()
    counts: Dict[str, int] = {}
    with c:
        course_ids = user_course_ids(user_id)
        counts["lessons"] = _delete_lessons(c, user_topic_ids(course_ids))
        for t in _existing_user_tables(c):
            counts[t] = c.execute(f"DELETE FROM {t} WHERE user_id = ?", (user_id,)).rowcount
        counts["sessions"] = c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,)).rowcount
        counts["classes"] = (c.execute(f"DELETE FROM classes WHERE course_id IN ({_marks(course_ids)})", course_ids).rowcount
                             if course_ids else 0)
        counts["courses"] = c.execute("DELETE FROM courses WHERE user_id = ?", (user_id,)).rowcount
        counts["users"] = c.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount
    _forget_cleared()
    return counts
