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
import hashlib
import html
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
    syllabus    TEXT NOT NULL DEFAULT '',   -- full syllabus markdown or extracted topics
    prereq_tree TEXT NOT NULL DEFAULT '[]', -- Conjunctive Normal Form (AND of OR-choice groups)
    source      TEXT NOT NULL DEFAULT '',
    inferred_attributes TEXT NOT NULL DEFAULT '[]',
    inferred_hash TEXT NOT NULL DEFAULT '',
    updated_at  REAL NOT NULL,
    PRIMARY KEY (school, code)
);
CREATE TABLE IF NOT EXISTS catalog_sections (
    school        TEXT NOT NULL DEFAULT 'wm',
    term          TEXT NOT NULL,              -- e.g. "202620"
    term_name     TEXT NOT NULL DEFAULT '',   -- e.g. "Spring 2026"
    crn           TEXT NOT NULL,              -- e.g. "23803"
    code          TEXT NOT NULL,              -- e.g. "CSCI 141"
    section       TEXT NOT NULL DEFAULT '01',
    title         TEXT NOT NULL,
    instructor    TEXT NOT NULL DEFAULT '',
    meets         TEXT NOT NULL DEFAULT '',   -- e.g. "MWF 10-10:50a"
    meeting_times TEXT NOT NULL DEFAULT '[]', -- JSON string of day/time objects
    schedule_type TEXT NOT NULL DEFAULT '',   -- "LC", "LB", "SE", etc.
    status        TEXT NOT NULL DEFAULT '',   -- "A" (Active), etc.
    seats         TEXT NOT NULL DEFAULT '',
    credits       TEXT NOT NULL DEFAULT '',
    updated_at    REAL NOT NULL,
    PRIMARY KEY (school, term, crn)
);
CREATE INDEX IF NOT EXISTS idx_sections_code ON catalog_sections(school, code);
CREATE INDEX IF NOT EXISTS idx_sections_term ON catalog_sections(school, term);
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

CODE_RE = re.compile(r"\b([A-Z]{2,5})\s?-?\s?([A-Z]?\d{3}[A-Z]{0,2})\b")
ENTRY_RE = re.compile(r"^\s*([A-Z]{2,5})\s?([A-Z]?\d{3}[A-Z]{0,2})\s*[.:-]\s*(.+?)\.\s*(?:\(([^)]*credits?[^)]*)\)|(\d(?:-\d)?\s*credits?))?", re.I)
PREREQ_RE = re.compile(r"(?:Prerequisites?(?:\(s\))?|Pre-?req(?:uisite)?s?)\s*[:\-]?\s*(.+?)(?:(?<=[a-z0-9)])\.\s|$)", re.I)
GRADE_RE = re.compile(r"(?<![A-Za-z])([A-D][+-]|[A-DFPS]|CR|TR|IP)(?![A-Za-z+-])")
NOT_COURSES = {"GPA", "SAT", "ACT", "ID", "USA", "PDF", "AM", "PM"}


def init():
    c = db.conn()
    c.executescript(SCHEMA)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(catalog_courses)")}
    if cols and "syllabus" not in cols:
        c.execute("ALTER TABLE catalog_courses ADD COLUMN syllabus TEXT NOT NULL DEFAULT ''")
    if cols and "prereq_tree" not in cols:
        c.execute("ALTER TABLE catalog_courses ADD COLUMN prereq_tree TEXT NOT NULL DEFAULT '[]'")
    if cols and "inferred_attributes" not in cols:
        c.execute("ALTER TABLE catalog_courses ADD COLUMN inferred_attributes TEXT NOT NULL DEFAULT '[]'")
    if cols and "inferred_hash" not in cols:
        c.execute("ALTER TABLE catalog_courses ADD COLUMN inferred_hash TEXT NOT NULL DEFAULT ''")
    c.commit()


def norm_code(dept: str, num: str) -> str:
    return f"{dept.upper()} {num.upper()}"


