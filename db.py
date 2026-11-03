"""
SQLite persistence for &.edu Studio: profiles, courses, the ordered classes in each course,
lesson snapshots and quiz attempts. Uses only the standard library.

Topic JSON files in content/topics stay the live format agents write to; every save is also
recorded in `lessons` so courses keep their history even if a file is edited or removed.
"""
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
    status         TEXT NOT NULL,          -- planning | diagnostic_ready | generating | ready | error
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
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | generating | ready | error
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
"""

JSON_COLUMNS = {"filenames", "concepts", "diagnostic", "answers", "mastery", "objectives"}


def conn() -> sqlite3.Connection:
    """One connection per thread (FastAPI runs sync handlers in a thread pool)."""
    c = getattr(_local, "conn", None)
    if c is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        _local.conn = c
    return c


MIGRATIONS = [
    # (table, column, definition) added after the first release; applied once to existing databases
    ("classes", "instruction", "TEXT"),
    ("classes", "adapted_from", "REAL"),
    ("users", "password_hash", "TEXT"),            # "scrypt$<salt hex>$<hash hex>"; NULL = local name-only profile
    ("courses", "plan_questions", "INTEGER"),      # remembered so interrupted planning can be redone
    ("courses", "plan_classes", "INTEGER"),
    ("classes", "opened_at", "REAL"),              # first time the student opened the lesson
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
            d[k] = json.loads(d[k]) if d[k] else ([] if k != "answers" and k != "mastery" else {})
        except (TypeError, json.JSONDecodeError):
            pass
    return d


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ---- users ----
def get_or_create_user(name: str) -> Dict[str, Any]:
    now = time.time()
    c = conn()
    row = c.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()
    if row:
        c.execute("UPDATE users SET last_seen = ? WHERE id = ?", (now, row["id"]))
        c.commit()
        return {**dict(row), "last_seen": now}
    uid = _new_id("u")
    c.execute("INSERT INTO users (id, name, created_at, last_seen) VALUES (?, ?, ?, ?)", (uid, name, now, now))
    c.commit()
    return {"id": uid, "name": name, "created_at": now, "last_seen": now}


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    return _row(conn().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def list_users() -> List[Dict[str, Any]]:
    rows = conn().execute("""
        SELECT u.*, COUNT(c.id) AS course_count FROM users u
        LEFT JOIN courses c ON c.user_id = u.id GROUP BY u.id ORDER BY u.last_seen DESC
    """).fetchall()
    return [dict(r) for r in rows]


# ---- courses ----
def create_course(user_id: str, title: str, goal: str, materials_text: str, filenames: List[str]) -> Dict[str, Any]:
    now = time.time()
    cid = _new_id("course")
    conn().execute(
        "INSERT INTO courses (id, user_id, title, goal, status, materials_text, filenames, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'planning', ?, ?, ?, ?)",
        (cid, user_id, title, goal, materials_text, json.dumps(filenames), now, now))
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


def get_course(course_id: str) -> Optional[Dict[str, Any]]:
    return _row(conn().execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone())


def list_courses(user_id: str) -> List[Dict[str, Any]]:
    rows = conn().execute("""
        SELECT c.id, c.title, c.subject, c.goal, c.status, c.error, c.job_id, c.created_at, c.updated_at,
               COUNT(k.id) AS class_count,
               SUM(k.status = 'ready') AS ready_count,
               SUM(k.completed) AS completed_count,
               AVG(k.score) AS avg_score
        FROM courses c LEFT JOIN classes k ON k.course_id = c.id
        WHERE c.user_id = ? GROUP BY c.id ORDER BY c.updated_at DESC
    """, (user_id,)).fetchall()
    return [{**dict(r), "ready_count": r["ready_count"] or 0, "completed_count": r["completed_count"] or 0} for r in rows]


def delete_course(course_id: str):
    conn().execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn().commit()


# ---- classes ----
def replace_classes(course_id: str, outline: List[Dict[str, Any]]):
    now = time.time()
    c = conn()
    c.execute("DELETE FROM classes WHERE course_id = ?", (course_id,))
    for seq, item in enumerate(outline, start=1):
        c.execute(
            "INSERT INTO classes (id, course_id, seq, title, objectives, concepts, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_new_id("class"), course_id, seq, item["title"], json.dumps(item.get("objectives", [])),
             json.dumps(item.get("concepts", [])), now))
    c.commit()


def list_classes(course_id: str) -> List[Dict[str, Any]]:
    rows = conn().execute("SELECT * FROM classes WHERE course_id = ? ORDER BY seq", (course_id,)).fetchall()
    return [_row(r) for r in rows]


def update_class(class_id: str, **fields):
    fields["updated_at"] = time.time()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = [json.dumps(v) if k in JSON_COLUMNS else v for k, v in fields.items()]
    conn().execute(f"UPDATE classes SET {cols} WHERE id = ?", (*vals, class_id))
    conn().commit()


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
    total = max(len(lesson.get("quiz") or []), len(rows), 1)
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
