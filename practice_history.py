"""History practice types (docs/agy-tasks/history_interactives.md §A). server.py merges NORMALIZERS into
PRACTICE_NORMALIZERS; each function gets the raw item `p` and `base` = {id, type, prompt, explanation, concept}
and returns the cleaned item, or None to drop it. Standard library only: this module never imports server.py.
Bodies live in src/practice/history.jsx."""
import math

MAPS = ("world", "europe", "mediterranean", "americas", "asia")  # public/maps/<name>.svg


def _s(v, n):
    return str(v if v is not None else "").strip()[:n]


def _strings(items, n, limit):
    """Non-empty, de-duplicated strings (order kept)."""
    out = []
    for v in items if isinstance(items, list) else []:
        s = _s(v, n)
        if s and s not in out:
            out.append(s)
    return out[:limit]


def _number(v):
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _choice(options, answer):
    """(options, answer) for a multiple-choice question: 2-5 distinct options, answer is one of them (an int
    answer is read as an index); None when that doesn't hold."""
    raw = [_s(o, 200) for o in options] if isinstance(options, list) else []
    if not raw or any(not o for o in raw) or len(set(raw)) != len(raw) or not 2 <= len(raw) <= 5:
        return None
    if isinstance(answer, int) and not isinstance(answer, bool) and 0 <= answer < len(raw):
        answer = raw[answer]
    answer = _s(answer, 200)
    return (raw, answer) if answer in raw else None


def _np_categorize(p, base):
    """Sort items into buckets. Fields: `buckets` (2-4 distinct names) and `items` (4-12 pairs `[text, bucket]`,
    or `{text, bucket}` objects; texts distinct). Graded when every item sits in its bucket. Dropped when an
    item's bucket is not one of `buckets`, a bucket has no item, texts repeat, or the counts are out of range."""
    buckets = _strings(p.get("buckets"), 60, 99)
    if not 2 <= len(buckets) <= 4 or len(buckets) != len([b for b in p.get("buckets") or [] if _s(b, 60)]):
        return None
    items = []
    for it in p.get("items") if isinstance(p.get("items"), list) else []:
        if isinstance(it, dict):
            text, bucket = it.get("text"), it.get("bucket")
        elif isinstance(it, (list, tuple)) and len(it) == 2:
            text, bucket = it
        else:
            return None
        text, bucket = _s(text, 160), _s(bucket, 60)
        if not text or bucket not in buckets:
            return None
        items.append([text, bucket])
    if not 4 <= len(items) <= 12 or len({t for t, _ in items}) != len(items):
        return None
    if any(not any(b == bk for _, bk in items) for b in buckets):
        return None
    return {**base, "buckets": buckets, "items": items}


def _np_cause_effect(p, base):
    """Build a cause-and-effect chain. Fields: `chain` (3-6 distinct events, cause first) and optional `links`
    (one "why" per join, so len(chain) - 1; any other length is ignored and stored as []). Graded when the
    student's order matches `chain`; links[i] is revealed when the join after chain[i] is right. Dropped when
    events repeat or there are fewer than 3 or more than 6."""
    raw = [_s(e, 200) for e in p.get("chain") or []] if isinstance(p.get("chain"), list) else []
    if any(not e for e in raw) or len(set(raw)) != len(raw) or not 3 <= len(raw) <= 6:
        return None
    links = [_s(w, 300) for w in p.get("links") or []] if isinstance(p.get("links"), list) else []
    return {**base, "chain": raw, "links": links if len(links) == len(raw) - 1 else []}


def _np_source_analysis(p, base):
    """Read a primary source and answer questions about it. Fields: `source` {text (cut to 1500 chars), author,
    date, citation} and `questions` [{question, options (2-5 distinct), answer (option text or index)}], at most
    5 kept. Graded per question like fill_blank; ok when all are right. Invalid questions are dropped; the item is
    dropped when the source has no text or no question is valid."""
    src = p.get("source") if isinstance(p.get("source"), dict) else {}
    text = _s(src.get("text"), 1500)
    if not text:
        return None
    questions = []
    for qd in p.get("questions") if isinstance(p.get("questions"), list) else []:
        if not isinstance(qd, dict) or not _s(qd.get("question"), 300):
            continue
        ch = _choice(qd.get("options"), qd.get("answer"))
        if ch:
            questions.append({"question": _s(qd["question"], 300), "options": ch[0], "answer": ch[1]})
    if not questions:
        return None
    return {**base, "source": {"text": text, "author": _s(src.get("author"), 120), "date": _s(src.get("date"), 60),
                               "citation": _s(src.get("citation"), 300)}, "questions": questions[:5]}