def expand_shorthand(text: str) -> str:
    """Expands course shorthand like 'MATH 111 or 131' to 'MATH 111 or MATH 131'."""
    pattern = re.compile(r"\b([A-Z]{2,5})\s+([A-Z]?\d{3}[A-Z]{0,2})([\s,/]+(?:or|and|/)?\s+)([A-Z]?\d{3}[A-Z]{0,2})\b", re.I)
    s = str(text or "")
    for _ in range(40):  # one more code per pass; long lists like "HISP 340, 350, ... or 391" need many
        prev = s
        s = pattern.sub(r"\1 \2\3\1 \4", s)
        if prev == s:
            break
    return s


def find_codes(text: str) -> List[str]:
    out, seen = [], set()
    expanded = expand_shorthand(text or "")
    for d, n in CODE_RE.findall(expanded):
        if d.upper() in NOT_COURSES:
            continue
        c = norm_code(d, n)
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


_NOT_PREREQ_LINE = re.compile(r"^\s*(?:\*\s*May be taken|A minimum grade|Corequisites?|Co-?req|Or consent|Enrollment|Registration|Instructor Approval|Department Approval|Dean Approval)", re.I)
# course codes are upper case ("the 300 level" is not a course); the words are matched in any case
_TOKEN_RE = re.compile(r"\(|\)|,|;|\b(?i:and|or)\b|\bALT\b|\b[A-Z]{2,5}\s?-?\s?[A-Z]?\d{3}[A-Z]{0,2}\b")
# older catalog text ran the course description on after the prerequisites: "ITAL 103 This course covers ..."
_PROSE_RE = re.compile(r"\s(?:This|These|A|An|The|Students|Topics|Emphasis|Introduction|Why|Examines?|Explores?|Designed|Intended|Research)\s[a-z]")


def prereq_statement(text: str) -> str:
    """The required-courses part of a prerequisite field: no HTML, no quoted test names, no grade, corequisite
    or consent lines, and no "may be taken concurrently" markers."""
    raw = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    lines = [ln for ln in raw.splitlines() if ln.strip() and not _NOT_PREREQ_LINE.match(ln)]
    t = " ".join(lines)
    m = _PROSE_RE.search(t)
    if m:
        t = t[:m.start()]
    t = re.sub(r"^\s*(?:Prerequisites?(?:\(s\))?|Pre-?req(?:uisite)?s?)\s*[:\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"\(?\s*\bA minimum grade of[^.;)]*[.;)]?", " ", t, flags=re.I)
    # a placement score or test is an alternative that isn't a course: keep its place in the expression
    t = re.sub(r"minimum score of \S+ in (?:'[^']*'|\"[^\"]*\")", " ALT ", t, flags=re.I)
    t = re.sub(r"'[^']*'|\"[^\"]*\"", " ALT ", t)
    t = t.replace("*", " ")
    # examples are alternatives: "(generally FREN 305, 314, 315, and higher)"
    t = re.sub(r"\b(?:generally|e\.g\.|such as|including|for example)\b[^)]*",
               lambda m: re.sub(r"\band\b|,", " or ", re.sub(r"\b(?:and|or) higher\b", "", m.group(0))), t, flags=re.I)
    return expand_shorthand(t)


def prereq_codes_of(text: str, self_code: str = "") -> List[str]:
    """Course codes a prerequisite field requires (in any alternative), without corequisites, test names or the course itself."""
    return [c for c in find_codes(prereq_statement(text)) if c != self_code]


