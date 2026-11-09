"""
Seat risk for the planning cart: how likely each course is to fill before the student can register, estimated
from past imported schedules (catalog_sections). Pure and deterministic: SQL plus arithmetic, no model calls.

for_codes() reads every course in one query and returns one risk object per code:
{score 0-1 or None, level high|medium|low|unknown, fill_phase, evidence[], confidence low|medium|high, estimate, live,
 past_terms, sections_next_term, other_sections[]}. research() ranks a student's cart by priority, then risk.

The history is thin (old terms mostly carry only a status, few rows have seat counts) and registration window dates
are not loaded, so every result is an estimate and many courses come out "unknown" or low confidence.
This module imports only db: never advisor_cart or server.
"""
import json
import re
import time
from typing import Any, Dict, Iterable, List, Optional

import db

PRIORITIES = ("must", "want", "nice")
PRIORITY_ORDER = {p: n for n, p in enumerate(PRIORITIES)}
CLASS_YEARS = ("Freshman", "Sophomore", "Junior", "Senior")
SEASONS = {"10": "Fall", "20": "Spring", "30": "Summer"}
MAX_CODES = 30
SAME_SEASON_TERMS = 6
OTHER_SEASON_WEIGHT, RECENCY = 0.4, 0.8
HIGH, MEDIUM = 0.65, 0.35
UNKNOWN_SORT_SCORE = 0.5  # an unknown risk ranks between likely-to-fill and usually-open courses
ESTIMATE = ("Estimate from past imported schedules, not a prediction you can count on: history is thin for many "
            "courses and registration window dates are not loaded.")
_SEATS_RE = re.compile(r"^\s*(-?\d+)\s*/\s*(\d+)")
_CLASS_OF_RE = re.compile(r"\bClass of (\d{4})\b")


def _term_label(term: str) -> str:
    year, part = term[:4], term[4:]
    if not year.isdigit() or part not in SEASONS:
        return term
    return f"{SEASONS[part]} {int(year) - 1 if part == '10' else int(year)}"


def _day(ts: Any) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.localtime(float(ts)))
    except (TypeError, ValueError, OverflowError):
        return "unknown date"


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _parse(row) -> Dict[str, Any]:
    d = dict(row)
    try:
        details = json.loads(d.get("details") or "{}")
    except (TypeError, ValueError):
        details = {}
    d["details"] = details if isinstance(details, dict) else {}
    seats = _SEATS_RE.match(str(d.get("seats") or ""))
    avail = _num(d["details"].get("seats_available"))
    cap = _num(d["details"].get("max_enrollment"))
    if avail is None and seats:
        avail = float(seats.group(1))
    if cap is None and seats:
        cap = float(seats.group(2))
    d["open"], d["cap"] = avail, cap
    # PATH marks a full section "F"; seat counts can go negative (over-enrolled), so anything <= 0 open is full
    d["full"] = d.get("status") == "F" or (avail is not None and avail <= 0)
    return d


def _weight(term: str, target: str) -> float:
    same = term[4:] == target[4:]
    years_back = max(0, int(target[:4]) - int(term[:4]) - (1 if same else 0))
    return (1.0 if same else OTHER_SEASON_WEIGHT) * RECENCY ** years_back


def _history(rows: List[Dict[str, Any]], target: str) -> Dict[str, Any]:
    """Past terms used for the estimate: the last 6 same-season terms (other seasons in that span, weighted less),
    or the last 6 terms of any season when the course never ran in this season."""
    by_term: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_term.setdefault(r["term"], []).append(r)
    past = sorted(by_term, reverse=True)
    same = [t for t in past if t[4:] == target[4:]][:SAME_SEASON_TERMS]
    chosen = [t for t in past if t >= same[-1]] if same else past[:SAME_SEASON_TERMS]
    return {"by_term": by_term, "past": past, "same": same, "terms": chosen}


def _share(by_term: Dict[str, List[Dict[str, Any]]], terms: Iterable[str], target: str) -> Optional[float]:
    num = den = 0.0
    for t in terms:
        secs = by_term.get(t) or []
        if not secs:
            continue
        w = _weight(t, target)
        num += w * sum(1 for s in secs if s["full"]) / len(secs)
        den += w
    return num / den if den else None


def _any_share(by_term: Dict[str, List[Dict[str, Any]]], terms: Iterable[str], target: str) -> Optional[float]:
    """Weighted share of terms in which at least one section filled: losing your section matters even when
    other sections of a big course kept seats."""
    num = den = 0.0
    for t in terms:
        secs = by_term.get(t) or []
        if not secs:
            continue
        w = _weight(t, target)
        num += w * any(s["full"] for s in secs)
        den += w
    return num / den if den else None


