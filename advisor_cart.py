"""
Planning cart: the courses a student is considering for a term, as primary picks and backups, each with an
optional section (CRN) from the imported schedule. The cart only holds what the student chose: it never picks a
section or a course for them. cart_summary() adds the credit load (12 full-time, 14-16 recommended, 18 the normal
maximum; only primary courses count) and time conflicts between the chosen sections. Each item carries the
student's priority (must | want | nice) and a seat-risk estimate from advisor_risk (or None); research() ranks the cart.

Tables are created from advisor.init(); the routes come from build_router() so this module never imports server.
"""
import re
import time
from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import advisor
import advisor_risk
import db
import wm_advising

SCHEMA = """
CREATE TABLE IF NOT EXISTS student_carts (
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    term             TEXT NOT NULL,                  -- e.g. "202720"
    course_code      TEXT NOT NULL,                  -- "CSCI 241"
    cart_type        TEXT NOT NULL DEFAULT 'primary', -- primary | backup
    section_crn      TEXT NOT NULL DEFAULT '',        -- '' until the student picks a section
    studio_course_id TEXT NOT NULL DEFAULT '',        -- the Studio course launched from this row
    notes            TEXT NOT NULL DEFAULT '',
    created_at       REAL NOT NULL,
    priority         TEXT NOT NULL DEFAULT 'want',   -- must | want | nice
    PRIMARY KEY (user_id, term, course_code)
);
CREATE INDEX IF NOT EXISTS idx_student_carts_user ON student_carts(user_id, term);
CREATE TABLE IF NOT EXISTS advisor_prefs (
    user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    class_year TEXT NOT NULL DEFAULT ''              -- '' | Freshman | Sophomore | Junior | Senior
);
"""

TYPES = ("primary", "backup")
PRIORITIES = advisor_risk.PRIORITIES
CLASS_YEARS = advisor_risk.CLASS_YEARS
TERM_RE = re.compile(r"^\d{6}$")
MIN_FULL_TIME, RECOMMENDED_MIN, RECOMMENDED_MAX, MAX_NORMAL = 12.0, 14.0, 16.0, 18.0
DEFAULT_CREDITS = 3.0
MAX_ITEMS = 30
MAX_NOTES = 500


class CartError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def init():
    c = db.conn()
    c.executescript(SCHEMA)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(student_carts)")}
    if "priority" not in cols:  # carts made before priorities existed
        c.execute("ALTER TABLE student_carts ADD COLUMN priority TEXT NOT NULL DEFAULT 'want'")
    c.commit()


def _code(code: str) -> str:
    m = advisor.CODE_RE.search(str(code or "").upper())
    if not m:
        raise CartError(f"'{str(code)[:40]}' is not a course code (e.g. CSCI 241).")
    return advisor.norm_code(*m.groups())


def _term(term: str) -> str:
    term = str(term or "").strip() or wm_advising.next_term()
    if not TERM_RE.match(term):
        raise CartError("The term must be a term code like 202720.")
    return term


def _section(code: str, term: str, crn: str) -> Optional[Dict[str, Any]]:
    """The listed section with this CRN for this course and term, or None."""
    crn = str(crn or "").strip()
    if not crn:
        return None
    for s in advisor.list_sections(code=code, term=term, limit=200):
        if str(s.get("crn")) == crn and s.get("code") == code:
            return s
    return None


def _row(user_id: str, term: str, code: str):
    return db.conn().execute("SELECT * FROM student_carts WHERE user_id = ? AND term = ? AND course_code = ?",
                             (user_id, term, code)).fetchone()


def _require_row(user_id: str, term: str, code: str):
    r = _row(user_id, term, code)
    if not r:
        raise CartError(f"{code} is not in your cart for {wm_advising.term_name(term)}.", 404)
    return r


def _checked_priority(priority: str) -> str:
    if priority not in PRIORITIES:
        raise CartError("priority must be must, want or nice.")
    return priority