def _parse_expr(tokens: List[str], i: int = 0):
    """Recursive descent over prerequisite tokens. Returns (node, next index). A node is ("code", c), ("alt",),
    ("and", [nodes]) or ("or", [nodes]). In a list like "A, B or C" the commas take the list's own conjunction;
    "and" binds looser than "or" when both appear at one level, and a bare comma list means all of them."""
    items, ops = [], []
    while i < len(tokens):
        tok = tokens[i]
        low = tok.lower()
        if tok == "(":
            lead = tokens[i + 1].lower() if i + 1 < len(tokens) else ""
            node, i = _parse_expr(tokens, i + 1)
            if items and len(ops) < len(items):
                ops.append(lead if lead in ("and", "or") else ",")  # "ITAL 103 (or ITAL 102)"; else a plain list
            items.append(node)
            continue
        if tok == ")":
            i += 1
            break
        if low in ("and", "or", ",", ";"):
            if items and len(ops) < len(items):
                ops.append(low)
            elif items and low in ("and", "or") and ops and ops[-1] in (",", ";") and len(ops) == len(items):
                ops[-1] = low  # "A, or B" / "A, and B"
            i += 1
            continue
        if items and len(ops) < len(items):
            ops.append(",")
        items.append(("alt",) if low == "alt" else ("code", norm_code(*re.match(r"([A-Za-z]{2,5})\s?-?\s?(\S+)", tok).groups())))
        i += 1
    ops = ops[:max(len(items) - 1, 0)]
    if not items:
        return ("and", []), i
    if len(items) == 1:
        return items[0], i
    # split at "and"/";" (looser), then each run joined by "or" or commas
    has_or = "or" in ops
    groups, cur, cur_ops = [], [items[0]], []
    for op, item in zip(ops, items[1:]):
        if op in ("and", ";") or (op == "," and not has_or):
            groups.append((cur, cur_ops))
            cur, cur_ops = [item], []
        else:
            cur.append(item)
            cur_ops.append(op)
    groups.append((cur, cur_ops))
    parts = [g[0] if len(g) == 1 else ("or", g) for g, _ in groups]
    return (parts[0] if len(parts) == 1 else ("and", parts)), i


def _cnf(node) -> Optional[List[List[str]]]:
    """CNF of a node; None means "always satisfiable" (an alternative that isn't a course)."""
    kind = node[0]
    if kind == "code":
        return [[node[1]]]
    if kind == "alt":
        return None
    subs = [_cnf(n) for n in node[1]]
    if kind == "and":
        out = [g for s in subs if s for g in s]
        return out
    # or: any non-course alternative satisfies it from the app's point of view only if it's the only one;
    # we keep the course alternatives, which is what a transcript can show
    course_subs = [s for s in subs if s]
    if not course_subs:
        return None
    out = [[]]
    for s in course_subs:
        out = [a + b for a in out for b in s]  # distribute (a OR (b AND c)) = (a OR b) AND (a OR c)
        if len(out) > 64:  # too many clauses to be useful: any one of these courses (looser, never wrongly stricter)
            return [sorted({c for sub in course_subs for g in sub for c in g})]
    return out


def parse_prereq_cnf(text: str = "", codes: Optional[List[str]] = None, self_code: str = "") -> List[List[str]]:
    """Parses prerequisite text into Conjunctive Normal Form (AND of OR-choice groups), respecting parentheses.
    Example: 'CSCI 141 and (MATH 111 or MATH 131)' -> [['CSCI 141'], ['MATH 111', 'MATH 131']].
    Without text, each code in `codes` is required. Corequisites, test scores and the course itself are left out."""
    statement = prereq_statement(text)
    if not statement.strip():
        return [[c] for c in (codes or []) if c != self_code]
    tokens = _TOKEN_RE.findall(statement)
    tokens = [t for t in tokens if not re.fullmatch(r"[A-Za-z]{2,5}\s?-?\s?\S+", t) or t.split()[0].upper().rstrip("-") not in NOT_COURSES]
    node, _ = _parse_expr(tokens)
    cnf = _cnf(node) or []
    out: List[List[str]] = []
    seen: Set[tuple] = set()
    for g in cnf:
        group = sorted({c for c in g if c != self_code})
        if group and tuple(group) not in seen:
            seen.add(tuple(group))
            out.append(group)
    # a group that is a superset of another required group adds nothing
    return [g for g in out if not any(set(h) < set(g) for h in out)]


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
        prereqs = re.split(r"\s*(?:College Curriculum|Domain|Proficiency|Corequisite|Cross-listed)\s*:", prereqs, flags=re.I)[0].strip()
        attrs = re.findall(r"\b(COLL\s?\d{3}[A-Z]?|NQR|ALV|CSI|GE\s?\d+[A-Z]?)\b", body)
        pcodes = prereq_codes_of(prereqs, e["code"])
        ptree = parse_prereq_cnf(prereqs, pcodes, self_code=e["code"])
        out.append({**e, "description": body[:2000], "prereqs": prereqs[:500],
                    "prereq_codes": pcodes, "prereq_tree": ptree, "attributes": sorted(set(attrs))})
    return out


