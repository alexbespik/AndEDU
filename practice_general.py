"""Practice types for Lab, Math and IDE classes: label_diagram, sort_by, odd_one_out, cloze and spot_the_bug.

Each normalizer takes (p, base): `p` is the raw item and `base` already holds {id, type, prompt, explanation, concept}.
It returns {**base, ...clean fields}, or None to drop the item. server.py merges NORMALIZERS into PRACTICE_NORMALIZERS
and GET /api/practice/guide shows the docstrings. Rendered by src/practice/general.jsx. Standard library only; never
imports server.py.
"""
import math
import re
from pathlib import Path

DIAGRAMS_DIR = Path(__file__).resolve().parent / "public" / "diagrams"
IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.svg$")  # same as server.DIAGRAM_NAME_RE
# Anything that could become active content if a renderer ever treated it as markup: dropped, never cleaned.
UNSAFE_RE = re.compile(r"<\s*script|\bon\w*\s*=|href", re.I)
HANDLER_KEY_RE = re.compile(r"^\s*on\w+", re.I)  # an event-handler attribute given as a key ("onclick": ...)

SVG_TONES = ("ink", "muted", "accent", "ok", "bad", "gold", "info")
SVG_ATTRS = {
    "rect": ("x", "y", "width", "height", "rx"),
    "circle": ("cx", "cy", "r"),
    "line": ("x1", "y1", "x2", "y2"),
    "text": ("x", "y", "size"),
}
SVG_MAX_SHAPES = 60
SVG_MAX_SIDE = 2000
CLOZE_GAP_RE = re.compile(r"\[\[([^\[\]]*)\]\]")