def _checked_crn(code: str, term: str, crn: Optional[str]) -> str:
    crn = str(crn or "").strip()
    if crn and not _section(code, term, crn):
        raise CartError(f"CRN {crn[:12]} is not a {code} section in {wm_advising.term_name(term)}.")
    return crn


# ---------------------------------------------------------------- changes
def add(user_id: str, term: str, code: str, cart_type: str = "primary", crn: str = "", notes: str = "",
        priority: Optional[str] = None) -> Dict[str, Any]:
    """Adds a catalog course, or updates its type/section if it is already there (adding twice keeps one row).
    priority (must | want | nice) defaults to want for a new row and is kept for an existing one unless given."""
    term, code = _term(term), _code(code)
    if cart_type not in TYPES:
        raise CartError("cart_type must be primary or backup.")
    if priority is not None:
        _checked_priority(priority)
    if not advisor.get_course(code):
        raise CartError(f"{code} is not in the imported catalog.", 404)
    crn = _checked_crn(code, term, crn)
    c = db.conn()
    existing = _row(user_id, term, code)
    if existing:
        c.execute("UPDATE student_carts SET cart_type = ?, section_crn = ?, notes = ?, priority = ? "
                  "WHERE user_id = ? AND term = ? AND course_code = ?",
                  (cart_type, crn or existing["section_crn"], (notes or existing["notes"])[:MAX_NOTES],
                   priority or existing["priority"], user_id, term, code))
    else:
        n = c.execute("SELECT COUNT(*) FROM student_carts WHERE user_id = ? AND term = ?", (user_id, term)).fetchone()[0]
        if n >= MAX_ITEMS:
            raise CartError(f"A cart holds at most {MAX_ITEMS} courses.")
        c.execute("INSERT INTO student_carts (user_id, term, course_code, cart_type, section_crn, notes, created_at, priority) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (user_id, term, code, cart_type, crn, (notes or "")[:MAX_NOTES], time.time(), priority or "want"))
    c.commit()
    return get(user_id, term)


def update(user_id: str, term: str, code: str, cart_type: Optional[str] = None, crn: Optional[str] = None,
           notes: Optional[str] = None, priority: Optional[str] = None) -> Dict[str, Any]:
    """Changes any of type, section ('' clears it), notes and priority of a course already in the cart."""
    term, code = _term(term), _code(code)
    _require_row(user_id, term, code)
    fields: Dict[str, Any] = {}
    if cart_type is not None:
        if cart_type not in TYPES:
            raise CartError("cart_type must be primary or backup.")
        fields["cart_type"] = cart_type
    if crn is not None:
        fields["section_crn"] = _checked_crn(code, term, crn)
    if notes is not None:
        fields["notes"] = str(notes)[:MAX_NOTES]
    if priority is not None:
        fields["priority"] = _checked_priority(priority)
    if fields:
        cols = ", ".join(f"{k} = ?" for k in fields)
        db.conn().execute(f"UPDATE student_carts SET {cols} WHERE user_id = ? AND term = ? AND course_code = ?",
                          (*fields.values(), user_id, term, code))
        db.conn().commit()
    return get(user_id, term)


def move(user_id: str, term: str, code: str, cart_type: str) -> Dict[str, Any]:
    return update(user_id, term, code, cart_type=cart_type)


def set_section(user_id: str, term: str, code: str, crn: str) -> Dict[str, Any]:
    return update(user_id, term, code, crn=crn)


def remove(user_id: str, term: str, code: str) -> Dict[str, Any]:
    term, code = _term(term), _code(code)
    _require_row(user_id, term, code)
    db.conn().execute("DELETE FROM student_carts WHERE user_id = ? AND term = ? AND course_code = ?", (user_id, term, code))
    db.conn().commit()
    return get(user_id, term)


def set_studio_course(user_id: str, term: str, code: str, course_id: str) -> bool:
    """Links a launched Studio course to the cart row, if the course is in the cart for that term."""
    try:
        term, code = _term(term), _code(code)
    except CartError:
        return False
    cur = db.conn().execute("UPDATE student_carts SET studio_course_id = ? WHERE user_id = ? AND term = ? AND course_code = ?",
                            (course_id, user_id, term, code))
    db.conn().commit()
    return cur.rowcount > 0


# ---------------------------------------------------------------- reading
def _number(raw: Any) -> Optional[float]:
    m = re.search(r"\d+(?:\.\d+)?", str(raw or ""))
    return float(m.group(0)) if m else None


def item_credits(item: Dict[str, Any]) -> Dict[str, Any]:
    """Section credits, else catalog credits, else 3.0 marked approximate (as is a variable range like 1-4)."""
    for raw in ((item.get("section") or {}).get("credits"), item.get("catalog_credits")):
        value = _number(raw)
        if value is not None:
            return {"credits": value, "approximate": bool(re.search(r"\d\s*(?:-|–|to|or)\s*\d", str(raw)))}
    return {"credits": DEFAULT_CREDITS, "approximate": True}


def _compact_section(s: Dict[str, Any]) -> Dict[str, Any]:
    return {k: s.get(k) for k in ("crn", "section", "term", "term_name", "instructor", "meets", "meeting_times",
                                  "schedule_type", "seats", "credits")}


def _studio_course(user_id: str, cid: str) -> str:
    """The linked Studio course id while that course exists and belongs to the student, else ''."""
    if not cid:
        return ""
    course = db.get_course(cid)
    return cid if course and course.get("user_id") == user_id else ""


def get(user_id: str, term: str = "") -> Dict[str, Any]:
    """The cart for a term: items (with the term's listed sections to choose from), flags and the summary."""
    term = _term(term)
    rows = db.conn().execute("SELECT * FROM student_carts WHERE user_id = ? AND term = ? ORDER BY created_at, course_code",
                             (user_id, term)).fetchall()
    done = {r["code"] for r in advisor.completed(user_id) if (r.get("grade") or "").upper() in advisor.PASSING}
    items = []
    for r in rows:
        code = r["course_code"]
        course = advisor.get_course(code) or {}
        sections = [s for s in advisor.list_sections(code=code, term=term, limit=200) if s.get("code") == code]
        chosen = next((s for s in sections if str(s.get("crn")) == r["section_crn"]), None) if r["section_crn"] else None
        studio = _studio_course(user_id, r["studio_course_id"])
        if studio != r["studio_course_id"]:  # the launched course was deleted (or isn't the student's): forget it
            db.conn().execute("UPDATE student_carts SET studio_course_id = '' WHERE user_id = ? AND term = ? AND course_code = ?",
                              (user_id, term, code))
            db.conn().commit()
        flags = []
        if not chosen:
            flags.append("no_section")
        if code in done:
            flags.append("already_done")
        elif course and advisor.readiness(user_id, code).get("status") == "missing":
            flags.append("prereq_missing")
        item = {"code": code, "title": course.get("title") or code, "cart_type": r["cart_type"],
                "section_crn": r["section_crn"], "section": _compact_section(chosen) if chosen else None,
                "sections": [_compact_section(s) for s in sections], "catalog_credits": course.get("credits") or "",
                "attributes": course.get("attributes") or [], "studio_course_id": studio, "notes": r["notes"],
                "flags": flags, "created_at": r["created_at"]}
        item.update(item_credits(item))
        items.append(item)
    _add_risk(user_id, term, items, [r["priority"] for r in rows])
    return {"term": term, "term_name": wm_advising.term_name(term), "items": items, "summary": cart_summary(items),
            "terms": terms(user_id, term)}


def _add_risk(user_id: str, term: str, items: List[Dict[str, Any]], priorities: List[str]) -> None:
    """Each item gets its priority and a seat-risk estimate (one query for the whole cart); risk is None on failure."""
    risks: Dict[str, Any] = {}
    if items:
        try:
            risks = advisor_risk.for_codes([i["code"] for i in items], term,
                                           {i["code"]: i["section_crn"] for i in items}, get_prefs(user_id)["class_year"])
        except Exception as e:  # an estimate must never break the cart
            print(f"[advisor_risk failed for term {term}]: {type(e).__name__}: {e}")
    for item, priority in zip(items, priorities):
        item["priority"] = priority if priority in PRIORITIES else "want"
        item["risk"] = risks.get(item["code"])


def get_prefs(user_id: str) -> Dict[str, Any]:
    return {"class_year": advisor_risk.class_year(user_id)}


def set_prefs(user_id: str, class_year: str = "") -> Dict[str, Any]:
    """Saves the optional class year ('' clears it); seat-risk only compares it with class-year restrictions."""
    class_year = str(class_year or "")
    if class_year and class_year not in CLASS_YEARS:
        raise CartError("class_year must be Freshman, Sophomore, Junior, Senior or empty.")
    db.conn().execute("INSERT INTO advisor_prefs (user_id, class_year) VALUES (?, ?) "
                      "ON CONFLICT(user_id) DO UPDATE SET class_year = excluded.class_year", (user_id, class_year))
    db.conn().commit()
    return get_prefs(user_id)


def research(user_id: str, term: str = "") -> Dict[str, Any]:
    """The cart as a ranked registration plan (advisor_risk.research), for a checked term."""
    term = _term(term)
    return {**advisor_risk.research(user_id, term), "term_name": wm_advising.term_name(term)}


def cart_summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Credit load and section time conflicts. Only primary courses count; backups are alternatives."""
    primary = [i for i in items if i.get("cart_type") == "primary"]
    credits, approximate = 0.0, False
    for i in primary:
        cr = item_credits(i) if "credits" not in i else {"credits": i["credits"], "approximate": i.get("approximate", False)}
        credits += cr["credits"]
        approximate = approximate or cr["approximate"]
    timed = [{"code": i["code"], "meets": i["section"].get("meets") or "", "meeting_times": i["section"].get("meeting_times") or []}
             for i in primary if i.get("section")]
    if credits < MIN_FULL_TIME:
        load = "underload"
    elif credits < RECOMMENDED_MIN:
        load = "full_time"
    elif credits <= RECOMMENDED_MAX:
        load = "recommended"
    elif credits <= MAX_NORMAL:
        load = "heavy"
    else:
        load = "overload"
    return {"credits": round(credits, 1), "approximate": approximate, "load": load,
            "min_full_time": MIN_FULL_TIME, "recommended_min": RECOMMENDED_MIN, "recommended_max": RECOMMENDED_MAX,
            "max_normal": MAX_NORMAL, "primary_count": len(primary), "backup_count": len(items) - len(primary),
            "conflicts": wm_advising.check_schedule_conflicts(timed),
            "without_section": [i["code"] for i in primary if not i.get("section")]}


def terms(user_id: str, current: str = "") -> List[Dict[str, str]]:
    """Terms the student can plan for: the next term, terms with imported sections and terms already in a cart."""
    codes = {wm_advising.next_term()}
    if current:
        codes.add(current)
    codes |= {t["term"] for t in advisor.stats().get("terms") or [] if TERM_RE.match(str(t.get("term") or ""))}
    codes |= {r[0] for r in db.conn().execute("SELECT DISTINCT term FROM student_carts WHERE user_id = ?", (user_id,))}
    out = []
    for t in sorted(codes, reverse=True):
        try:
            out.append({"term": t, "term_name": wm_advising.term_name(t)})
        except ValueError:
            out.append({"term": t, "term_name": t})
    return out


def context_block(user_id: str, term: str) -> str:
    """The cart as advisor-chat data (fenced: titles and notes are imported/student text, not instructions)."""
    cart = get(user_id, term)
    if not cart["items"]:
        return ""
    s = cart["summary"]
    lines = [f"STUDENT'S CART for {cart['term_name']} (term {cart['term']}): {s['primary_count']} primary, "
             f"{s['backup_count']} backup; primary load {s['credits']}{'~' if s['approximate'] else ''} credits ({s['load']})."]
    for i in cart["items"]:
        sec = i["section"]
        where = (f"sec {sec.get('section')} CRN {sec.get('crn')}" + (f" {sec['meets']}" if sec.get("meets") else "")
                 + (f" ({sec['instructor']})" if sec.get("instructor") else "")) if sec else "no section chosen"
        risk = i.get("risk")
        line = (f"- {i['cart_type'].upper()} {i['code']}: {i['title']} ({i['credits']}{'~' if i['approximate'] else ''} cr), {where}"
                + (f" [{', '.join(i['flags'])}]" if i["flags"] else "") + f", priority {i['priority']}"
                + (f", seat risk {risk['level']} ({risk['confidence']} confidence)" if risk else ""))
        if i.get("notes"):
            line += f" | student note: {i['notes'][:200]}"
        lines.append(line)
    for c in s["conflicts"]:
        lines.append(f"- CONFLICT: {c['description']}")
    order = advisor_risk.rank(cart["items"])
    lines.append("REGISTRATION ORDER (estimate from past imported schedules; registration window dates not loaded): "
                 + "; ".join(f"{o['rank']}. {o['code']} ({o['priority']}, risk {(o['risk'] or {}).get('level', 'unknown')}"
                             f"{', ' + o['risk']['fill_phase'].lower() if o['risk'] else ''})" for o in order))
    for o in order:
        for e in ((o["risk"] or {}).get("evidence") or [])[:3]:
            lines.append(f"  {o['code']} evidence: {e}")
    body = "\n".join(lines).replace("<<<", "<<").replace(">>>", ">>")
    return f"<<<CART\n{body}\nCART>>>"


# ---------------------------------------------------------------- routes
Priority = Literal["must", "want", "nice"]


class CartAdd(BaseModel):
    code: str
    term: Optional[str] = ""
    cart_type: Optional[str] = "primary"
    section_crn: Optional[str] = ""
    notes: Optional[str] = ""
    priority: Optional[Priority] = None


class CartPatch(BaseModel):
    term: Optional[str] = ""
    cart_type: Optional[str] = None
    section_crn: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[Priority] = None


class PrefsPut(BaseModel):
    class_year: Optional[str] = ""


def build_router(*, rate_limit: Callable[[str], None], require_user: Callable[[str], Any],
                 current_user: Callable[[], Any], auth_required: Callable[[], bool]) -> APIRouter:
    """Cart routes. require_user checks the profile (and, with accounts on, that it is the signed-in user's own)."""
    router = APIRouter()

    def run(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except CartError as e:
            raise HTTPException(status_code=e.status, detail=str(e))

    @router.get("/api/advisor/{user_id}/cart")
    def cart_get(user_id: str, term: str = ""):
        require_user(user_id)
        return run(get, user_id, term)

    @router.post("/api/advisor/{user_id}/cart")
    def cart_add(user_id: str, body: CartAdd):
        require_user(user_id)
        rate_limit("advisor")
        return run(add, user_id, body.term or "", body.code, body.cart_type or "primary", body.section_crn or "", body.notes or "",
                   body.priority)

    @router.get("/api/advisor/{user_id}/cart/research")
    def cart_research(user_id: str, term: str = ""):
        require_user(user_id)
        return run(research, user_id, term)

    @router.get("/api/advisor/{user_id}/prefs")
    def prefs_get(user_id: str):
        require_user(user_id)
        return get_prefs(user_id)

    @router.put("/api/advisor/{user_id}/prefs")
    def prefs_put(user_id: str, body: PrefsPut):
        require_user(user_id)
        rate_limit("advisor")
        return run(set_prefs, user_id, body.class_year or "")

    @router.patch("/api/advisor/{user_id}/cart/{code}")
    def cart_update(user_id: str, code: str, body: CartPatch):
        require_user(user_id)
        rate_limit("advisor")
        return run(update, user_id, body.term or "", code, body.cart_type, body.section_crn, body.notes, body.priority)

    @router.delete("/api/advisor/{user_id}/cart/{code}")
    def cart_remove(user_id: str, code: str, term: str = ""):
        require_user(user_id)
        rate_limit("advisor")
        return run(remove, user_id, term, code)

    return router