def upsert_courses(rows: Iterable[Dict[str, Any]], source: str = "", school: str = "wm") -> int:
    c, n = db.conn(), 0
    for r in rows:
        code = r.get("code")
        m = CODE_RE.search(str(code or ""))
        if not m or not r.get("title"):
            continue
        code = norm_code(*m.groups())
        prereqs = str(r.get("prereqs") or "")[:500]
        # the codes and tree always follow the text when there is one (given lists could hold corequisites)
        pcodes = prereq_codes_of(prereqs, code) if prereqs.strip() else [x for x in (r.get("prereq_codes") or []) if x != code]
        syllabus = str(r.get("syllabus") or "")
        prereq_tree = parse_prereq_cnf(prereqs, pcodes, self_code=code) if prereqs.strip() else (r.get("prereq_tree") or [[x] for x in pcodes])
        inferred_attrs = json.dumps(list(r.get("inferred_attributes") or []))
        inferred_hash = str(r.get("inferred_hash") or "")
        c.execute("""INSERT INTO catalog_courses (school, code, title, credits, description, prereqs, prereq_codes, attributes, syllabus, prereq_tree, source, updated_at, inferred_attributes, inferred_hash)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (school, code) DO UPDATE SET
                       title = CASE WHEN lower(excluded.title) IN ('varies by section', 'tbd', 'tba') THEN title ELSE excluded.title END,
                       credits = CASE WHEN excluded.credits != '' THEN excluded.credits ELSE credits END,
                       description = CASE WHEN excluded.description != '' THEN excluded.description ELSE description END,
                       prereqs = CASE WHEN excluded.prereqs != '' THEN excluded.prereqs ELSE prereqs END,
                       prereq_codes = CASE WHEN excluded.prereqs != '' OR excluded.prereq_codes != '[]' THEN excluded.prereq_codes ELSE prereq_codes END,
                       attributes = CASE WHEN excluded.attributes != '[]' THEN excluded.attributes ELSE attributes END,
                       syllabus = CASE WHEN excluded.syllabus != '' THEN excluded.syllabus ELSE syllabus END,
                       prereq_tree = CASE WHEN excluded.prereqs != '' OR excluded.prereq_tree != '[]' THEN excluded.prereq_tree ELSE prereq_tree END,
                       source = CASE WHEN excluded.source GLOB '*[0-9][0-9][0-9][0-9]*' THEN excluded.source ELSE source END,
                       updated_at = excluded.updated_at,
                       inferred_attributes = CASE WHEN catalog_courses.inferred_attributes != '[]' THEN catalog_courses.inferred_attributes ELSE excluded.inferred_attributes END,
                       inferred_hash = CASE WHEN catalog_courses.inferred_hash != '' THEN catalog_courses.inferred_hash ELSE excluded.inferred_hash END""",
                  (school, code, str(r["title"])[:200], str(r.get("credits") or "")[:20], str(r.get("description") or "")[:2000],
                   prereqs, json.dumps(pcodes), json.dumps(list(r.get("attributes") or [])), syllabus, json.dumps(prereq_tree), str(r.get("source") or source)[:200], time.time(),
                   inferred_attrs, inferred_hash))
        n += 1
    c.commit()
    return n


