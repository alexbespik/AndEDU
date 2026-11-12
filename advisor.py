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
import functools
import hashlib
import html
import json
import re
import time
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple

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
    details       TEXT NOT NULL DEFAULT '{}', -- JSON: rooms, dates, seats, restrictions (the section's prerequisites), consent
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
CREATE TABLE IF NOT EXISTS semester_plans (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL,
    term           TEXT NOT NULL,
    term_name      TEXT,
    title          TEXT,
    target_credits REAL,
    courses_json   TEXT,
    notes          TEXT,
    status         TEXT,
    created_at     REAL,
    updated_at     REAL,
    UNIQUE (user_id, term)
);
CREATE INDEX IF NOT EXISTS idx_semester_plans_user ON semester_plans(user_id);

"""

# course numbers: 3 digits with optional letters (CSCI 141, PHYS 101L), graduate 4 digits (BUAD 5002, never a year
# like 2025) and a letter plus 2 digits (MUSC J99, EDUC C99)
_NUM = r"(?:[A-Z]?\d{3}[A-Z]{0,2}|(?!19\d\d|20\d\d)\d{4}[A-Z]?|[A-Z]\d{2}[A-Z]?)"
CODE_RE = re.compile(r"\b([A-Z]{2,5})\s?-?\s?(" + _NUM + r")\b")
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
    scols = {r["name"] for r in c.execute("PRAGMA table_info(catalog_sections)")}
    if scols and "details" not in scols:  # per-section PATH details: rooms, dates, seats, restrictions, attributes
        c.execute("ALTER TABLE catalog_sections ADD COLUMN details TEXT NOT NULL DEFAULT '{}'")
    c.commit()
    import advisor_cart  # here, not at the top: advisor_cart imports this module
    advisor_cart.init()


def norm_code(dept: str, num: str) -> str:
    return f"{dept.upper()} {num.upper()}"


def expand_shorthand(text: str) -> str:
    """Expands course shorthand like 'MATH 111 or 131' to 'MATH 111 or MATH 131'."""
    pattern = re.compile(r"\b([A-Z]{2,5})\s+(" + _NUM + r")([\s,/]+(?:or|and|/)?\s+)(" + _NUM + r")\b(?!-?level)")
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
_TOKEN_RE = re.compile(r"\(|\)|,|;|\b(?i:and|or)\b|\bALT\b|\b[A-Z]{2,5}\s?-?\s?" + _NUM + r"\b")
# older catalog text ran the course description on after the prerequisites: "ITAL 103 This course covers ..."
_PROSE_RE = re.compile(r"\s(?:This|These|A|An|The|Students|Topics|Emphasis|Introduction|Why|Examines?|Explores?|Designed|Intended|Research)\s[a-z]")


_SCORE_RE = re.compile(r"minimum score of (\S+) in ('[^']*'|\"[^\"]*\")", re.I)
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_ALT_MARK_RE = re.compile(r"\x00(\d+)\x00")


def _statement_and_alts(text: str):
    """prereq_statement() plus the alternatives it replaced with " ALT ", in the order they appear:
    [{"test": quoted name, "min": score (None for a bare quoted name)}]."""
    raw = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    lines = [ln for ln in raw.splitlines() if ln.strip() and not _NOT_PREREQ_LINE.match(ln)]
    t = " ".join(lines)
    m = _PROSE_RE.search(t)
    if m:
        t = t[:m.start()]
    t = re.sub(r"^\s*(?:Prerequisites?(?:\(s\))?|Pre-?req(?:uisite)?s?)\s*[:\-]?\s*", "", t, flags=re.I)
    t = re.sub(r"\(?\s*\bA minimum grade of[^.;)]*[.;)]?", " ", t, flags=re.I)
    # a placement score or test is an alternative that isn't a course: keep its place in the expression.
    # Two passes as always (scores, then any other quoted name); each leaves a quote-free marker that becomes " ALT "
    found: List[Dict[str, Any]] = []

    def mark(test: str, score: Optional[str]) -> str:
        m_score = re.fullmatch(r"\d+", score or "")
        found.append({"test": test[1:-1].strip(), "min": int(score) if m_score else (score or None)})
        return f" \x00{len(found) - 1}\x00 "

    t = _SCORE_RE.sub(lambda m: mark(m.group(2), m.group(1)), t)
    t = _QUOTED_RE.sub(lambda m: mark(m.group(0), None), t)
    alts = [found[int(k)] for k in _ALT_MARK_RE.findall(t)]  # the order in the text, not the order of the passes
    t = _ALT_MARK_RE.sub("ALT", t)
    t = t.replace("*", " ")
    # examples are alternatives: "(generally FREN 305, 314, 315, and higher)"
    t = re.sub(r"\b(?:generally|e\.g\.|such as|including|for example)\b[^)]*",
               lambda m: re.sub(r"\band\b|,", " or ", re.sub(r"\b(?:and|or) higher\b", "", m.group(0))), t, flags=re.I)
    return expand_shorthand(t), alts


def prereq_statement(text: str) -> str:
    """The required-courses part of a prerequisite field: no HTML, no quoted test names, no grade, corequisite
    or consent lines, and no "may be taken concurrently" markers."""
    return _statement_and_alts(text)[0]


def prereq_codes_of(text: str, self_code: str = "") -> List[str]:
    """Course codes a prerequisite field requires (in any alternative), without corequisites, test names or the course itself."""
    return [c for c in find_codes(prereq_statement(text)) if c != self_code]


def _parse_expr(tokens: List[str], i: int = 0):
    """Recursive descent over prerequisite tokens. Returns (node, next index). A node is ("code", c), ("alt", k),
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
        # an alternative is numbered by its place among the ALT tokens (parse_prereq_scores maps it back)
        items.append(("alt", sum(1 for t in tokens[:i] if t.lower() == "alt")) if low == "alt"
                     else ("code", norm_code(*re.match(r"([A-Za-z]{2,5})\s?-?\s?(\S+)", tok).groups())))
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


def _prereq_tokens(statement: str) -> List[str]:
    tokens = _TOKEN_RE.findall(statement)
    return [t for t in tokens if not re.fullmatch(r"[A-Za-z]{2,5}\s?-?\s?\S+", t) or t.split()[0].upper().rstrip("-") not in NOT_COURSES]


def parse_prereq_cnf(text: str = "", codes: Optional[List[str]] = None, self_code: str = "") -> List[List[str]]:
    """Parses prerequisite text into Conjunctive Normal Form (AND of OR-choice groups), respecting parentheses.
    Example: 'CSCI 141 and (MATH 111 or MATH 131)' -> [['CSCI 141'], ['MATH 111', 'MATH 131']].
    Without text, each code in `codes` is required. Corequisites, test scores and the course itself are left out."""
    statement = prereq_statement(text)
    if not statement.strip():
        return [[c] for c in (codes or []) if c != self_code]
    node, _ = _parse_expr(_prereq_tokens(statement))
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


class ScoreOption(NamedTuple):
    test: str             # the name PATH quotes: 'AP Calculus BC', 'Intro to Biology Equivalent', 'Admitted to SOE-Secondary'
    min: Any              # the minimum score (an int), None for a quoted name without one
    kind: str             # test (AP/IB/CLEP/SAT/ACT) | admission | equivalent (PATH equivalency, exemption or placement flags)


class ScoreRules(NamedTuple):
    groups: Tuple[Tuple[Tuple[str, ...], Tuple[ScoreOption, ...]], ...]  # (CNF group, the options that also satisfy it)
    required_alts: Tuple[ScoreOption, ...]  # alternatives required on their own, outside any OR with a course
    required_any: Tuple[Tuple[ScoreOption, ...], ...] = ()  # the same, kept per OR: any one option of a group is enough


_TEST_NAME_RE = re.compile(r"^(?:AP|IB|CLEP|SAT|ACT)\b")
_ADMISSION_RE = re.compile(r"^Admitted to\b", re.I)


def _score_kind(name: str) -> str:
    return "test" if _TEST_NAME_RE.match(name) else "admission" if _ADMISSION_RE.match(name) else "equivalent"


def _lower_min(a: Any, b: Any) -> Any:
    """The lower of two minimum scores; None (no score named) is the lowest; anything else that isn't a number keeps a."""
    if a is None or b is None:
        return None
    return min(a, b) if isinstance(a, int) and isinstance(b, int) else a


def _dedupe_options(options: Iterable[ScoreOption]) -> Tuple[ScoreOption, ...]:
    """One option per (test, kind), in first-seen order, with the lowest minimum (any of them is enough)."""
    out: Dict[tuple, ScoreOption] = {}
    for o in options:
        key = (o.test, o.kind)
        out[key] = o._replace(min=_lower_min(out[key].min, o.min)) if key in out else o
    return tuple(out.values())


def _required_groups(groups: List[Tuple[ScoreOption, ...]]) -> Tuple[Tuple[ScoreOption, ...], ...]:
    """OR groups of required alternatives without repeats; a group that contains another adds nothing ("X" already
    required makes "X or Y" moot)."""
    keys = [frozenset((o.test, o.kind) for o in g) for g in groups]
    out, seen = [], set()
    for g, k in zip(groups, keys):
        if g and k not in seen and not any(h < k for h in keys):
            seen.add(k)
            out.append(g)
    return tuple(out)


_ABSENT = object()


def _common_options(lists: List[Tuple[ScoreOption, ...]]) -> Tuple[ScoreOption, ...]:
    """Options that satisfy every one of several clauses on the same courses (each must hold): the highest minimum."""
    if not lists:
        return ()
    out = []
    for o in lists[0]:
        mins = [next((x.min for x in lst if (x.test, x.kind) == (o.test, o.kind)), _ABSENT) for lst in lists[1:]]
        if any(x is _ABSENT for x in mins):  # a sentinel: a minimum of 0 must not read as "absent"
            continue
        m = o.min
        for x in mins:
            m = x if m is None else m if x is None else max(m, x) if isinstance(m, int) and isinstance(x, int) else m
        out.append(o._replace(min=m))
    return tuple(out)


def _clauses(node, state: Dict[str, bool]):
    """_cnf() with each clause's non-course alternatives kept. Returns (clauses, alt_only): clauses are (codes, alt
    numbers) pairs whose code lists are exactly the groups _cnf builds; alt_only lists clauses made of alternatives
    alone (tuples of alt numbers, any one enough). Sets state["collapsed"] when _cnf's 64-clause fallback fires."""
    kind = node[0]
    if kind == "code":
        return [([node[1]], ())], []
    if kind == "alt":
        return [], [(node[1],)]
    subs = [_clauses(n, state) for n in node[1]]
    if kind == "and":
        return [c for s, _ in subs for c in s], [a for _, alt in subs for a in alt]
    course_subs = [s for s, _ in subs if s]  # as in _cnf; their alternative-only clauses are dropped as _cnf drops them
    # an alternative on its own in this OR (an AND of several alternatives is left out: no one of them is enough)
    opts = tuple(k for s, alt in subs if not s and len(alt) == 1 for k in alt[0])
    if not course_subs:
        return [], ([opts] if opts else [])
    out = [([], opts)]
    for s in course_subs:
        out = [(a + b, a_alts + b_alts) for a, a_alts in out for b, b_alts in s]
        if len(out) > 64:
            state["collapsed"] = True
            return [(sorted({c for sub in course_subs for g, _ in sub for c in g}), ())], []
    return out, []


@functools.lru_cache(maxsize=4096)
def parse_prereq_scores(text: str, self_code: str = "") -> ScoreRules:
    """The test scores, equivalencies and admissions in a prerequisite field that parse_prereq_cnf leaves out: for
    each of its groups (same order, same codes) the options that would also satisfy it, plus the ones required on
    their own (EDUC 311: "minimum score of 1 in 'Admitted to SOE-Secondary', EDUC 301 and 310"). No groups when
    the rule collapsed to "any one of these courses" or the alternatives can't be placed. Cached, so the result is
    immutable (tuples and NamedTuples)."""
    statement, alts = _statement_and_alts(text)
    tokens = _prereq_tokens(statement)
    if not alts or sum(1 for t in tokens if t.lower() == "alt") != len(alts):  # e.g. a literal "ALT" in the text
        return ScoreRules((), ())
    node, _ = _parse_expr(tokens)
    state: Dict[str, bool] = {}
    clauses, alt_only = _clauses(node, state)
    options = [ScoreOption(a["test"], a["min"], _score_kind(a["test"])) for a in alts]
    required = _dedupe_options(options[k] for clause in alt_only for k in clause)
    any_of = _required_groups([_dedupe_options(options[k] for k in clause) for clause in alt_only])
    if state.get("collapsed"):
        return ScoreRules((), required, any_of)
    by_key: Dict[Tuple[str, ...], List[Tuple[ScoreOption, ...]]] = {}
    for codes, ks in clauses:  # the cleanup parse_prereq_cnf does: no self-reference, duplicates merged
        key = tuple(sorted({c for c in codes if c != self_code}))
        if key:
            by_key.setdefault(key, []).append(_dedupe_options(options[k] for k in ks))
    kept = [k for k in by_key if not any(set(h) < set(k) for h in by_key)]
    if [list(k) for k in kept] != parse_prereq_cnf(text, self_code=self_code):
        return ScoreRules((), required, any_of)
    # a dropped superset clause must hold too: an option only counts when every clause over these courses lists it
    groups = tuple((key, _common_options([o for k, lists in by_key.items() if set(key) <= set(k) for o in lists]))
                   for key in kept)
    return ScoreRules(groups, required, any_of)


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
                       title = CASE WHEN lower(excluded.title) IN ('varies by section', 'tbd', 'tba')
                                      OR (title != '' AND excluded.title LIKE title || ': %') THEN title  -- "Topics: this term's topic"
                                    ELSE excluded.title END,
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
        details = r.get("details")
        details_str = json.dumps(details) if isinstance(details, dict) else "{}"
        c.execute("""INSERT INTO catalog_sections (school, term, term_name, crn, code, section, title, instructor, meets, meeting_times, schedule_type, status, seats, credits, updated_at, details)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                       details = CASE WHEN excluded.details != '{}' THEN excluded.details ELSE details END,
                       updated_at = excluded.updated_at""",
                  (school, term, str(r.get("term_name") or "")[:40], crn[:20], code,
                   str(r.get("section") or "01")[:20], str(r.get("title") or "")[:200],
                   str(r.get("instructor") or "")[:200], str(r.get("meets") or "")[:100],
                   mtimes_str, str(r.get("schedule_type") or "")[:20],
                   str(r.get("status") or "")[:20], str(r.get("seats") or "")[:50],
                   str(r.get("credits") or "")[:20], now, details_str[:8000]))
        n += 1
    c.commit()
    return n


def list_sections(code: str = "", dept: str = "", term: str = "", q: str = "", school: str = "wm", limit: int = 50) -> List[Dict[str, Any]]:
    # PATH marks cancelled/inactive sections "I"; its own class search hides them, so do we.
    sql = "SELECT * FROM catalog_sections WHERE school = ? AND status != 'I'"
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
    return [_section_row(r) for r in db.conn().execute(sql, args)]


def _section_row(r) -> Dict[str, Any]:
    d = dict(r)
    try:
        d["details"] = json.loads(d.get("details") or "{}")
    except Exception:
        d["details"] = {}
    try:
        d["meeting_times"] = json.loads(d.get("meeting_times") or "[]")
    except Exception:
        d["meeting_times"] = []
    return d


def get_section(code: str, crn: str, term: str = "", school: str = "wm") -> Optional[Dict[str, Any]]:
    """The listed (not cancelled) section with this CRN, in this term when given (else the latest term it ran in)
    and of this course when a code is given; None when there is no such section."""
    crn = str(crn or "").strip()
    if not crn:
        return None
    sql, args = "SELECT * FROM catalog_sections WHERE school = ? AND crn = ? AND status != 'I'", [school, crn]
    if term:
        sql += " AND term = ?"
        args.append(str(term).strip())
    if code:
        m = CODE_RE.search(str(code).upper())
        sql += " AND code = ?"
        args.append(norm_code(*m.groups()) if m else str(code).strip().upper())
    r = db.conn().execute(sql + " ORDER BY term DESC LIMIT 1", args).fetchone()
    return _section_row(r) if r else None


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


def _search_where(query: str, dept: str, school: str):
    sql, args = " FROM catalog_courses WHERE school = ?", [school]
    if dept:
        sql += " AND code LIKE ?"; args.append(dept.upper() + " %")
    for word in (query or "").split()[:6]:
        sql += " AND (code LIKE ? OR title LIKE ? OR description LIKE ?)"; args += [f"%{word}%"] * 3
    return sql, args


def search(query: str = "", dept: str = "", limit: int = 40, school: str = "wm") -> List[Dict[str, Any]]:
    sql, args = _search_where(query, dept, school)
    # a whole department can exceed 300 courses (LAW): the cap must not hide its upper levels
    return [_row(r) for r in db.conn().execute("SELECT *" + sql + " ORDER BY code LIMIT ?", args + [min(max(limit, 1), 500)])]


def search_count(query: str = "", dept: str = "", school: str = "wm") -> int:
    sql, args = _search_where(query, dept, school)
    return db.conn().execute("SELECT COUNT(*)" + sql, args).fetchone()[0]


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


_SECTION_PREREQ_RE = re.compile(r"^\s*Prerequisites?\b", re.I)
_CONCURRENT_NOTE_RE = re.compile(r"\*\s*May be taken concurrently", re.I)
# a code, a bare shorthand number ("BUAD 311, 317 * , 323") or the "*" that marks the code before it
_STAR_TOKEN_RE = re.compile(r"\b([A-Z]{2,5})\s?-?\s?(" + _NUM + r")\b|\b(" + _NUM + r")\b|\*")
_GRADE_MIN_RE = re.compile(r"A minimum grade of [A-DF][+-]? is required in [^\n]+", re.I)


def section_prereq_text(section: Optional[Dict[str, Any]]) -> str:
    """The section's own prerequisite line from its PATH restrictions ('' when it lists none)."""
    details = (section or {}).get("details") or {}
    for line in details.get("restrictions") or [] if isinstance(details, dict) else []:
        if isinstance(line, str) and _SECTION_PREREQ_RE.match(line):
            return line
    return ""


def concurrent_codes(text: str, self_code: str = "") -> List[str]:
    """Codes PATH marks "* May be taken concurrently" (a "*" right after the code; shorthand numbers keep the
    department before them). Only read when the text carries that footnote."""
    raw = str(text or "")
    if not _CONCURRENT_NOTE_RE.search(raw):
        return []
    out, dept, last = [], "", ""
    for ln in raw.splitlines():
        if not ln.strip() or _NOT_PREREQ_LINE.match(ln):
            continue
        for m in _STAR_TOKEN_RE.finditer(re.sub(r"'[^']*'|\"[^\"]*\"", " ", ln)):
            if m.group(0) == "*":
                if last and last != self_code and last not in out:
                    out.append(last)
                last = ""
            elif m.group(1) and m.group(1) not in NOT_COURSES:
                dept, last = m.group(1), norm_code(m.group(1), m.group(2))
            elif m.group(3) and dept:
                last = norm_code(dept, m.group(3))
    return out


def prereq_display(text: str) -> str:
    """The prerequisite line for people: no "Prerequisites:" label, no "*" marks, no grade or footnote lines, and
    shorthand spelled out ("BUAD 231L * and 231" -> "BUAD 231L and BUAD 231")."""
    lines = [ln for ln in str(text or "").splitlines() if ln.strip() and not _NOT_PREREQ_LINE.match(ln)]
    t = re.sub(r"^\s*(?:Prerequisites?(?:\(s\))?|Pre-?req(?:uisite)?s?)\s*[:\-]?\s*", "", " ".join(lines), flags=re.I)
    t = re.sub(r"\s+", " ", re.sub(r"\s*\*\s*", " ", t))
    # spell out shorthand outside quoted test names only ("'SAT 600 or 650'" stays as written)
    parts = re.split(r"('[^']*'|\"[^\"]*\")", t)
    t = "".join(p if i % 2 else expand_shorthand(p) for i, p in enumerate(parts))
    return re.sub(r"\s+([,.;)])", r"\1", t).strip()


def grade_minimum(text: str) -> str:
    """The catalog's "A minimum grade of X is required in ..." lines (only those naming a grade), as written."""
    return " ".join(m.group(0).strip() for m in _GRADE_MIN_RE.finditer(str(text or "")))


def cnf_key(cnf: List[List[str]]):
    return frozenset(frozenset(g) for g in cnf or [])


def section_rule(course: Dict[str, Any], section: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The prerequisite rule that applies: the section's own PATH line when it parses to courses, else the course
    rule (note = the section's line when it named no course, e.g. an admission score)."""
    code = course["code"]
    course_text = course.get("prereqs") or ""
    course_cnf = course.get("prereq_tree") or parse_prereq_cnf(course_text, course.get("prereq_codes") or [], self_code=code)
    sec_text = section_prereq_text(section)
    sec_cnf = parse_prereq_cnf(sec_text, self_code=code) if sec_text else []
    if sec_cnf:
        basis, text, cnf, note = "section", sec_text, sec_cnf, ""
    else:
        basis, text, cnf = "course", course_text, course_cnf
        note = sec_text.splitlines()[0].strip() if sec_text else ""
    codes = {c for g in cnf for c in g}
    return {"basis": basis, "text": text, "cnf": cnf, "note": note,
            "concurrent_ok": [c for c in concurrent_codes(text, code) if c in codes],
            "course_text": course_text, "course_cnf": course_cnf}


def prereq_rule(code: str, crn: str = "", term: str = "") -> Optional[Dict[str, Any]]:
    """section_rule() for a course code and an optional section (CRN, term); None when the course isn't imported."""
    course = get_course(code)
    if not course:
        return None
    return section_rule(course, get_section(course["code"], crn, term) if crn else None)


def _evaluate(cnf: List[List[str]], have: Set[str], alongside: Iterable[str] = (),
              concurrent_ok: Iterable[str] = ()) -> Dict[str, Any]:
    """Which CNF groups `have` doesn't satisfy. A code marked "may be taken concurrently" that is in `alongside`
    (the same term's primary cart) satisfies its group and is reported in `concurrent`."""
    ok_now = set(alongside) & set(concurrent_ok)
    missing, missing_codes, concurrent = [], [], []
    for group in cnf:
        if any(c in have for c in group):
            continue
        now = [c for c in group if c in ok_now]
        if now:
            concurrent.extend(now)
            continue
        missing.append(" or ".join(group) if len(group) > 1 else group[0])
        missing_codes.extend(c for c in group if c not in have)
    return {"missing": missing, "missing_codes": sorted(set(missing_codes)), "concurrent": sorted(set(concurrent))}


def _score_check(rule: Dict[str, Any], course_code: str, missing_groups: List[List[str]]):
    """(score_options for the missing groups, required_alts, required_any) from the rule's text, as plain dicts.
    required_any keeps the required alternatives per OR (any one of a group is enough). Empty when the text names
    no score or its groups don't match the rule's stored tree (then the rule is judged as before)."""
    text = rule.get("text") or ""
    if "minimum score of" not in text.lower():  # cheap: recommend() judges every catalog course
        return [], [], []
    scores = parse_prereq_scores(text, course_code)
    if [list(k) for k, _ in scores.groups] != [list(g) for g in rule["cnf"]]:
        return [], [], []
    by_key = dict(scores.groups)
    options = []
    for g in missing_groups:
        opts = by_key.get(tuple(g)) or ()
        if opts:
            options.append({"group": " or ".join(g) if len(g) > 1 else g[0], "options": [o._asdict() for o in opts]})
    return (options, [o._asdict() for o in scores.required_alts],
            [[o._asdict() for o in g] for g in scores.required_any])


def score_option_text(option: Dict[str, Any]) -> str:
    """'AP Calculus BC (4+)' for a test; an equivalency or admission flag by its name only."""
    m = option.get("min")
    return f"{option.get('test')} ({m}+)" if option.get("kind") == "test" and m is not None else str(option.get("test"))


def required_alts_text(st: Dict[str, Any]) -> List[str]:
    """The required alternatives as phrases, one per OR: 'X', or 'one of X or Y' when any one of them is enough.
    Falls back to the flat required_alts (one phrase each) when no groups are given."""
    groups = st.get("required_any") or [[a] for a in st.get("required_alts") or []]
    return [score_option_text(g[0]) if len(g) == 1 else "one of " + " or ".join(map(score_option_text, g))
            for g in groups if g]


def rule_status(course: Dict[str, Any], rule: Dict[str, Any], have: Set[str], alongside: Iterable[str] = ()) -> Dict[str, Any]:
    """met | missing | check | none | unknown for a rule; unknown (no rule listed for a 300+ course) only on the
    course basis. check: what's missing could only be satisfied by a test score, equivalency or admission
    (score_options per missing group), or one is required on its own (required_alts). No scores are stored, so
    check is never met. When the text's groups don't match the stored tree the score data is ignored (missing)."""
    cnf = rule["cnf"]
    ev = _evaluate(cnf, have, alongside, rule["concurrent_ok"])
    missing_groups = [g for g in cnf if not any(c in have for c in g) and not any(c in ev["concurrent"] for c in g)]
    score_options, required_alts, required_any = _score_check(rule, course["code"], missing_groups)
    ev = {**ev, "score_options": score_options, "required_alts": required_alts, "required_any": required_any}
    if cnf or required_alts:
        if not ev["missing"] and not required_alts:
            return {**ev, "met": True, "status": "met", "notes": ""}
        check = len(score_options) == len(ev["missing"])  # every missing group has an option (or none is missing)
        return {**ev, "met": False, "status": "check" if check else "missing", "notes": ""}
    level = 100
    parts = course["code"].split()
    num_m = re.search(r"(\d+)", parts[1]) if len(parts) > 1 else None
    if num_m:
        level = int(num_m.group(1))
    is_explicit_none = (course.get("prereqs") or "").strip().lower() in {"none", "none.", "n/a", "no prerequisites"}
    if level >= 300 and not is_explicit_none:
        return {**ev, "met": False, "status": "unknown", "notes": "Prerequisites not listed in current catalog data"}
    return {**ev, "met": True, "status": "none", "notes": ""}


def readiness(user_id: str, code: str, crn: str = "", term: str = "", alongside: Iterable[str] = ()) -> Dict[str, Any]:
    """Whether the student's record meets the course's prerequisites, or a section's own rule when a CRN is given
    (basis says which applied). Without a term the CRN's latest term is used. `alongside` (the same term's primary
    cart) satisfies "may be taken concurrently" codes; those are listed in `concurrent`. status: met | missing |
    check | none | unknown (rule_status)."""
    course = get_course(code)
    if not course:
        return {"code": code, "found": False}
    done = {r["code"]: r for r in completed(user_id)}
    have = {c for c, r in done.items() if (r.get("grade") or "").upper() in PASSING}
    section = get_section(course["code"], crn, term) if crn else None
    rule = section_rule(course, section)
    st = rule_status(course, rule, have, alongside)
    out = {"code": course["code"], "found": True, "title": course["title"],
           "prereqs": rule["text"] if rule["basis"] == "section" else course["prereqs"],
           "prereq_codes": (list(dict.fromkeys(c for g in rule["cnf"] for c in g)) if rule["basis"] == "section"
                            else course["prereq_codes"]),
           "prereq_tree": rule["cnf"], "missing": st["missing"], "missing_codes": st["missing_codes"],
           "met": st["met"], "status": st["status"], "notes": st["notes"], "taken": course["code"] in done,
           "basis": rule["basis"], "crn": str(crn or "").strip(), "term": (section or {}).get("term") or str(term or ""),
           "section_note": rule["note"], "concurrent_ok": rule["concurrent_ok"], "concurrent": st["concurrent"],
           "score_options": st["score_options"], "required_alts": st["required_alts"],
           "required_any": st["required_any"]}
    if rule["basis"] == "section":
        out["course_prereqs"] = course["prereqs"]
        out["course_prereq_tree"] = rule["course_cnf"]
    return out


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


ADVISOR_STOP_WORDS = {
    "what", "which", "should", "take", "next", "course", "courses", "class", "classes",
    "can", "the", "and", "for", "with", "that", "this", "have", "need", "want", "about",
    "semester", "year", "will", "does", "are", "help", "from", "some", "tell", "like", "recommend"
}


def recommend(user_id: str, interests: str = "", limit: int = 12) -> List[Dict[str, Any]]:
    """Courses the student hasn't taken whose listed prerequisites they have, ranked by how much they build on
    what they did (shared department, prerequisites satisfied) and by interest words.
    De-biased when explicit interest keywords are provided to avoid drowning out topical courses."""
    done = {r["code"] for r in completed(user_id)}
    depts = {c.split()[0] for c in done}
    words = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", interests or "")]
    interest_words = [w for w in words if w not in ADVISOR_STOP_WORDS]
    has_explicit_interest = bool(interest_words)
    out = []
    for r in db.conn().execute("SELECT * FROM catalog_courses WHERE school = 'wm'"):
        c = _row(r)
        if c["code"] in done:
            continue
        rd = readiness(user_id, c["code"])
        if not rd["met"]:  # strict: "check" (only an unverified score or admission would do) is left out too
            continue
        blob = f"{c['code']} {c['title']} {c['description']}".lower()

        # De-bias when explicit interest keywords are provided:
        # scale keyword matches to +10 and suppress the +3 past-department continuation bonus
        if has_explicit_interest:
            dept_bonus = 0
            kw_matches = sum(1 for w in interest_words if w in blob)
            kw_score = 10 * kw_matches
        else:
            dept_bonus = 3 if c["code"].split()[0] in depts else 0
            kw_score = sum(2 for w in words if w in blob)

        score = dept_bonus + 2 * len([p for p in c["prereq_codes"] if p in done]) + kw_score
        num = int(re.sub(r"\D", "", c["code"].split()[1]) or 0)
        score -= 0 if not done else abs(num // 100 - (max(int(re.sub(r"\D", "", d.split()[1]) or 0) for d in done) // 100 + 1)) * 0.5
        out.append({**c, "score": round(score, 1), "builds_on": [p for p in c["prereq_codes"] if p in done]})
    out.sort(key=lambda c: (-c["score"], c["code"]))
    return out[:limit]


def parse_credits(raw: Any) -> float:
    """Parses a credit value (number, string like '3', '1-4', '3 credits') into a float."""
    if raw is None or raw == "":
        return 3.0
    if isinstance(raw, (int, float)):
        return float(raw)
    m = re.search(r"(\d+(?:\.\d+)?)", str(raw))
    return float(m.group(1)) if m else 3.0


# ---------------------------------------------------------------- semester plans (read-only: rows from the retired
# Auto-Plan stay as the student's data; advisor_cart.py is the planning tool now)
def get_semester_plan(user_id: str, term: str = "") -> Optional[Dict[str, Any]]:
    """Retrieves the semester plan for a user, either for a specific term or their latest."""
    c = db.conn()
    if term:
        row = c.execute("SELECT * FROM semester_plans WHERE user_id = ? AND term = ?", (user_id, term)).fetchone()
    else:
        row = c.execute("SELECT * FROM semester_plans WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1", (user_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["courses"] = json.loads(d.get("courses_json") or "[]")
    except Exception:
        d["courses"] = []
    return d