def _np_map_pins(p, base):
    """Drag labels onto an outline map. Fields: `map` (world | europe | mediterranean | americas | asia, the files
    in public/maps/) and `pins` [{label, x, y, tolerance?}] (1-10; x and y are 0-1 fractions of the map's viewBox,
    tolerance a 0.01-0.3 fraction, default 0.06). Graded when every label is dropped within its tolerance. Dropped
    for an unknown map, a coordinate outside 0-1, a missing or repeated label, or more than 10 pins."""
    if p.get("map") not in MAPS:
        return None
    pins = p.get("pins") if isinstance(p.get("pins"), list) else []
    if not 1 <= len(pins) <= 10:
        return None
    out = []
    for pin in pins:
        if not isinstance(pin, dict):
            return None
        label, x, y = _s(pin.get("label"), 80), _number(pin.get("x")), _number(pin.get("y"))
        if not label or x is None or y is None or not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        tol = _number(pin.get("tolerance"))
        out.append({"label": label, "x": round(x, 4), "y": round(y, 4),
                    "tolerance": min(0.3, max(0.01, tol)) if tol is not None else 0.06})
    if len({pin["label"] for pin in out}) != len(out):
        return None
    return {**base, "map": p["map"], "pins": out}


def _np_who_am_i(p, base):
    """Guess the figure (or place, or event) from clues. Fields: `clues` (3-6, hardest first; more are cut to 6),
    `answer`, `options` (3-5 distinct, including the answer). Clues are revealed one at a time; fewer clues used
    means more points (shown, not XP). Dropped when `answer` is not one of `options` or there are fewer than 3 clues."""
    clues = [_s(c, 300) for c in p.get("clues") or [] if _s(c, 300)] if isinstance(p.get("clues"), list) else []
    opts = [_s(o, 120) for o in p.get("options")] if isinstance(p.get("options"), list) else []
    answer = _s(p.get("answer"), 120)
    if len(clues) < 3 or not 3 <= len(opts) <= 5 or any(not o for o in opts) or len(set(opts)) != len(opts):
        return None
    if not answer or answer not in opts:
        return None
    return {**base, "clues": clues[:6], "answer": answer, "options": opts}


def _np_date_guess(p, base):
    """Guess the year of an event. Fields: `event` (what happened), `year` (a number, negative for BCE; whole
    years), `tolerance` (years either side that count as right, default 5, 0-500). The student gets up to 3 tries
    with earlier/later hints. Dropped when `event` is empty or `year` is not a number."""
    event = _s(p.get("event"), 200)
    year = _number(p.get("year"))
    if not event or year is None or abs(year) > 10000:
        return None
    tol = _number(p.get("tolerance"))
    return {**base, "event": event, "year": int(round(year)),
            "tolerance": int(round(min(500, max(0, tol)))) if tol is not None else 5}


def _np_roleplay(p, base):
    """Talk to a historical figure (the tutor's persona mode, /api/tutor/lesson with mode "persona"). Fields:
    `persona` (who the tutor plays), `era` (when and where), `goal` (what the student should find out) and
    `opening` (the figure's first line). Ungraded: done after 4 student turns. Dropped without persona or goal."""
    persona, goal = _s(p.get("persona"), 120), _s(p.get("goal"), 300)
    if not persona or not goal:
        return None
    return {**base, "persona": persona, "era": _s(p.get("era"), 80), "goal": goal, "opening": _s(p.get("opening"), 500)}


NORMALIZERS = {
    "categorize": _np_categorize, "cause_effect": _np_cause_effect, "source_analysis": _np_source_analysis,
    "map_pins": _np_map_pins, "who_am_i": _np_who_am_i, "date_guess": _np_date_guess, "roleplay": _np_roleplay,
}