def upsert_sections(rows: Iterable[Dict[str, Any]], school: str = "wm") -> int:
    """Inserts or updates university class sections (CRN, meeting times, instructors, term)."""
    c, n = db.conn(), 0
    now = time.time()
    for r in rows:
        crn = str(r.get("crn") or "").strip()
        term = str(r.get("term") or "").strip()
        code = str(r.get("code") or "").strip()
        if not crn or not term or not code:
            continue
        m = CODE_RE.search(code.upper())
        if m:
            code = norm_code(*m.groups())
        mtimes = r.get("meeting_times")
        mtimes_str = json.dumps(mtimes) if isinstance(mtimes, list) else str(mtimes or "[]")
        c.execute("""INSERT INTO catalog_sections (school, term, term_name, crn, code, section, title, instructor, meets, meeting_times, schedule_type, status, seats, credits, updated_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT (school, term, crn) DO UPDATE SET
                       term_name = CASE WHEN excluded.term_name != '' THEN excluded.term_name ELSE term_name END,
                       code = excluded.code,
                       section = excluded.section,
                       title = excluded.title,
                       instructor = excluded.instructor,
                       meets = excluded.meets,
                       meeting_times = excluded.meeting_times,
                       schedule_type = excluded.schedule_type,
                       status = excluded.status,
                       seats = CASE WHEN excluded.seats != '' THEN excluded.seats ELSE seats END,
                       credits = excluded.credits,
                       updated_at = excluded.updated_at""",
                  (school, term, str(r.get("term_name") or "")[:40], crn[:20], code,
                   str(r.get("section") or "01")[:20], str(r.get("title") or "")[:200],
                   str(r.get("instructor") or "")[:200], str(r.get("meets") or "")[:100],
                   mtimes_str, str(r.get("schedule_type") or "")[:20],
                   str(r.get("status") or "")[:20], str(r.get("seats") or "")[:50],
                   str(r.get("credits") or "")[:20], now))
        n += 1
    c.commit()
    return n


def list_sections(code: str = "", dept: str = "", term: str = "", q: str = "", school: str = "wm", limit: int = 50) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM catalog_sections WHERE school = ?"
    args = [school]
    if code:
        m = CODE_RE.search(code.upper())
        if m:
            sql += " AND code = ?"
            args.append(norm_code(*m.groups()))
        else:
            sql += " AND code LIKE ?"
            args.append(f"%{code.strip()}%")
    if dept:
        sql += " AND code LIKE ?"
        args.append(f"{dept.strip().upper()} %")
    if term:
        sql += " AND term = ?"
        args.append(str(term).strip())
    if q and q.strip():
        q_clean = q.strip().lower()
        needle = f"%{q_clean}%"
        compact = f"%{re.sub(r'\s+', '', q_clean)}%"
        sql += (" AND (LOWER(code) LIKE ? OR REPLACE(LOWER(code), ' ', '') LIKE ?"
                " OR LOWER(term_name) LIKE ? OR REPLACE(LOWER(term_name), ' ', '') LIKE ?"
                " OR LOWER(term) LIKE ? OR LOWER(instructor) LIKE ? OR REPLACE(LOWER(instructor), ' ', '') LIKE ?"
                " OR LOWER(title) LIKE ?)")
        args.extend([needle, compact, needle, compact, needle, needle, compact, needle])
    sql += " ORDER BY term DESC, code ASC, section ASC LIMIT ?"
    try:
        lim = int(limit or 50)
    except (ValueError, TypeError):
        lim = 50
    args.append(min(max(lim, 1), 200))
    out = []
    for r in db.conn().execute(sql, args):
        d = dict(r)
        try:
            d["meeting_times"] = json.loads(d.get("meeting_times") or "[]")
        except Exception:
            d["meeting_times"] = []
        out.append(d)
    return out


def _row(r) -> Dict[str, Any]:
    d = dict(r)
    d["prereq_codes"] = json.loads(d.get("prereq_codes") or "[]")
    d["attributes"] = json.loads(d.get("attributes") or "[]")
    try:
        raw_inferred = json.loads(d.get("inferred_attributes") or "[]")
    except Exception:
        raw_inferred = []
    d["inferred_attributes"] = raw_inferred
    d["inferred_hash"] = str(d.get("inferred_hash") or "")
    try:
        raw_tree = json.loads(d.get("prereq_tree") or "[]")
    except Exception:
        raw_tree = []
    d["prereq_tree"] = raw_tree if raw_tree else parse_prereq_cnf(d.get("prereqs") or "", d["prereq_codes"])
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


YEAR_RE = re.compile(r"\b((?:19|20)\d\d)\s*[-–/]\s*((?:19|20)?\d\d)\b")


def catalog_year(text: str) -> str:
    """'2016-2017' from a catalog's opening pages, or '' when it doesn't say."""
    m = YEAR_RE.search((text or "")[:5000])
    if not m:
        return ""
    end = m.group(2) if len(m.group(2)) == 4 else m.group(1)[:2] + m.group(2)
    return f"{m.group(1)}-{end}" if int(end) == int(m.group(1)) + 1 else ""


