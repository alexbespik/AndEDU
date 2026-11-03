"""
Course advisor: a local copy of a course catalog (W&M by default), the courses a student has done, and
what they can take next.

Getting the catalog: catalog.wm.edu and the Open Course List sit behind bot protection that answers scripts
with an empty challenge page, so the app cannot download them unattended. Instead the student (or an agent)
imports what their browser can see:
  - a catalog PDF (W&M publishes yearly catalogs; archived ones are on dspace.swem.wm.edu),
  - pasted text from a catalog or department page, or
  - JSON rows {code, title, credits, description, prereqs, attributes}.
parse_catalog_text() reads the usual "DEPT 123. Title. (3 Credits)" layout; anything it can't read can go
through the model (server.py) and come back as JSON rows.
"""
import json
import re
import time
from typing import Any, Dict, Iterable, List, Optional, Set

import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_courses (
    school      TEXT NOT NULL DEFAULT 'wm',
    code        TEXT NOT NULL,              -- "CSCI 141"
    title       TEXT NOT NULL,
    credits     TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    prereqs     TEXT NOT NULL DEFAULT '',   -- the catalog's own wording
    prereq_codes TEXT NOT NULL DEFAULT '[]',
    attributes  TEXT NOT NULL DEFAULT '[]', -- e.g. COLL 200, NQR
    source      TEXT NOT NULL DEFAULT '',
    updated_at  REAL NOT NULL,
    PRIMARY KEY (school, code)
);
CREATE TABLE IF NOT EXISTS completed_courses (
    user_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code     TEXT NOT NULL,
    title    TEXT NOT NULL DEFAULT '',
    grade    TEXT NOT NULL DEFAULT '',
    term     TEXT NOT NULL DEFAULT '',
    source   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, code)
);
"""

CODE_RE = re.compile(r"\b([A-Z]{2,5})\s?-?\s?(\d{3}[A-Z]?)\b")
ENTRY_RE = re.compile(r"^\s*([A-Z]{2,5})\s?(\d{3}[A-Z]?)\s*[.:-]\s*(.+?)\.\s*(?:\(([^)]*credits?[^)]*)\)|(\d(?:-\d)?\s*credits?))?", re.I)
PREREQ_RE = re.compile(r"(?:Prerequisites?(?:\(s\))?|Pre-?req(?:uisite)?s?)\s*[:\-]?\s*(.+?)(?:(?<=[a-z0-9)])\.\s|$)", re.I)
GRADE_RE = re.compile(r"(?<![A-Za-z])([A-D][+-]|[A-DFPS]|CR|TR|IP)(?![A-Za-z+-])")
NOT_COURSES = {"GPA", "SAT", "ACT", "ID", "USA", "PDF", "AM", "PM"}


def init():
    db.conn().executescript(SCHEMA)
    db.conn().commit()


def norm_code(dept: str, num: str) -> str:
    return f"{dept.upper()} {num.upper()}"


def find_codes(text: str) -> List[str]:
    out, seen = [], set()
    for d, n in CODE_RE.findall(text or ""):
        if d.upper() in NOT_COURSES:
            continue
        c = norm_code(d, n)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def parse_catalog_text(text: str) -> List[Dict[str, Any]]:
    """Splits catalog text into course entries: a line starting 'DEPT 123. Title.' opens an entry."""
    entries, cur = [], None
    for line in (text or "").splitlines():
        m = ENTRY_RE.match(line)
        if m and len(m.group(3)) < 140:
            if cur:
                entries.append(cur)
            credits = (m.group(4) or m.group(5) or "").strip()
            cur = {"code": norm_code(m.group(1), m.group(2)), "title": m.group(3).strip(" ."),
                   "credits": re.sub(r"\s*credits?", "", credits, flags=re.I).strip(), "body": line[m.end():]}
        elif cur:
            cur["body"] += " " + line.strip()
    if cur:
        entries.append(cur)
    out = []
    for e in entries:
        body = re.sub(r"\s+", " ", e.pop("body")).strip()
        pm = PREREQ_RE.search(body)
        prereqs = pm.group(1).strip() if pm else ""
        attrs = re.findall(r"\b(COLL\s?\d{3}[A-Z]?|NQR|ALV|CSI|GE\s?\d+[A-Z]?)\b", body)
        out.append({**e, "description": body[:2000], "prereqs": prereqs[:500],
                    "prereq_codes": [c for c in find_codes(prereqs) if c != e["code"]], "attributes": sorted(set(attrs))})
    return out


def upsert_courses(rows: Iterable[Dict[str, Any]], source: str, school: str = "wm") -> int:
    c, n = db.conn(), 0
    for r in rows:
        code = r.get("code")
        m = CODE_RE.search(str(code or ""))
        if not m or not r.get("title"):
            continue
        code = norm_code(*m.groups())
        prereqs = str(r.get("prereqs") or "")[:500]
        pcodes = r.get("prereq_codes") or [x for x in find_codes(prereqs) if x != code]
        c.execute("""INSERT INTO catalog_courses (school, code, title, credits, description, prereqs, prereq_codes, attributes, source, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (school, code) DO UPDATE SET title = excluded.title, credits = excluded.credits,
                       description = CASE WHEN excluded.description != '' THEN excluded.description ELSE description END,
                       prereqs = excluded.prereqs, prereq_codes = excluded.prereq_codes, attributes = excluded.attributes,
                       source = excluded.source, updated_at = excluded.updated_at""",
                  (school, code, str(r["title"])[:200], str(r.get("credits") or "")[:20], str(r.get("description") or "")[:2000],
                   prereqs, json.dumps(pcodes), json.dumps(list(r.get("attributes") or [])), source[:200], time.time()))
        n += 1
    c.commit()
    return n


def _row(r) -> Dict[str, Any]:
    d = dict(r)
    d["prereq_codes"] = json.loads(d.get("prereq_codes") or "[]")
    d["attributes"] = json.loads(d.get("attributes") or "[]")
    return d


def get_course(code: str, school: str = "wm") -> Optional[Dict[str, Any]]:
    m = CODE_RE.search(code.upper())
    if not m:
        return None
    r = db.conn().execute("SELECT * FROM catalog_courses WHERE school = ? AND code = ?", (school, norm_code(*m.groups()))).fetchone()
    return _row(r) if r else None


def search(query: str = "", dept: str = "", limit: int = 40, school: str = "wm") -> List[Dict[str, Any]]:
    sql, args = "SELECT * FROM catalog_courses WHERE school = ?", [school]
    if dept:
        sql += " AND code LIKE ?"; args.append(dept.upper() + " %")
    for word in (query or "").split()[:6]:
        sql += " AND (code LIKE ? OR title LIKE ? OR description LIKE ?)"; args += [f"%{word}%"] * 3
    sql += " ORDER BY code LIMIT ?"; args.append(min(max(limit, 1), 200))
    return [_row(r) for r in db.conn().execute(sql, args)]


def stats(school: str = "wm") -> Dict[str, Any]:
    c = db.conn()
    n = c.execute("SELECT COUNT(*) FROM catalog_courses WHERE school = ?", (school,)).fetchone()[0]
    depts = [r[0] for r in c.execute("SELECT DISTINCT substr(code, 1, instr(code, ' ') - 1) FROM catalog_courses WHERE school = ? ORDER BY 1", (school,))]
    return {"courses": n, "departments": depts}


# ---------------------------------------------------------------- the student's record
def completed(user_id: str) -> List[Dict[str, Any]]:
    return [dict(r) for r in db.conn().execute("SELECT * FROM completed_courses WHERE user_id = ? ORDER BY code", (user_id,))]


def add_completed(user_id: str, rows: Iterable[Dict[str, Any]], source: str) -> int:
    c, n = db.conn(), 0
    for r in rows:
        m = CODE_RE.search(str(r.get("code") or "").upper())
        if not m:
            continue
        c.execute("""INSERT INTO completed_courses (user_id, code, title, grade, term, source) VALUES (?, ?, ?, ?, ?, ?)
                     ON CONFLICT (user_id, code) DO UPDATE SET title = COALESCE(NULLIF(excluded.title, ''), title),
                       grade = COALESCE(NULLIF(excluded.grade, ''), grade), term = COALESCE(NULLIF(excluded.term, ''), term)""",
                  (user_id, norm_code(*m.groups()), str(r.get("title") or "")[:200], str(r.get("grade") or "")[:4],
                   str(r.get("term") or "")[:30], source[:60]))
        n += 1
    c.commit()
    return n


def remove_completed(user_id: str, code: str):
    db.conn().execute("DELETE FROM completed_courses WHERE user_id = ? AND code = ?", (user_id, code.upper()))
    db.conn().commit()


def transcript_rows(text: str) -> List[Dict[str, Any]]:
    """Course codes from a transcript, degree audit or a typed list; grade/title when they sit on the same line."""
    rows = []
    for line in (text or "").splitlines():
        for d, n in CODE_RE.findall(line):
            if d.upper() in NOT_COURSES:
                continue
            code = norm_code(d, n)
            rest = line.split(n, 1)[-1]
            g = GRADE_RE.findall(rest)
            title = re.sub(r"\s{2,}.*$", "", re.sub(r"^[\s.:-]+", "", rest)).strip()
            rows.append({"code": code, "grade": g[-1] if g else "", "title": title[:120] if re.search(r"[a-z]", title) else ""})
    seen, out = set(), []
    for r in rows:
        if r["code"] not in seen:
            seen.add(r["code"])
            out.append(r)
    return out


# ---------------------------------------------------------------- advice
PASSING = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "P", "S", "CR", "TR", ""}


def readiness(user_id: str, code: str) -> Dict[str, Any]:
    course = get_course(code)
    if not course:
        return {"code": code, "found": False}
    done = {r["code"]: r for r in completed(user_id)}
    have = {c for c, r in done.items() if r["grade"].upper() in PASSING}
    missing = [c for c in course["prereq_codes"] if c not in have]
    # "A or B" prerequisites: one of a group is enough when the catalog wording says "or"
    either = " or " in course["prereqs"].lower() and any(c in have for c in course["prereq_codes"])
    return {"code": course["code"], "found": True, "title": course["title"], "prereqs": course["prereqs"],
            "prereq_codes": course["prereq_codes"], "missing": [] if either else missing,
            "met": either or not missing, "taken": course["code"] in done}


def recommend(user_id: str, interests: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    """Courses the student hasn't taken whose listed prerequisites they have, ranked by how much they build on
    what they did (shared department, prerequisites satisfied) and by interest words."""
    done = {r["code"] for r in completed(user_id)}
    depts = {c.split()[0] for c in done}
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", interests or "")]
    out = []
    for r in db.conn().execute("SELECT * FROM catalog_courses WHERE school = 'wm'"):
        c = _row(r)
        if c["code"] in done:
            continue
        rd = readiness(user_id, c["code"])
        if not rd["met"]:
            continue
        blob = f"{c['title']} {c['description']}".lower()
        score = (3 if c["code"].split()[0] in depts else 0) + 2 * len([p for p in c["prereq_codes"] if p in done])
        score += sum(2 for w in words if w in blob)
        num = int(re.sub(r"\D", "", c["code"].split()[1]) or 0)
        score -= 0 if not done else abs(num // 100 - (max(int(re.sub(r"\D", "", d.split()[1]) or 0) for d in done) // 100 + 1)) * 0.5
        out.append({**c, "score": round(score, 1), "builds_on": [p for p in c["prereq_codes"] if p in done]})
    out.sort(key=lambda c: (-c["score"], c["code"]))
    return out[:limit]