def _class_of(class_year: str, target: str) -> Optional[int]:
    if class_year not in CLASS_YEARS or not target[:4].isdigit():
        return None
    return int(target[:4]) + (3 - CLASS_YEARS.index(class_year))  # Senior: the class graduating this academic year


def _restriction_lines(restrictions: Iterable[Any], class_year: str, target: str) -> List[str]:
    """Seat reservations worth a check. Only the saved class year is compared; a major is never inferred."""
    class_of = _class_of(class_year, target)
    out: List[str] = []
    for raw in restrictions:
        text = " ".join(str(raw or "").split())
        low = text.lower()
        if not text or low.startswith(("prerequisite", "a minimum grade", "corequisite")):
            continue
        if "limited to" not in low and "may not enroll" not in low and "reserved" not in low:
            continue
        if "level students" in low and "undergraduate" in low:
            continue  # "limited to ... Undergraduate level students": every undergraduate qualifies
        years = [int(y) for y in _CLASS_OF_RE.findall(text)] if "law class" not in low else []
        excluded = "may not enroll" in low
        if years and class_of:
            if excluded and class_of in years:
                out.append(f"{text[:200]} Your saved class year ({class_year}, Class of {class_of}) is excluded.")
            elif not excluded and class_of not in years:
                out.append(f"{text[:200]} Your saved class year ({class_year}, Class of {class_of}) is not listed.")
            continue
        m = re.search(r"limited to (.+?)\.?$", text, re.I)
        if m:
            out.append(f"Seats reserved for {m.group(1)[:180]}; check you qualify.")
        elif excluded:
            out.append(f"Not open to: {text[:low.index('may not enroll')].strip()[:180]}; check you qualify.")
        else:
            out.append(f"{text[:180].rstrip('.')}; check you qualify.")
    return list(dict.fromkeys(out))[:3]


def _section_share(rows: List[Dict[str, Any]], section: str, target: str) -> Dict[str, Any]:
    """How often this section number filled in past terms (CRNs change; section numbers mostly don't)."""
    by_term: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        if r.get("section") == section:
            by_term.setdefault(r["term"], []).append(r)
    terms = sorted(by_term, reverse=True)[:SAME_SEASON_TERMS * 2]
    return {"terms": len(terms), "full": sum(1 for t in terms if any(s["full"] for s in by_term[t])),
            "share": _share(by_term, terms, target)}


def _fill_phase(level: str, score: Optional[float], full_now: bool, any_full: Optional[float] = None) -> str:
    if full_now:
        return "Full now"
    if level == "unknown" or score is None:
        return "Unknown"
    if score >= 0.8:
        return "Likely fills in the earliest registration windows"
    if score >= HIGH:
        return "Likely fills during registration"
    if score >= MEDIUM:
        return "May fill before add/drop"
    if any_full is not None and any_full >= 0.5:
        return "Some sections usually fill; others keep seats through add/drop"
    return "Usually has open seats through add/drop"