def stats(school: str = "wm") -> Dict[str, Any]:
    c = db.conn()
    n = c.execute("SELECT COUNT(*) FROM catalog_courses WHERE school = ?", (school,)).fetchone()[0]
    depts = [r[0] for r in c.execute("SELECT DISTINCT substr(code, 1, instr(code, ' ') - 1) FROM catalog_courses WHERE school = ? ORDER BY 1", (school,))]
    sources = [{"source": r[0], "courses": r[1]} for r in c.execute(
        "SELECT source, COUNT(*) FROM catalog_courses WHERE school = ? GROUP BY source ORDER BY 2 DESC", (school,))]
    years = sorted({m.group(0) for s in sources for m in [re.search(r"(?:19|20)\d\d(?:-(?:19|20)\d\d)?", s["source"])] if m})
    n_sections = c.execute("SELECT COUNT(*) FROM catalog_sections WHERE school = ?", (school,)).fetchone()[0]
    terms = [{"term": r[0], "term_name": r[1], "count": r[2], "sections": r[2]} for r in c.execute(
        "SELECT term, MAX(term_name), COUNT(*) FROM catalog_sections WHERE school = ? GROUP BY term ORDER BY term DESC", (school,))]
    term_years = [int(t["term"][:4]) for t in terms if len(t.get("term", "")) >= 4 and t["term"][:4].isdigit()]
    current_year = int(time.strftime("%Y")) + (1 if int(time.strftime("%m")) >= 8 else 0)
    has_fresh_data = any(y >= current_year for y in term_years) or any(int(y[-4:]) >= current_year for y in years)
    return {"courses": n, "departments": depts, "sources": sources, "years": years,
            "sections": n_sections, "total_sections": n_sections, "terms": terms,
            # anything older than the current academic year (or of unknown year) is shown as possibly outdated
            "outdated": bool(n) and not has_fresh_data}


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
    have = {c for c, r in done.items() if (r.get("grade") or "").upper() in PASSING}

    cnf = course.get("prereq_tree") or parse_prereq_cnf(course.get("prereqs") or "", course.get("prereq_codes") or [])
    missing = []
    missing_codes = []
    for group in cnf:
        if not any(c in have for c in group):
            missing.append(" or ".join(group) if len(group) > 1 else group[0])
            missing_codes.extend([c for c in group if c not in have])

    met = len(missing) == 0
    level = 100
    parts = course["code"].split()
    if len(parts) > 1:
        num_m = re.search(r"(\d+)", parts[1])
        if num_m:
            level = int(num_m.group(1))

    prereqs_raw = (course.get("prereqs") or "").strip().lower()
    is_explicit_none = prereqs_raw in {"none", "none.", "n/a", "no prerequisites"}

    if not cnf:
        if level >= 300 and not is_explicit_none:
            status = "unknown"
            met = False
            notes = "Prerequisites not listed in current catalog data"
        else:
            status = "none"
            met = True
            notes = ""
    else:
        met = len(missing) == 0
        status = "met" if met else "missing"
        notes = ""

    return {"code": course["code"], "found": True, "title": course["title"], "prereqs": course["prereqs"],
            "prereq_codes": course["prereq_codes"], "prereq_tree": cnf,
            "missing": missing, "missing_codes": sorted(set(missing_codes)),
            "met": met, "status": status, "notes": notes, "taken": course["code"] in done}


def compute_course_content_hash(course: Dict[str, Any]) -> str:
    blob = f"{course.get('code', '')}|{course.get('title', '')}|{course.get('description', '')}|{course.get('prereqs', '')}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def effective_attributes(course: Dict[str, Any]) -> Dict[str, List[str]]:
    coll_num = coll_by_number(course.get("code", ""))
    raw_ai = course.get("inferred_attributes") or []
    ai_tags = [a["attr"] if isinstance(a, dict) and "attr" in a else str(a) for a in raw_ai]
    return {
        "official": list(course.get("attributes") or []),
        "by_number": [coll_num] if coll_num else [],
        "ai": ai_tags,
    }


