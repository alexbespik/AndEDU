"""
Engagement loop (gamified, without the dark patterns): XP for real learning actions, a daily goal,
a streak with freezes, three daily quests, badges, and spaced review of every question the student missed.

The server decides every amount: clients only say *what* happened (a source and a reference), and each
(source, reference) pays once per day, or once ever for one-time achievements, so XP can't be farmed.
Days are the student's local calendar days (sent by the browser, checked to be within a day of UTC).
"""
import datetime
import hashlib
import json
import math
import threading
import time
from typing import Any, Dict, List, Optional

import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS xp_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,
    source     TEXT NOT NULL,
    ref        TEXT NOT NULL DEFAULT '',
    amount     INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS xp_user_day ON xp_events (user_id, day);
CREATE INDEX IF NOT EXISTS xp_user_source_ref ON xp_events (user_id, source, ref);
CREATE TABLE IF NOT EXISTS quest_days (
    user_id  TEXT NOT NULL,
    day      TEXT NOT NULL,
    ids      TEXT NOT NULL,                 -- JSON list of the quest ids picked for that day
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS engage_prefs (
    user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    daily_goal INTEGER NOT NULL DEFAULT 30,
    freezes    INTEGER NOT NULL DEFAULT 1,
    focus_mode INTEGER NOT NULL DEFAULT 0,
    badges     TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS freeze_days (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day     TEXT NOT NULL,
    PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS activity_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id   TEXT NOT NULL,
    kind       TEXT NOT NULL,              -- speed | flashcards | timeline | practice
    correct    INTEGER NOT NULL,
    total      INTEGER NOT NULL,
    points     INTEGER NOT NULL DEFAULT 0, -- speed-round points
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS activity_user_topic ON activity_results (user_id, topic_id);
CREATE TABLE IF NOT EXISTS review_items (
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic_id    TEXT NOT NULL,
    question_id TEXT NOT NULL,
    box         INTEGER NOT NULL DEFAULT 0,
    due_day     TEXT NOT NULL,
    lapses      INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL NOT NULL,
    PRIMARY KEY (user_id, topic_id, question_id)
);
"""

# source -> (xp, scope). scope: "day" = once per (ref, day); "ever" = once per ref; ("cap", n) = n per day
SOURCES = {
    "quiz_correct": (8, "day"),          # was 10 — reduced: quiz correct per ref per day
    "quiz_attempt": (0, "day"),          # unchanged: wrong answers don't reward
    "class_complete": (25, "ever"),      # was 20 — bonus for completing a full class
    "quiz_perfect": (15, "ever"),        # was 10 — perfect score bonus, once per class
    "practice_correct": (5, ("cap", 20)),  # was (8, "day") — cap at 20 correct per day (100 XP max from practice)
    "math_correct": (5, ("cap", 20)),    # was (8, "day") — same cap
    "review_correct": (8, "day"),        # was 6 — reviewing missed items is higher value
    "review_attempt": (0, "day"),        # unchanged
    "review_session": (10, ("cap", 2)),  # was cap 3 — reduced to 2 review session bonuses per day
    "ide_solved": (20, "ever"),          # was 15 — coding tasks are hard, one-time
    "sim_explored": (3, ("cap", 5)),     # was (5, "day") — cap at 5 unique sims per day (15 XP max)
    "lesson_read": (2, ("cap", 10)),     # was (3, "day") — cap at 10 lessons per day (20 XP max)
    "quests_bonus": (20, "day"),         # was 15 — completing all 3 quests deserves more
}
CLIENT_SOURCES = {"practice_correct", "math_correct", "ide_solved", "sim_explored", "lesson_read"}
CLIENT_DAILY_CAP = 40  # per client-reported source per day
DAILY_MAX = {"ide_solved": 5}  # "ever" sources whose refs the client names: at most this many new ones a day
CORRECT_SOURCES = ("quiz_correct", "practice_correct", "math_correct", "review_correct")
GOALS = (10, 20, 30, 50)                    # casual, regular, serious, intense
REVIEW_INTERVALS = (1, 3, 7, 14, 30)        # days until the next review, by Leitner box
MAX_FREEZES = 2

BADGES = [
    ("first_steps", "First steps", "Earn your first XP"),
    ("streak_3", "Warming up", "Study 3 days in a row"),
    ("streak_7", "One week strong", "Study 7 days in a row"),
    ("streak_30", "Habit formed", "Study 30 days in a row"),
    ("class_done", "Class dismissed", "Finish every question in a class"),
    ("perfect", "Flawless", "Get a class quiz 100% right"),
    ("sharp_50", "Sharp mind", "Answer 50 questions correctly"),
    ("reviewer", "Comeback", "Finish 3 review sessions"),
    ("coder", "Hello, world", "Solve 5 problems in the IDE"),
    ("explorer", "Explorer", "Explore 5 different simulations"),
    ("goal_7", "Goal getter", "Reach your daily goal on 7 days"),
    ("xp_1000", "Scholar", "Earn 1,000 XP"),
]


def init():
    db.conn().executescript(SCHEMA)
    db.conn().commit()


def utc_day() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def clean_day(value: Optional[str]) -> str:
    """The browser's local date, accepted only if it is a real date within a day of UTC."""
    try:
        d = datetime.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return utc_day()
    today = datetime.date.fromisoformat(utc_day())
    return d.isoformat() if abs((d - today).days) <= 1 else today.isoformat()


def _shift(day: str, n: int) -> str:
    return (datetime.date.fromisoformat(day) + datetime.timedelta(days=n)).isoformat()


# ---------------------------------------------------------------- preferences
def prefs(user_id: str) -> Dict[str, Any]:
    c = db.conn()
    row = c.execute("SELECT * FROM engage_prefs WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        c.execute("INSERT OR IGNORE INTO engage_prefs (user_id) VALUES (?)", (user_id,))
        c.commit()
        row = c.execute("SELECT * FROM engage_prefs WHERE user_id = ?", (user_id,)).fetchone()
    out = dict(row)
    out["badges"] = json.loads(out["badges"] or "{}")
    return out


def set_prefs(user_id: str, daily_goal: Optional[int] = None, focus_mode: Optional[bool] = None):
    prefs(user_id)
    c = db.conn()
    if daily_goal is not None:
        c.execute("UPDATE engage_prefs SET daily_goal = ? WHERE user_id = ?", (min(GOALS, key=lambda g: abs(g - daily_goal)), user_id))
    if focus_mode is not None:
        c.execute("UPDATE engage_prefs SET focus_mode = ? WHERE user_id = ?", (int(bool(focus_mode)), user_id))
    c.commit()


# ---------------------------------------------------------------- streaks
def _active_days(user_id: str) -> set:
    c = db.conn()
    days = {r[0] for r in c.execute("SELECT DISTINCT day FROM xp_events WHERE user_id = ? AND amount > 0", (user_id,))}
    days |= {r[0] for r in c.execute("SELECT day FROM freeze_days WHERE user_id = ?", (user_id,))}
    return days


def streak_info(user_id: str, today: str) -> Dict[str, Any]:
    days = _active_days(user_id)
    start = today if today in days else _shift(today, -1)   # today not done yet: the streak is still alive
    n, d = 0, start
    while d in days:
        n += 1
        d = _shift(d, -1)
    longest, run, prev = 0, 0, None
    for day in sorted(days):
        run = run + 1 if prev and _shift(prev, 1) == day else 1
        longest, prev = max(longest, run), day
    return {"streak": n, "longest": longest, "doneToday": today in days}


def _apply_freezes(user_id: str, today: str):
    """On the first activity of a day: if the student missed days and has freezes for all of them, spend them."""
    c = db.conn()
    days = _active_days(user_id)
    if not days or today in days:
        return
    last = max((d for d in days if d < today), default=None)
    if not last:
        return
    gap = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last)).days - 1
    p = prefs(user_id)
    if 0 < gap <= p["freezes"]:
        for i in range(1, gap + 1):
            c.execute("INSERT OR IGNORE INTO freeze_days (user_id, day) VALUES (?, ?)", (user_id, _shift(last, i)))
        c.execute("UPDATE engage_prefs SET freezes = freezes - ? WHERE user_id = ?", (gap, user_id))
        c.commit()


# ---------------------------------------------------------------- XP
def _xp_today(user_id: str, day: str) -> int:
    return db.conn().execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE user_id = ? AND day = ?",
                             (user_id, day)).fetchone()[0]


def _total_xp(user_id: str) -> int:
    return db.conn().execute("SELECT COALESCE(SUM(amount), 0) FROM xp_events WHERE user_id = ?", (user_id,)).fetchone()[0]


def level_for(total: int) -> Dict[str, int]:
    """Level n starts at 25 * (n - 1)^2 XP: quick early levels, slower later."""
    level = int(math.sqrt(total / 25)) + 1
    start, nxt = 25 * (level - 1) ** 2, 25 * level ** 2
    return {"level": level, "levelStart": start, "nextLevel": nxt}


# Sync handlers run in a thread pool: two identical requests at once (a double click) must not both pass the
# duplicate check. The server runs as one process (ARCHITECTURE.md §5.3), so a process lock is enough.
_award_lock = threading.RLock()


def award(user_id: str, day: str, source: str, ref: str = "") -> Dict[str, Any]:
    """Records XP for one action (if this action hasn't paid out already) and returns what changed."""
    with _award_lock:
        return _award(user_id, day, source, ref)


def _award(user_id: str, day: str, source: str, ref: str = "") -> Dict[str, Any]:
    if source not in SOURCES:
        raise ValueError(f"unknown XP source {source}")
    amount, scope = SOURCES[source]
    ref = str(ref)[:200]
    c = db.conn()
    if scope == "day":
        dup = c.execute("SELECT 1 FROM xp_events WHERE user_id = ? AND source = ? AND ref = ? AND day = ?", (user_id, source, ref, day)).fetchone()
    elif scope == "ever":
        dup = c.execute("SELECT 1 FROM xp_events WHERE user_id = ? AND source = ? AND ref = ?", (user_id, source, ref)).fetchone()
    else:
        if ref and c.execute("SELECT 1 FROM xp_events WHERE user_id = ? AND source = ? AND ref = ? AND day = ?", (user_id, source, ref, day)).fetchone():
            dup = True
        else:
            dup = c.execute("SELECT COUNT(*) FROM xp_events WHERE user_id = ? AND source = ? AND day = ?", (user_id, source, day)).fetchone()[0] >= scope[1]
    if not dup and source in DAILY_MAX:
        dup = c.execute("SELECT COUNT(*) FROM xp_events WHERE user_id = ? AND source = ? AND day = ?",
                        (user_id, source, day)).fetchone()[0] >= DAILY_MAX[source]
    if dup:
        return {"xp": 0}
    if source in CLIENT_SOURCES and c.execute("SELECT COUNT(*) FROM xp_events WHERE user_id = ? AND source = ? AND day = ?",
                                              (user_id, source, day)).fetchone()[0] >= CLIENT_DAILY_CAP:
        return {"xp": 0}  # invented references can't farm XP

    p = prefs(user_id)
    before_today = _xp_today(user_id, day)
    before_total = _total_xp(user_id)
    first_today = (amount > 0) and not streak_info(user_id, day)["doneToday"]
    if first_today:
        _apply_freezes(user_id, day)
    c.execute("INSERT INTO xp_events (user_id, day, source, ref, amount, created_at) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, day, source, ref, amount, time.time()))
    c.commit()

    s = streak_info(user_id, day)
    out = {"xp": amount, "source": source, "xpToday": before_today + amount, "goal": p["daily_goal"],
           "goalReached": before_today < p["daily_goal"] <= before_today + amount,
           "streak": s["streak"], "streakExtended": first_today, "freezeEarned": False,
           "levelUp": level_for(before_total + amount)["level"] > level_for(before_total)["level"],
           "level": level_for(before_total + amount)["level"]}
    if first_today and s["streak"] and s["streak"] % 7 == 0 and p["freezes"] < MAX_FREEZES:
        c.execute("UPDATE engage_prefs SET freezes = freezes + 1 WHERE user_id = ?", (user_id,))
        c.commit()
        out["freezeEarned"] = True
    out["newBadges"] = _check_badges(user_id, day)
    if source != "quests_bonus" and all(q["done"] for q in quests(user_id, day)):
        bonus = award(user_id, day, "quests_bonus", day)
        if bonus["xp"]:
            out["questsDone"] = True
            out["xp"] += bonus["xp"]
            out["xpToday"] = bonus["xpToday"]
            out["goalReached"] = out["goalReached"] or bonus["goalReached"]
            out["newBadges"] += bonus.get("newBadges", [])
    return out


# ---------------------------------------------------------------- quests & badges
def _counts(user_id: str, day: Optional[str] = None) -> Dict[str, int]:
    q = "SELECT source, COUNT(*) AS n FROM xp_events WHERE user_id = ?" + (" AND day = ?" if day else "") + " GROUP BY source"
    return {r["source"]: r["n"] for r in db.conn().execute(q, (user_id, day) if day else (user_id,))}


def quests(user_id: str, day: str) -> List[Dict[str, Any]]:
    goal = prefs(user_id)["daily_goal"]
    n = _counts(user_id, day)
    xp = _xp_today(user_id, day) - n.get("quests_bonus", 0) * SOURCES["quests_bonus"][0]
    pool = [
        ("correct", "Answer 5 questions correctly", sum(n.get(s, 0) for s in CORRECT_SOURCES), 5),
        ("practice", "Solve 3 practice problems", n.get("practice_correct", 0) + n.get("math_correct", 0), 3),
        ("review", "Finish a review session", n.get("review_session", 0), 1),
        ("sim", "Explore a simulation", n.get("sim_explored", 0), 1),
        ("read", "Read a lesson for a few minutes", n.get("lesson_read", 0), 1),
    ]
    # the day's two quests are picked once and stored, so finishing a review mid-day can't swap them
    c = db.conn()
    row = c.execute("SELECT ids FROM quest_days WHERE user_id = ? AND day = ?", (user_id, day)).fetchone()
    if row:
        ids = json.loads(row[0])
        by_id = {p[0]: p for p in pool}
        picked = [by_id[i] for i in ids if i in by_id]  # in the order they were picked
    else:
        if due_count(user_id, day) == 0 and not n.get("review_session"):
            pool = [p for p in pool if p[0] != "review"]
        seed = int(hashlib.sha256(f"{user_id}:{day}".encode()).hexdigest(), 16)
        picked = []
        while len(picked) < 2 and pool:
            picked.append(pool.pop(seed % len(pool)))
            seed //= 7
        c.execute("INSERT OR IGNORE INTO quest_days (user_id, day, ids) VALUES (?, ?, ?)", (user_id, day, json.dumps([p[0] for p in picked])))
        c.commit()
    out = [{"id": "xp", "title": f"Earn {goal} XP", "progress": min(xp, goal), "target": goal}]
    out += [{"id": i, "title": t, "progress": min(v, target), "target": target} for i, t, v, target in picked]
    for q in out:
        q["done"] = q["progress"] >= q["target"]
    return out


def _check_badges(user_id: str, day: str) -> List[Dict[str, str]]:
    p = prefs(user_id)
    have = p["badges"]
    n = _counts(user_id)
    c = db.conn()
    goal_days = c.execute("""SELECT COUNT(*) FROM (SELECT day FROM xp_events WHERE user_id = ? GROUP BY day
                             HAVING SUM(amount) >= ?)""", (user_id, p["daily_goal"])).fetchone()[0]
    sims = c.execute("SELECT COUNT(DISTINCT ref) FROM xp_events WHERE user_id = ? AND source = 'sim_explored'", (user_id,)).fetchone()[0]
    streak = streak_info(user_id, day)["longest"]
    earned = {
        "first_steps": _total_xp(user_id) > 0,
        "streak_3": streak >= 3, "streak_7": streak >= 7, "streak_30": streak >= 30,
        "class_done": n.get("class_complete", 0) > 0,
        "perfect": n.get("quiz_perfect", 0) > 0,
        "sharp_50": sum(n.get(s, 0) for s in CORRECT_SOURCES) >= 50,
        "reviewer": n.get("review_session", 0) >= 3,
        "coder": n.get("ide_solved", 0) >= 5,
        "explorer": sims >= 5,
        "goal_7": goal_days >= 7,
        "xp_1000": _total_xp(user_id) >= 1000,
    }
    new = [b for b in BADGES if earned.get(b[0]) and b[0] not in have]
    if new:
        have.update({b[0]: day for b in new})
        c.execute("UPDATE engage_prefs SET badges = ? WHERE user_id = ?", (json.dumps(have), user_id))
        c.commit()
    return [{"id": b[0], "name": b[1], "description": b[2]} for b in new]


# ---------------------------------------------------------------- spaced review
def remember_miss(user_id: str, topic_id: str, question_id: str, day: str):
    """A missed question comes back tomorrow; missing it again sends it back to the first box."""
    db.conn().execute("""
        INSERT INTO review_items (user_id, topic_id, question_id, box, due_day, lapses, updated_at)
        VALUES (?, ?, ?, 0, ?, 1, ?)
        ON CONFLICT (user_id, topic_id, question_id)
        DO UPDATE SET box = 0, due_day = excluded.due_day, lapses = lapses + 1, updated_at = excluded.updated_at
    """, (user_id, topic_id, str(question_id), _shift(day, 1), time.time()))
    db.conn().commit()


def due_count(user_id: str, day: str) -> int:
    return db.conn().execute("SELECT COUNT(*) FROM review_items WHERE user_id = ? AND due_day <= ?", (user_id, day)).fetchone()[0]


def next_due(user_id: str) -> Optional[str]:
    r = db.conn().execute("SELECT MIN(due_day) FROM review_items WHERE user_id = ?", (user_id,)).fetchone()
    return r[0] if r else None


def due_items(user_id: str, day: str, limit: int = 10) -> List[Dict[str, Any]]:
    rows = db.conn().execute("""SELECT * FROM review_items WHERE user_id = ? AND due_day <= ?
                                ORDER BY box, lapses DESC, due_day LIMIT ?""", (user_id, day, limit)).fetchall()
    return [dict(r) for r in rows]


def drop_item(user_id: str, topic_id: str, question_id: str):
    db.conn().execute("DELETE FROM review_items WHERE user_id = ? AND topic_id = ? AND question_id = ?", (user_id, topic_id, str(question_id)))
    db.conn().commit()


def review_result(user_id: str, topic_id: str, question_id: str, correct: bool, day: str) -> Dict[str, Any]:
    c = db.conn()
    row = c.execute("SELECT box FROM review_items WHERE user_id = ? AND topic_id = ? AND question_id = ?",
                    (user_id, topic_id, str(question_id))).fetchone()
    if not correct:
        remember_miss(user_id, topic_id, question_id, day)
        return {"box": 0, "nextReview": _shift(day, 1), "mastered": False}
    box = (row["box"] if row else 0) + 1
    if box >= len(REVIEW_INTERVALS):
        drop_item(user_id, topic_id, question_id)
        return {"box": box, "nextReview": None, "mastered": True}
    nxt = _shift(day, REVIEW_INTERVALS[box])
    c.execute("UPDATE review_items SET box = ?, due_day = ?, updated_at = ? WHERE user_id = ? AND topic_id = ? AND question_id = ?",
              (box, nxt, time.time(), user_id, topic_id, str(question_id)))
    c.commit()
    return {"box": box, "nextReview": nxt, "mastered": False}


# ---------------------------------------------------------------- dashboard
def continue_target(user_id: str) -> Optional[Dict[str, Any]]:
    """The next class to study: the earliest ready, unfinished class of the most recently used course."""
    r = db.conn().execute("""
        SELECT c.id AS course_id, c.title AS course_title, k.seq, k.title, k.topic_id, k.score
        FROM courses c JOIN classes k ON k.course_id = c.id
        WHERE c.user_id = ? AND k.status = 'ready' AND k.completed = 0 AND k.topic_id IS NOT NULL
        ORDER BY c.updated_at DESC, k.seq LIMIT 1
    """, (user_id,)).fetchone()
    return dict(r) if r else None


def progress(user_id: str, day: str) -> Dict[str, Any]:
    p = prefs(user_id)
    s = streak_info(user_id, day)
    total = _total_xp(user_id)
    week = []
    active = _active_days(user_id)
    for i in range(6, -1, -1):
        d = _shift(day, -i)
        xp = _xp_today(user_id, d)
        frozen = db.conn().execute("SELECT 1 FROM freeze_days WHERE user_id = ? AND day = ?", (user_id, d)).fetchone() is not None
        week.append({"day": d, "xp": xp, "active": d in active, "frozen": frozen})
    have = p["badges"]
    return {
        "day": day, "xpToday": _xp_today(user_id, day), "dailyGoal": p["daily_goal"], "goals": list(GOALS),
        "streak": s["streak"], "longestStreak": s["longest"], "doneToday": s["doneToday"], "freezes": p["freezes"],
        "totalXp": total, **level_for(total), "week": week, "quests": quests(user_id, day),
        "badges": [{"id": b, "name": n, "description": d, "earned": b in have, "earnedOn": have.get(b)} for b, n, d in BADGES],
        "reviewDue": due_count(user_id, day), "nextReview": next_due(user_id),
        "continue": continue_target(user_id), "focusMode": bool(p["focus_mode"]),
    }


# ---------------------------------------------------------------- practice & games score (separate from the quiz)
# Speed rounds, flashcards, timeline ordering and practice puzzles are recorded here and NEVER touch the class quiz
# score (classes.score), which is what adaptation and course progress read.
ACTIVITY_KINDS = ("speed", "flashcards", "timeline", "practice")


def record_activity(user_id: str, topic_id: str, kind: str, correct: int, total: int, points: int = 0) -> Dict[str, Any]:
    if kind not in ACTIVITY_KINDS or total <= 0:
        raise ValueError("unknown activity or empty result")
    correct = max(0, min(int(correct), int(total)))
    db.conn().execute("INSERT INTO activity_results (user_id, topic_id, kind, correct, total, points, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (user_id, str(topic_id)[:120], kind, correct, int(total), max(0, int(points)), time.time()))
    db.conn().commit()
    return activity_summary(user_id, topic_id)


def activity_summary(user_id: str, topic_id: str) -> Dict[str, Any]:
    """Best result per activity and their average: the 'practice & games' score shown next to the quiz score."""
    rows = db.conn().execute("""SELECT kind, MAX(CAST(correct AS REAL) / total) AS best, MAX(points) AS points, COUNT(*) AS plays
                                FROM activity_results WHERE user_id = ? AND topic_id = ? GROUP BY kind""", (user_id, topic_id)).fetchall()
    kinds = {r["kind"]: {"best": round(r["best"], 3), "points": r["points"], "plays": r["plays"]} for r in rows}
    score = round(sum(k["best"] for k in kinds.values()) / len(kinds), 3) if kinds else None
    klass = db.class_for_topic(topic_id)
    return {"topicId": topic_id, "activityScore": score, "activities": kinds,
            "quizScore": klass.get("score") if klass else None, "quizCounts": bool(klass)}