def _num(v):
    """A finite int/float (bools are not numbers here), else None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    v = float(v)
    return v if math.isfinite(v) else None


def _text(v, limit):
    return str(v).strip()[:limit] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def has_unsafe(value):
    """True if any string (key or value) anywhere inside `value` contains `<script`, an `on*=` handler or `href`,
    or a key names an event handler (on...)."""
    if isinstance(value, str):
        return bool(UNSAFE_RE.search(value))
    if isinstance(value, dict):
        return any(has_unsafe(k) or has_unsafe(v) or (isinstance(k, str) and HANDLER_KEY_RE.match(k)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(has_unsafe(v) for v in value)
    return False


def clean_svg_spec(spec):
    """Validates an svg_spec ({width, height, shapes: [...]}) and returns a whitelisted copy, or None."""
    if not isinstance(spec, dict) or has_unsafe(spec):
        return None
    w, h = _num(spec.get("width")), _num(spec.get("height"))
    if not w or not h or not (0 < w <= SVG_MAX_SIDE and 0 < h <= SVG_MAX_SIDE):
        return None
    raw = spec.get("shapes")
    if not isinstance(raw, list) or not 1 <= len(raw) <= SVG_MAX_SHAPES:
        return None
    shapes = []
    for s in raw:
        kind = s.get("kind") if isinstance(s, dict) else None
        if kind not in SVG_ATTRS:
            return None
        out = {"kind": kind}
        for attr in SVG_ATTRS[kind]:
            if attr in s:
                v = _num(s[attr])
                if v is None or abs(v) > 10 * SVG_MAX_SIDE:
                    return None
                out[attr] = v
        if kind == "text":
            out["text"] = _text(s.get("text"), 80)
            if not out["text"]:
                return None
        if s.get("tone") in SVG_TONES:
            out["tone"] = s["tone"]
        if kind in ("rect", "circle") and s.get("filled") is True:
            out["filled"] = True
        shapes.append(out)
    return {"width": w, "height": h, "shapes": shapes}


def _image_name(v):
    """A plain file name under public/diagrams/ (leading 'diagrams/' or '/diagrams/' is accepted), else None."""
    if not isinstance(v, str) or has_unsafe(v):
        return None
    name = re.sub(r"^/?(public/)?diagrams/", "", v.strip())
    if not IMAGE_RE.fullmatch(name):
        return None
    if DIAGRAMS_DIR.is_dir() and not (DIAGRAMS_DIR / name).is_file():
        return None  # a missing file would leave the student nothing to label
    return name


def np_label_diagram(p, base):
    """label_diagram: drag each label onto its spot on a diagram (correct within 0.06). Fields: `image` (a file name
    from GET /api/diagrams, e.g. "cell.svg") or `svg_spec` ({width, height, shapes: [{kind: rect|circle|line|text,
    numeric attrs (rect x y width height rx; circle cx cy r; line x1 y1 x2 y2; text x y size), text (text only),
    tone? ink|muted|accent|ok|bad|gold|info, filled? true}]}, at most 60 shapes; data only, never SVG markup), and
    `labels: [{text, x, y}]` (3-8, unique texts, x/y fractions 0-1 of the image). Dropped when: neither a valid image
    nor a valid svg_spec; an svg_spec string contains `<script`, an `on*=` handler or `href` (or a key starts with "on"); a shape kind or
    attribute is invalid; fewer than 3 or more than 8 labels; a coordinate is not a number in 0-1."""
    image = _image_name(p.get("image")) if p.get("image") else None
    spec = None
    if not image:
        if p.get("svg_spec") is None:
            return None
        spec = clean_svg_spec(p.get("svg_spec"))
        if not spec:
            return None
    raw = p.get("labels")
    if not isinstance(raw, list) or not 3 <= len(raw) <= 8:
        return None
    labels = []
    for lab in raw:
        if not isinstance(lab, dict):
            return None
        text, x, y = _text(lab.get("text"), 60), _num(lab.get("x")), _num(lab.get("y"))
        if not text or x is None or y is None or not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        labels.append({"text": text, "x": x, "y": y})
    if len({lab["text"] for lab in labels}) != len(labels):
        return None
    return {**base, "image": image, "svg_spec": spec, "labels": labels}


def np_sort_by(p, base):
    """sort_by: put items in order of a property, low to high; the values are revealed afterwards. Fields:
    `property` (e.g. "density", up to 60 chars), `items: [{text, value}]` (3-7, unique texts, distinct numeric
    values), `unit?` (shown with the values). Dropped when: no property; fewer than 3 or more than 7 items; a value is
    not a finite number (numeric strings are not accepted); two items share a text or a value."""
    prop = _text(p.get("property"), 60)
    raw = p.get("items")
    if not prop or not isinstance(raw, list) or not 3 <= len(raw) <= 7:
        return None
    items = []
    for it in raw:
        if not isinstance(it, dict):
            return None
        text, value = _text(it.get("text"), 120), _num(it.get("value"))
        if not text or value is None:
            return None
        items.append({"text": text, "value": value})
    if len({i["text"] for i in items}) != len(items) or len({i["value"] for i in items}) != len(items):
        return None
    return {**base, "property": prop, "items": items, "unit": _text(p.get("unit"), 30)}


def np_odd_one_out(p, base):
    """odd_one_out: pick the option that does not belong. Fields: `options` (exactly 4 unique non-empty strings),
    `answer` (one of the options), `why` (shown afterwards; defaults to the explanation). Dropped when: not exactly 4
    unique options, or `answer` is not one of them."""
    raw = p.get("options")
    if not isinstance(raw, list):
        return None
    opts = [_text(o, 160) for o in raw]
    ans = _text(p.get("answer"), 160)
    if len(opts) != 4 or not all(opts) or len(set(opts)) != 4 or ans not in opts:
        return None
    return {**base, "options": opts, "answer": ans, "why": _text(p.get("why"), 600) or base.get("explanation", "")}


def parse_cloze(text):
    """[[answer]] / [[answer|alt]] gaps in `text` -> list of answer lists, or None if a gap is empty or malformed."""
    gaps = []
    for m in CLOZE_GAP_RE.finditer(text):
        answers = [a.strip()[:80] for a in m.group(1).split("|") if a.strip()]
        if not answers:
            return None
        gaps.append(list(dict.fromkeys(answers))[:6])
    if "[[" in CLOZE_GAP_RE.sub("", text) or "]]" in CLOZE_GAP_RE.sub("", text):
        return None  # an unclosed or nested gap
    return gaps


def np_cloze(p, base):
    """cloze: fill each gap in a text, typed or tapped from a word bank; graded leniently like language answers.
    Fields: `text` (up to 2000 chars) with 1-6 gaps written [[answer]] or [[answer|alternative]], `bank?` (up to 12
    words; must contain the first answer of every gap). Dropped when: fewer than 1 or more than 6 gaps; a gap is empty;
    a `[[` or `]]` is unmatched or nested; a bank is given but misses a gap's answer."""
    text = p.get("text") if isinstance(p.get("text"), str) else ""
    if not text.strip() or len(text) > 2000:
        return None
    gaps = parse_cloze(text)
    if not gaps or not 1 <= len(gaps) <= 6:
        return None
    bank = []
    if p.get("bank") is not None:
        if not isinstance(p.get("bank"), list):
            return None
        bank = list(dict.fromkeys(w for w in (_text(b, 80) for b in p["bank"]) if w))[:12]
        if any(g[0] not in bank for g in gaps):
            return None
    return {**base, "text": text, "gaps": gaps, "bank": bank}


def np_spot_the_bug(p, base):
    """spot_the_bug: click the line with the bug, then optionally edit it and run the program in the browser
    (Pyodide). Fields: `code` (Python, up to 60 lines / 4000 chars), `language` ("python", the default),
    `bug_line` (1-based line number), `fix?` (the corrected version of that one line). Dropped when: no code; the
    language is not python; `bug_line` is not an integer within the code's line count or points at a blank line;
    `fix` spans more than one line."""
    code = p.get("code") if isinstance(p.get("code"), str) else ""
    code = code.strip("\n")
    lang = p.get("language") or "python"
    if not code.strip() or len(code) > 4000 or lang != "python":
        return None
    lines = code.split("\n")
    n = p.get("bug_line")
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= len(lines) <= 60 or not lines[n - 1].strip():
        return None
    fix = p.get("fix") if isinstance(p.get("fix"), str) else ""
    fix = fix.strip("\n")
    if "\n" in fix or len(fix) > 400:
        return None
    return {**base, "language": "python", "code": code, "bug_line": n, "fix": fix}


NORMALIZERS = {
    "label_diagram": np_label_diagram,
    "sort_by": np_sort_by,
    "odd_one_out": np_odd_one_out,
    "cloze": np_cloze,
    "spot_the_bug": np_spot_the_bug,
}

_np_label_diagram = np_label_diagram
_np_sort_by = np_sort_by
_np_odd_one_out = np_odd_one_out
_np_cloze = np_cloze
_np_spot_the_bug = np_spot_the_bug