def _risk(code: str, rows: List[Dict[str, Any]], target: str, crn: str, class_year: str) -> Dict[str, Any]:
    past_rows = [r for r in rows if r["term"] < target]
    now = sorted((r for r in rows if r["term"] == target), key=lambda r: (r.get("section") or "", r["crn"]))
    chosen = next((r for r in now if str(r["crn"]) == str(crn or "")), None) if crn else None
    h = _history(past_rows, target)
    evidence: List[str] = []
    season = SEASONS.get(target[4:], "same-season")

    sections_full = _share(h["by_term"], h["terms"], target)
    any_full = _any_share(h["by_term"], h["terms"], target)
    # half "how many seats ran out", half "how often some section ran out", so one section filling every
    # spring is not diluted to nothing by the other sections of a large course
    score = None if sections_full is None else 0.5 * sections_full + 0.5 * (any_full or 0.0)
    if h["same"]:
        filled = sum(1 for t in h["same"] if any(s["full"] for s in h["by_term"][t]))
        secs = [s for t in h["same"] for s in h["by_term"][t]]
        any_full = max(any_full or 0.0, filled / len(h["same"]))  # the wording follows the plain same-season count
        evidence.append(f"A section filled in {filled} of the last {len(h['same'])} {season} terms "
                        f"({sum(1 for s in secs if s['full'])} of {len(secs)} sections).")
        others = [t for t in h["terms"] if t[4:] != target[4:]]
        if others:
            ofilled = sum(1 for t in others if any(s["full"] for s in h["by_term"][t]))
            evidence.append(f"Other terms in that span (weighted less): a section filled in {ofilled} of {len(others)}.")
    elif h["past"]:
        filled = sum(1 for t in h["terms"] if any(s["full"] for s in h["by_term"][t]))
        evidence.append(f"Never offered in a {season} term before; other terms (weighted less): "
                        f"a section filled in {filled} of {len(h['terms'])}.")

    caps = [r["cap"] for r in ([chosen] if chosen and chosen["cap"] else now) if r["cap"]]
    if not caps:
        caps = [r["cap"] for t in h["past"] for r in h["by_term"][t] if r["cap"]][:6]
    cap = sorted(caps)[len(caps) // 2] if caps else None
    if score is not None and cap:
        if cap <= 20:
            score += 0.10
            evidence.append(f"Small class: about {int(cap)} seats per section.")
        elif cap >= 100:
            score -= 0.10
            evidence.append(f"Large class: about {int(cap)} seats per section.")
    if score is not None and now:
        if len(now) == 1:
            score += 0.10
            evidence.append(f"Only one section in {_term_label(target)}.")
        elif len(now) >= 4:
            score -= 0.10
            evidence.append(f"{len(now)} sections in {_term_label(target)}.")

    if chosen and score is not None and chosen.get("section"):  # no section number: nothing to match against
        own = _section_share(past_rows, chosen.get("section") or "", target)
        if own["terms"] >= 2 and own["share"] is not None:
            score = 0.7 * score + 0.3 * own["share"]
            evidence.append(f"Section {chosen.get('section')} filled in {own['full']} of {own['terms']} past terms.")

    live = None
    counted = [r for r in now if r["cap"] and r["open"] is not None]
    if counted:
        seats_open = sum(max(0.0, r["open"]) for r in counted)
        capacity = sum(r["cap"] for r in counted)
        as_of = max(float(r.get("updated_at") or 0) for r in counted)
        started = any(r["open"] < r["cap"] for r in counted)
        live = {"open": int(seats_open), "capacity": int(capacity), "started": started, "as_of": as_of}
        if started:
            fill = 1 - seats_open / capacity
            if score is not None:
                score = max(score, 0.7 * fill + 0.3 * score)
            evidence.append(f"Registration has started: {int(capacity - seats_open)} of {int(capacity)} seats taken "
                            f"(as of {_day(as_of)}).")
        else:
            evidence.append(f"No seats taken yet: {int(seats_open)} of {int(capacity)} open (as of {_day(as_of)}).")

    full_now = bool(chosen and chosen["full"])
    if full_now:
        score = max(score or 0.0, 0.9)
        evidence.append(f"Full at last snapshot (as of {_day(chosen.get('updated_at'))}).")

    restrictions = (chosen["details"].get("restrictions") or []) if chosen else \
        [x for r in now for x in (r["details"].get("restrictions") or [])]
    evidence.extend(_restriction_lines(restrictions if isinstance(restrictions, list) else [], class_year, target))

    if full_now:
        level = "high"
    elif not now:
        level, score = "unknown", None
        evidence.insert(0, f"No sections listed for {_term_label(target)}.")
    elif (len(h["past"]) < 2 or score is None) and live and live["started"] and live["capacity"] \
            and 1 - live["open"] / live["capacity"] >= MEDIUM:
        # little history, but seats are going now: the live count is the estimate
        score = 1 - live["open"] / live["capacity"]
        level = "high" if score >= HIGH else "medium"
        evidence.insert(0, f"Only {len(h['past'])} past term(s) on file: estimate from the live seat count only.")
    elif len(h["past"]) < 2 or score is None:
        level, score = "unknown", None
        evidence.insert(0, f"Only {len(h['past'])} past term(s) on file: too little history to estimate.")
    else:
        score = min(1.0, max(0.0, score))
        level = "high" if score >= HIGH else "medium" if score >= MEDIUM else "low"

    has_counts = any(r["cap"] for r in rows)
    if level == "unknown":
        confidence = "low"
    elif len(h["same"]) >= 5 and has_counts:
        confidence = "high"
    elif len(h["same"]) >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    other_sections = []
    if chosen:
        mine = _section_share(past_rows, chosen.get("section") or "", target)
        for r in now:
            if r is chosen or r["full"]:
                continue
            theirs = _section_share(past_rows, r.get("section") or "", target)
            if full_now:
                note = "is not full at the last snapshot"
            elif (theirs["terms"] >= 2 and mine["terms"] >= 2 and theirs["share"] is not None and mine["share"] is not None
                  and theirs["share"] <= mine["share"] - 0.2):
                note = f"filled in {theirs['full']} of {theirs['terms']} past terms"
            else:
                continue
            other_sections.append({"crn": str(r["crn"]), "section": r.get("section") or "", "note": note})

    return {"code": code, "title": (now[0]["title"] if now else (past_rows[0]["title"] if past_rows else "")) or code,
            "score": round(score, 2) if score is not None else None, "level": level,
            "fill_phase": _fill_phase(level, score, full_now, any_full), "evidence": evidence, "confidence": confidence,
            "estimate": ESTIMATE, "live": live, "past_terms": len(h["past"]), "sections_next_term": len(now),
            "other_sections": other_sections[:2]}


def for_codes(codes: Iterable[str], term: str, crns: Optional[Dict[str, str]] = None,
              class_year: str = "") -> Dict[str, Dict[str, Any]]:
    """Risk for each course code (at most 30) in term, from one query over the imported sections."""
    codes = list(dict.fromkeys(str(c) for c in codes if c))[:MAX_CODES]
    if not codes:
        return {}
    crns = crns or {}
    marks = ", ".join("?" * len(codes))
    rows = db.conn().execute(
        f"SELECT term, crn, code, section, title, status, seats, details, updated_at FROM catalog_sections "
        f"WHERE school = 'wm' AND code IN ({marks}) AND term <= ? AND status != 'I' ORDER BY term DESC, section",
        (*codes, term)).fetchall()
    grouped: Dict[str, List[Dict[str, Any]]] = {c: [] for c in codes}
    for r in rows:
        grouped[r["code"]].append(_parse(r))
    return {c: _risk(c, grouped[c], term, crns.get(c, ""), class_year) for c in codes}


def class_year(user_id: str) -> str:
    r = db.conn().execute("SELECT class_year FROM advisor_prefs WHERE user_id = ?", (user_id,)).fetchone()
    return r["class_year"] if r else ""


def _sort_score(item: Dict[str, Any]) -> float:
    risk = item.get("risk") or {}
    return risk["score"] if risk.get("score") is not None else UNKNOWN_SORT_SCORE


def _advice(item: Dict[str, Any], has_backup: bool) -> List[str]:
    risk = item.get("risk")
    if not risk:
        return ["No estimate available for this course."]
    level, out = risk["level"], []
    if level == "unknown":
        out.append("No sections are listed for this term yet; check again after the schedule updates."
                   if not risk.get("sections_next_term") else
                   "Too little past schedule data to estimate; if you need it, register for it early anyway.")
    elif level == "high":
        out.append("Register for it first, in your earliest registration window.")
    elif level == "medium":
        out.append("Register for it early in your window.")
    else:
        out.append("Usually has seats: it can wait until your higher-risk courses are in.")
    if level in ("high", "medium") and item.get("cart_type") == "primary" and not has_backup:
        out.append("Add a backup in case it fills.")
    if level == "high" and item.get("priority") == "nice":
        out.append("It's a nice-to-have that tends to fill: decide whether it is worth an early slot.")
    for s in risk.get("other_sections") or []:
        out.append(f"Section {s['section']} (CRN {s['crn']}) {s['note']}: compare it before you register "
                   f"(the cart won't switch sections for you).")
    return out


def rank(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Registration order: must before want before nice, then the higher risk first, then the code."""
    has_backup = any(i.get("cart_type") == "backup" for i in items)
    # primary picks first (a backup is only registered for if a primary falls through), then priority, then risk
    ordered = sorted(items, key=lambda i: (i.get("cart_type") == "backup", PRIORITY_ORDER.get(i.get("priority"), 1),
                                           -_sort_score(i), i.get("code") or ""))
    return [{"rank": n, "code": i["code"], "title": i.get("title") or (i.get("risk") or {}).get("title") or i["code"],
             "cart_type": i.get("cart_type") or "primary", "priority": i.get("priority") or "want",
             "section_crn": i.get("section_crn") or "", "risk": i.get("risk"), "advice": _advice(i, has_backup)}
            for n, i in enumerate(ordered, 1)]


def research(user_id: str, term: str) -> Dict[str, Any]:
    """The student's cart for term as a registration plan: ranked items with risk, evidence and advice."""
    rows = db.conn().execute("SELECT course_code, cart_type, section_crn, priority FROM student_carts "
                             "WHERE user_id = ? AND term = ? ORDER BY created_at, course_code LIMIT ?",
                             (user_id, term, MAX_CODES)).fetchall()
    year = class_year(user_id)
    risks = for_codes([r["course_code"] for r in rows], term, {r["course_code"]: r["section_crn"] for r in rows}, year)
    items = [{"code": r["course_code"], "cart_type": r["cart_type"], "section_crn": r["section_crn"],
              "priority": r["priority"], "risk": risks.get(r["course_code"])} for r in rows]
    order = rank(items)
    likely = [o["code"] for o in order if (o["risk"] or {}).get("level") == "high"]
    unknown = [o["code"] for o in order if (o["risk"] or {}).get("level") == "unknown"]
    summary = ("Your cart is empty." if not order else
               f"Register in this order: {', '.join(o['code'] for o in order)}."
               + (f" Likely to fill: {', '.join(likely)}." if likely else "")
               + (f" Not enough history to estimate: {', '.join(unknown)}." if unknown else ""))
    return {"term": term, "term_name": _term_label(term), "class_year": year, "estimate_note": ESTIMATE,
            "order": order, "summary": summary}