def save_inferred_attributes(updates: List[Dict[str, Any]], school: str = "wm") -> int:
    c = db.conn()
    n = 0
    for u in updates:
        code = str(u.get("code") or "").strip()
        m = CODE_RE.search(code.upper())
        if m:
            code = norm_code(*m.groups())
        inferred_attrs = json.dumps(list(u.get("inferred_attributes") or []))
        inferred_hash = str(u.get("inferred_hash") or "")
        cur = c.execute(
            "UPDATE catalog_courses SET inferred_attributes = ?, inferred_hash = ? WHERE school = ? AND code = ?",
            (inferred_attrs, inferred_hash, school, code),
        )
        n += cur.rowcount
    c.commit()
    return n


def coll_by_number(code: str) -> Optional[str]:
    """A department course numbered 100 or 150 (letter prefix/suffix allowed, e.g. HIST 150W, HIST S150) counts as COLL 100 / COLL 150.
    Derived from the number only: callers keep it apart from the catalog's official attributes."""
    m = re.match(r"^([A-Z]{2,5})\s+([A-Z]?)(\d{3})([A-Z]{0,2})$", (code or "").strip().upper())
    if not m or m.group(1) == "COLL" or m.group(3) not in ("100", "150"):
        return None
    return f"COLL {m.group(3)}"


