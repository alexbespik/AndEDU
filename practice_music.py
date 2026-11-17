"""
Music theory practice types: lint_satb_progression, roman_numeral_analysis, ear_interval_id, figured_bass_realize.
Exports NORMALIZERS, GRADERS, SECRET_FIELDS and PUBLIC_FIELDS (both per type).
Standard library only.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

# Fields the server keeps from the browser (stripped on every read; graders read them from the stored topic).
SECRET_FIELDS: Dict[str, Set[str]] = {
    "lint_satb_progression": {"expected_errors", "valid"},
    "roman_numeral_analysis": {"expected", "solution"},
    "ear_interval_id": {"semitones", "interval_name"},
    "figured_bass_realize": {"solution"},
}
# Fields a grader reads that the browser may see.
PUBLIC_FIELDS: Dict[str, Set[str]] = {t: set() for t in SECRET_FIELDS}

NOTE_TO_SEMITONE = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3,
    "E": 4, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8,
    "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11,
}
_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Interval names -> semitones. Full names are matched case-insensitively. "m" (minor) and "M" (major) differ only by
# case, so those abbreviations are matched case-sensitively; "maj2"/"min2" style spellings work in any case.
_FULL_NAMES = {
    "unison": 0, "perfect unison": 0, "minor second": 1, "major second": 2, "minor third": 3, "major third": 4,
    "perfect fourth": 5, "tritone": 6, "augmented fourth": 6, "diminished fifth": 6, "perfect fifth": 7,
    "minor sixth": 8, "major sixth": 9, "minor seventh": 10, "major seventh": 11, "octave": 12, "perfect octave": 12,
}
_ABBREV_CASE_SENSITIVE = {"m2": 1, "M2": 2, "m3": 3, "M3": 4, "m6": 8, "M6": 9, "m7": 10, "M7": 11}
_ABBREV_ANY_CASE = {
    "p1": 0, "p4": 5, "p5": 7, "p8": 12, "tt": 6, "a4": 6, "d5": 6,
    "min2": 1, "maj2": 2, "min3": 3, "maj3": 4, "min6": 8, "maj6": 9, "min7": 10, "maj7": 11,
}


def interval_semitones(name: Any) -> Optional[int]:
    """Semitones (0-12) for an interval name or abbreviation, or None when it is not one."""
    if not isinstance(name, str):
        return None
    raw = " ".join(name.split())
    if raw in _ABBREV_CASE_SENSITIVE:
        return _ABBREV_CASE_SENSITIVE[raw]
    low = raw.lower()
    if low in _FULL_NAMES:
        return _FULL_NAMES[low]
    return _ABBREV_ANY_CASE.get(low)


def _pitch_name(midi: int) -> str:
    return f"{_PITCH_NAMES[midi % 12]}{midi // 12 - 1}"


def _parse_pitch(pitch: Any) -> Optional[int]:
    if isinstance(pitch, int):
        return pitch
    if not isinstance(pitch, str):
        return None
    s = pitch.strip().upper()
    if not s:
        return None
    # e.g. "C4", "F#3", "Bb2"
    octave = 4
    if s[-1].isdigit():
        octave = int(s[-1])
        s = s[:-1]
    if s in NOTE_TO_SEMITONE:
        return 12 * (octave + 1) + NOTE_TO_SEMITONE[s]
    return None


def _lint_satb(chords: List[Dict[str, int]]) -> List[str]:
    """Runs deterministic voice leading check for SATB progression:
    - Voice crossing (S >= A >= T >= B)
    - Parallel fifths
    - Parallel octaves
    """
    errors: List[str] = []
    voices = ["s", "a", "t", "b"]

    # Check voice crossing within each chord
    for i, ch in enumerate(chords):
        s, a, t, b = ch["s"], ch["a"], ch["t"], ch["b"]
        if not (s >= a >= t >= b):
            errors.append(f"voice_crossing:chord_{i + 1}")

    # Check consecutive chords for parallel fifths and octaves
    pairs = [("s", "a"), ("s", "t"), ("s", "b"), ("a", "t"), ("a", "b"), ("t", "b")]
    for i in range(len(chords) - 1):
        c1, c2 = chords[i], chords[i + 1]
        for v1, v2 in pairs:
            # Check motion: both voices must move
            if c1[v1] != c2[v1] and c1[v2] != c2[v2]:
                int1 = abs(c1[v1] - c1[v2]) % 12
                int2 = abs(c2[v1] - c2[v2]) % 12
                if int1 == 7 and int2 == 7:
                    errors.append(f"parallel_fifth:{v1.upper()}_{v2.upper()}:chord_{i + 1}_to_{i + 2}")
                elif int1 == 0 and int2 == 0:
                    errors.append(f"parallel_octave:{v1.upper()}_{v2.upper()}:chord_{i + 1}_to_{i + 2}")
    return errors


# ---- 1. lint_satb_progression ----
def _np_lint_satb_progression(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """lint_satb_progression: find the voice-leading errors in a four-part progression.
    Fields: chords (2+ items, each {s,a,t,b} or [s,a,t,b]; pitches as names like "G4" or MIDI numbers).
    Secret (computed by the server): expected_errors, valid. Submit a list of error codes such as
    "voice_crossing:chord_2", "parallel_fifth:S_T:chord_1_to_2", "parallel_octave:A_B:chord_2_to_3" (voices S A T B),
    or [] / "valid" when the progression has no defect."""
    raw_chords = p.get("chords")
    if not isinstance(raw_chords, list) or len(raw_chords) < 2:
        return None
    parsed_chords: List[Dict[str, int]] = []
    for c in raw_chords:
        if isinstance(c, dict):
            s = _parse_pitch(c.get("s"))
            a = _parse_pitch(c.get("a"))
            t = _parse_pitch(c.get("t"))
            b = _parse_pitch(c.get("b"))
        elif isinstance(c, (list, tuple)) and len(c) == 4:
            s, a, t, b = [_parse_pitch(x) for x in c]
        else:
            return None
        if None in (s, a, t, b):
            return None
        parsed_chords.append({"s": s, "a": a, "t": t, "b": b})

    computed_errors = _lint_satb(parsed_chords)
    return {
        **base,
        "chords": raw_chords,
        "expected_errors": computed_errors,
        "valid": len(computed_errors) == 0,
    }


def _grade_lint_satb_progression(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = set(item.get("expected_errors", []))
    sub_errors: Set[str] = set()
    if isinstance(submission, list):
        for e in submission:
            sub_errors.add(str(e).strip())
    elif isinstance(submission, str):
        s = submission.strip()
        if s.lower() in ("valid", "none", "ok"):
            sub_errors = set()
        else:
            sub_errors.add(s)

    # If both expected and submitted agree on validity or specific errors
    if not expected and not sub_errors:
        return {"ok": True, "score": 1.0, "feedback": "Correct! SATB progression is voice-leading valid.", "details": {}}

    # Compare errors
    tp = len(expected & sub_errors)
    fp = len(sub_errors - expected)
    fn = len(expected - sub_errors)

    if fp == 0 and fn == 0:
        return {
            "ok": True,
            "score": 1.0,
            "feedback": f"Correctly identified all voice-leading defects ({', '.join(sorted(expected))}).",
            "details": {"errors": sorted(list(expected))},
        }

    score = max(0.0, round(tp / max(len(expected), 1) - 0.25 * fp, 2))
    return {
        "ok": False,
        "score": score,
        "feedback": "Not yet: recheck each voice pair for parallels, crossings and leaps.",
        "details": {"submitted": sorted(list(sub_errors))},
    }


# ---- 2. roman_numeral_analysis ----
def _np_roman_numeral_analysis(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """roman_numeral_analysis: label each chord with its Roman numeral in a key.
    Fields: key (text, default "C major"), chords (list of chord names or notes). Secret: expected (alias solution),
    one numeral per chord. Submit a list of numerals, one per chord."""
    key = str(p.get("key") or "C major")[:40]
    chords = p.get("chords") or []
    if not isinstance(chords, list) or not chords:
        return None
    raw_exp = p.get("expected") or p.get("solution")
    if not isinstance(raw_exp, list) or len(raw_exp) != len(chords):
        return None
    expected = [str(x).strip() for x in raw_exp]
    return {
        **base,
        "key": key,
        "chords": chords,
        "expected": expected,
    }


def _grade_roman_numeral_analysis(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("expected", [])
    if not isinstance(submission, list):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be a list of Roman numerals", "details": {}}
    sub = [str(x).strip() for x in submission]
    if len(sub) != len(expected):
        return {"ok": False, "score": 0.0, "feedback": "Give exactly one Roman numeral for each chord.", "details": {}}

    matches = sum(1 for e, s in zip(expected, sub) if e.lower() == s.lower())
    score = round(matches / len(expected), 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Flawless Roman numeral analysis!" if ok else "Not yet: recheck the root and quality of each chord.",
        "details": {"accuracy": score},
    }


# ---- 3. ear_interval_id ----
def _np_ear_interval_id(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """ear_interval_id: hear two pitches and name the interval.
    Fields: notes (two pitches like ["C4", "E4"]; the browser plays them with WebAudio), mode ("melodic" default, or
    "harmonic" to sound them together). The author gives notes, or semitones (0-24) / interval_name, or both; they
    must agree. When only semitones/interval_name are given the server writes notes upward from C4.
    Secret: semitones, interval_name (the notes themselves are public, they are what the ear hears).
    Submit an interval name ("major third", "M3", "maj3"; "m3"/"min3" is the minor third, case matters for m/M)
    or the number of semitones."""
    semitones = p.get("semitones")
    if isinstance(semitones, bool):
        return None
    if semitones is not None:
        try:
            semitones = int(semitones)
        except (ValueError, TypeError):
            return None
    named = interval_semitones(str(p.get("interval_name") or p.get("name") or ""))
    if p.get("interval_name") or p.get("name"):
        if named is None:
            return None
        if semitones is None:
            semitones = named
        elif semitones % 12 != named % 12 or (semitones != named and semitones != named + 12):
            return None  # the name and the count disagree
    raw_notes = p.get("notes")
    notes: List[str] = []
    if isinstance(raw_notes, list) and len(raw_notes) == 2:
        pitches = [_parse_pitch(n) for n in raw_notes]
        if None in pitches:
            return None
        notes = [str(n).strip()[:8] if isinstance(n, str) else _pitch_name(int(n)) for n in raw_notes]
        diff = abs(pitches[1] - pitches[0])
        if semitones is not None and semitones != diff:
            return None
        semitones = diff
    elif raw_notes:
        return None
    if semitones is None or not (0 <= semitones <= 24):
        return None
    if not notes:
        notes = ["C4", _pitch_name(60 + semitones)]
    name = next((n for n, st in _FULL_NAMES.items() if st == semitones % 12 or (semitones == 12 and st == 12)), "interval")
    if semitones == 12:
        name = "octave"
    mode = "harmonic" if str(p.get("mode") or "").lower() == "harmonic" else "melodic"
    return {
        **base,
        "semitones": int(semitones),
        "interval_name": name,
        "notes": notes,
        "mode": mode,
    }


def _grade_ear_interval_id(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    st_exp = item.get("semitones")
    exp_simple = st_exp if st_exp <= 12 else st_exp - 12
    if isinstance(submission, bool):
        return {"ok": False, "score": 0.0, "feedback": "Name the interval or give its size in semitones.", "details": {}}
    named: Optional[int] = None
    if isinstance(submission, (int, float)):
        named = int(submission)
    elif isinstance(submission, str):
        text = submission.strip()
        if text.lstrip("-").isdigit():
            named = int(text)
        else:
            named = interval_semitones(text)
    ok = named is not None and (named == st_exp or named == exp_simple)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Correct interval identification: {item.get('interval_name')}." if ok else "Incorrect interval identification.",
        "details": {} if ok else {"submitted": submission if isinstance(submission, (str, int, float)) else None},
    }


# ---- 4. figured_bass_realize ----
def _np_figured_bass_realize(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """figured_bass_realize: write the upper voices that a figured bass calls for.
    Fields: bass_note (pitch like "C3"), figures (text such as "6" or "6/4"). Secret: solution (alias realization),
    the list of upper-voice pitches. Submit a list of pitches (order does not matter; enharmonic spellings such as C#4 and Db4 count as equal)."""
    bass = p.get("bass_note")
    figures = str(p.get("figures") or "").strip()
    solution = p.get("solution") or p.get("realization")
    if bass is None or not figures or not isinstance(solution, list):
        return None
    return {
        **base,
        "bass_note": bass,
        "figures": figures,
        "solution": [str(x).strip() for x in solution],
    }


def _grade_figured_bass_realize(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    def key(x: Any) -> Any:  # enharmonic spellings (C#4, Db4) are the same pitch
        m = _parse_pitch(str(x).strip())
        return m if m is not None else str(x).strip().upper()

    expected = [key(x) for x in item.get("solution", [])]
    if not isinstance(submission, list):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be a list of realized voices", "details": {}}
    sub = [key(x) for x in submission]
    ok = (sorted(map(str, sub)) == sorted(map(str, expected)))
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Figured bass correctly realized!" if ok else "Incorrect upper voice realization.",
        "details": {},
    }


NORMALIZERS = {
    "lint_satb_progression": _np_lint_satb_progression,
    "roman_numeral_analysis": _np_roman_numeral_analysis,
    "ear_interval_id": _np_ear_interval_id,
    "figured_bass_realize": _np_figured_bass_realize,
}

GRADERS = {
    "lint_satb_progression": _grade_lint_satb_progression,
    "roman_numeral_analysis": _grade_roman_numeral_analysis,
    "ear_interval_id": _grade_ear_interval_id,
    "figured_bass_realize": _grade_figured_bass_realize,
}
