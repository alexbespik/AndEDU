"""Normalizers for the extra language practice types: story, dialogue, conjugate, script_match.

Merged into server.PRACTICE_NORMALIZERS. Each fn(p, base) returns {**base, ...clean fields} or None to drop the item;
`base` already holds {id, type, prompt, explanation, concept}. Standard library only, never imports server.py.
Rendered by src/practice/language_extra.jsx; typed answers are graded in the browser by src/lib/langgrade.js.
"""
import re

LANG_RE = re.compile(r"[a-z]{2,3}(-[A-Za-z]{2,4})?")  # same as server.LANG_RE (used with fullmatch)

SCRIPTS = ("hiragana", "katakana", "cyrillic", "hangul", "greek", "arabic", "devanagari")
SCRIPT_LANG = {"hiragana": "ja", "katakana": "ja", "cyrillic": "ru", "hangul": "ko", "greek": "el", "arabic": "ar", "devanagari": "hi"}


def _lang(value):
    value = str(value or "")
    return value if LANG_RE.fullmatch(value) else None


def _s(value, limit):
    return str(value if value is not None else "").strip()[:limit]


def _np_story(p, base):
    """Story read aloud line by line, each speaker in their own voice, with questions inline.
    Fields: title (<=120 chars), lang (BCP-47, required), lines [{speaker, text, translation?}] (4-16; extra lines are
    cut), questions [{after: line index, question, options (2-6, unique), answer}] (at most 8). A line needs text;
    a question is dropped when `after` is not a line index or `answer` is not one of `options`. The item is dropped
    without a valid lang, with fewer than 4 lines, or with no valid question left."""
    lang = _lang(p.get("lang"))
    lines = []
    for ln in p.get("lines") or []:
        if isinstance(ln, dict) and _s(ln.get("text"), 300):
            line = {"speaker": _s(ln.get("speaker"), 40), "text": _s(ln.get("text"), 300)}
            if _s(ln.get("translation"), 300):
                line["translation"] = _s(ln.get("translation"), 300)
            lines.append(line)
    lines = lines[:16]
    if not lang or len(lines) < 4:
        return None
    questions = []
    for qn in p.get("questions") or []:
        if not isinstance(qn, dict):
            continue
        after = qn.get("after")
        if isinstance(after, bool) or not isinstance(after, (int, float)) or int(after) != after or not 0 <= after < len(lines):
            continue
        opts = [_s(o, 200) for o in qn.get("options") or [] if _s(o, 200)]
        ans = _s(qn.get("answer"), 200)
        if _s(qn.get("question"), 300) and ans in opts and 2 <= len(opts) <= 6 and len(set(opts)) == len(opts):
            questions.append({"after": int(after), "question": _s(qn.get("question"), 300), "options": opts, "answer": ans})
    if not questions:
        return None
    return {**base, "title": _s(p.get("title"), 120), "lang": lang, "lines": lines, "questions": sorted(questions[:8], key=lambda x: x["after"])}


def _np_dialogue(p, base):
    """AI roleplay with a persona (POST /api/language/roleplay); ungraded, ends after the goal or 6 turns with a recap.
    Fields: persona (who the partner is, <=80), setting (where, <=200), goal (what the student must do, <=200),
    lang (BCP-47), level (CEFR such as A1-C2, <=10, default A2). Dropped when persona, setting or goal is empty or
    lang is not a language code."""
    persona, setting, goal, lang = _s(p.get("persona"), 80), _s(p.get("setting"), 200), _s(p.get("goal"), 200), _lang(p.get("lang"))
    if persona and setting and goal and lang:
        return {**base, "persona": persona, "setting": setting, "goal": goal, "lang": lang, "level": _s(p.get("level"), 10) or "A2"}


def _np_conjugate(p, base):
    """Conjugation table: type each form, graded leniently in the browser (accents and typos noted).
    Fields: verb (<=60), tense (<=60), lang (BCP-47), forms [[pronoun, form], ...] (3-8 pairs, pronouns unique;
    {pronoun, form} objects are accepted too). Dropped when verb, tense or lang is missing, a pair has an empty side,
    or the number of forms is outside 3-8."""
    verb, tense, lang = _s(p.get("verb"), 60), _s(p.get("tense"), 60), _lang(p.get("lang"))
    raw = p.get("forms") or []
    if not verb or not tense or not lang or not isinstance(raw, list):
        return None
    forms = []
    for f in raw:
        if isinstance(f, dict):
            f = [f.get("pronoun"), f.get("form")]
        if not isinstance(f, (list, tuple)) or len(f) != 2:
            return None
        pronoun, form = _s(f[0], 40), _s(f[1], 80)
        if not pronoun or not form:
            return None
        forms.append([pronoun, form])
    if 3 <= len(forms) <= 8 and len({pr for pr, _ in forms}) == len(forms):
        return {**base, "verb": verb, "tense": tense, "lang": lang, "forms": forms}


def _np_script_match(p, base):
    """Match glyphs of a writing system to their romanization; each glyph is read aloud when tapped.
    Fields: script (hiragana | katakana | cyrillic | hangul | greek | arabic | devanagari), pairs [[glyph, romanization]]
    (4-10, glyphs <=8 chars, both sides unique), lang (optional BCP-47; defaults to the script's usual language).
    Dropped for any other script, a malformed or empty pair, duplicates, or a pair count outside 4-10."""
    script = p.get("script")
    raw = p.get("pairs") or []
    if script not in SCRIPTS or not isinstance(raw, list):
        return None
    pairs = []
    for pr in raw:
        if not isinstance(pr, (list, tuple)) or len(pr) != 2:
            return None
        glyph, roman = _s(pr[0], 8), _s(pr[1], 24)
        if not glyph or not roman:
            return None
        pairs.append([glyph, roman])
    if 4 <= len(pairs) <= 10 and len({g for g, _ in pairs}) == len(pairs) and len({r for _, r in pairs}) == len(pairs):
        return {**base, "script": script, "pairs": pairs, "lang": _lang(p.get("lang")) or SCRIPT_LANG[script]}


NORMALIZERS = {"story": _np_story, "dialogue": _np_dialogue, "conjugate": _np_conjugate, "script_match": _np_script_match}