def degree_audit(user_id: str, school: str = "wm") -> Dict[str, Any]:
    """Evaluates William & Mary College Curriculum (COLL 100/150/200/300/400) and Proficiencies."""
    done_records = completed(user_id)
    passed = [r for r in done_records if (r.get("grade") or "").upper() in PASSING]

    coll = {
        "coll100": {"name": "COLL 100", "title": "Big Ideas", "required": 4, "earned": 0, "likely": 0, "met": False, "courses": [], "likely_courses": []},
        "coll150": {"name": "COLL 150", "title": "First-Year Seminar", "required": 4, "earned": 0, "likely": 0, "met": False, "courses": [], "likely_courses": []},
        "coll200": {"name": "COLL 200", "title": "Exploring Foundations", "required": 12, "earned": 0, "likely": 0, "alv": 0, "csi": 0, "nqr": 0, "met": False, "courses": [], "likely_courses": []},
        "coll300": {"name": "COLL 300", "title": "In the World / Global", "required": 3, "earned": 0, "likely": 0, "met": False, "courses": [], "likely_courses": []},
        "coll400": {"name": "COLL 400", "title": "Capstone in Major", "required": 3, "earned": 0, "likely": 0, "met": False, "courses": [], "likely_courses": []},
    }
    prof = {
        "math": {"name": "Mathematics", "met": False, "courses": []},
        "arts": {"name": "Creative & Performing Arts", "met": False, "courses": []},
    }
    total_credits = 0.0

    for r in passed:
        code = r["code"]
        c = get_course(code, school=school)
        eff = effective_attributes(c or {"code": code})
        official_attrs = set(eff["official"] + eff["by_number"])
        ai_attrs = set(eff["ai"])

        raw_cr = (c.get("credits") if c else None) or r.get("credits") or "3"
        try:
            m_cr = re.search(r"(\d+(?:\.\d+)?)", str(raw_cr))
            cr = float(m_cr.group(1)) if m_cr else 3.0
        except Exception:
            cr = 3.0
        total_credits += cr

        parts = code.split()
        dept = parts[0] if parts else ""
        num_str = parts[1] if len(parts) > 1 else ""
        num = int(re.sub(r"\D", "", num_str) or 0)
        title_lower = ((c.get("title") if c else "") or r.get("title") or "").lower()

        # COLL 100
        is_coll100 = "COLL 100" in official_attrs or "COLL100" in official_attrs or code.startswith("COLL 100") or "coll 100" in title_lower
        if is_coll100:
            coll["coll100"]["earned"] += cr
            coll["coll100"]["courses"].append(code)
        elif "COLL 100" in ai_attrs or "COLL100" in ai_attrs:
            if code not in coll["coll100"]["likely_courses"]:
                coll["coll100"]["likely"] += cr
                coll["coll100"]["likely_courses"].append(code)

        # COLL 150
        is_coll150 = "COLL 150" in official_attrs or "COLL150" in official_attrs or code.startswith("COLL 150") or "coll 150" in title_lower
        if is_coll150:
            coll["coll150"]["earned"] += cr
            coll["coll150"]["courses"].append(code)
        elif "COLL 150" in ai_attrs or "COLL150" in ai_attrs:
            if code not in coll["coll150"]["likely_courses"]:
                coll["coll150"]["likely"] += cr
                coll["coll150"]["likely_courses"].append(code)

        # COLL 200
        has_coll200 = "COLL 200" in official_attrs or "COLL200" in official_attrs or "coll 200" in title_lower or (200 <= num < 300 and any(a in official_attrs for a in ["ALV", "CSI", "NQR"]))
        if has_coll200:
            coll["coll200"]["earned"] += cr
            coll["coll200"]["courses"].append(code)
            if "ALV" in official_attrs:
                coll["coll200"]["alv"] += cr
            if "CSI" in official_attrs:
                coll["coll200"]["csi"] += cr
            if "NQR" in official_attrs:
                coll["coll200"]["nqr"] += cr
        elif "COLL 200" in ai_attrs or "COLL200" in ai_attrs or any(a in ai_attrs for a in ["ALV", "CSI", "NQR"]):
            if code not in coll["coll200"]["likely_courses"]:
                coll["coll200"]["likely"] += cr
                coll["coll200"]["likely_courses"].append(code)

        # COLL 300
        is_coll300 = "COLL 300" in official_attrs or "COLL300" in official_attrs or code.startswith("COLL 300") or "coll 300" in title_lower
        if is_coll300:
            coll["coll300"]["earned"] += cr
            coll["coll300"]["courses"].append(code)
        elif "COLL 300" in ai_attrs or "COLL300" in ai_attrs:
            if code not in coll["coll300"]["likely_courses"]:
                coll["coll300"]["likely"] += cr
                coll["coll300"]["likely_courses"].append(code)

        # COLL 400
        is_coll400 = "COLL 400" in official_attrs or "COLL400" in official_attrs or code.startswith("COLL 400") or num == 400 or "coll 400" in title_lower or num in (495, 496)
        if is_coll400:
            coll["coll400"]["earned"] += cr
            coll["coll400"]["courses"].append(code)
        elif "COLL 400" in ai_attrs or "COLL400" in ai_attrs:
            if code not in coll["coll400"]["likely_courses"]:
                coll["coll400"]["likely"] += cr
                coll["coll400"]["likely_courses"].append(code)

        # Mathematics Proficiency
        if dept in {"MATH", "DATA"} or code in {"CSCI 141", "BUAD 231", "ECON 307"} or "MATH" in official_attrs or "calculus" in title_lower or "statistics" in title_lower:
            prof["math"]["met"] = True
            prof["math"]["courses"].append(code)

        # Arts Proficiency
        if dept in {"ART", "ARTH", "MUSC", "THEA", "DANC"} or any(a in official_attrs for a in ["ARTS", "ACTV"]) or "creative writing" in title_lower:
            prof["arts"]["met"] = True
            prof["arts"]["courses"].append(code)

    coll["coll100"]["met"] = coll["coll100"]["earned"] >= coll["coll100"]["required"]
    coll["coll150"]["met"] = coll["coll150"]["earned"] >= coll["coll150"]["required"]
    coll["coll200"]["met"] = (coll["coll200"]["earned"] >= 12 and coll["coll200"]["alv"] >= 3 and coll["coll200"]["csi"] >= 3 and coll["coll200"]["nqr"] >= 3 and len(coll["coll200"]["courses"]) >= 3)
    coll["coll300"]["met"] = coll["coll300"]["earned"] >= coll["coll300"]["required"]
    coll["coll400"]["met"] = coll["coll400"]["earned"] >= coll["coll400"]["required"]

    all_coll_met = all(req["met"] for req in coll.values())
    all_prof_met = all(p["met"] for p in prof.values())

    return {
        "user_id": user_id,
        "total_credits": round(total_credits, 1),
        "coll": coll,
        "proficiencies": prof,
        "completed_count": len(done_records),
        "all_coll_met": all_coll_met,
        "overall_met": all_coll_met and all_prof_met,
    }


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
