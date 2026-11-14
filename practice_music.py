"""
Music theory practice types: lint_satb_progression, roman_numeral_analysis, ear_interval_id, figured_bass_realize.
Exports NORMALIZERS, GRADERS, and SECRET_FIELDS.
Standard library only.
"""
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"expected", "solution", "expected_errors", "semitones", "interval_name"}

NOTE_TO_SEMITONE = {
    "C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3,
    "E": 4, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8,
    "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11,
}

INTERVAL_NAMES = {
    0: {"unison", "p1", "perfect unison"},
    1: {"minor second", "m2"},
    2: {"major second", "m2", "maj2"},
    3: {"minor third", "m3"},
    4: {"major third", "m3", "maj3"},
    5: {"perfect fourth", "p4"},
    6: {"tritone", "augmented fourth", "diminished fifth", "tt", "a4", "d5"},
    7: {"perfect fifth", "p5"},
    8: {"minor sixth", "m6"},
    9: {"major sixth", "m6", "maj6"},
    10: {"minor seventh", "m7"},
    11: {"major seventh", "m7", "maj7"},
    12: {"octave", "p8", "perfect octave"},
}


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
        "feedback": f"Detected {tp}/{len(expected)} voice-leading errors.",
        "details": {"submitted": sorted(list(sub_errors)), "true_errors": sorted(list(expected))},
    }


# ---- 2. roman_numeral_analysis ----
def _np_roman_numeral_analysis(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        return {"ok": False, "score": 0.0, "feedback": f"Expected {len(expected)} numerals, got {len(sub)}.", "details": {}}

    matches = sum(1 for e, s in zip(expected, sub) if e.lower() == s.lower())
    score = round(matches / len(expected), 2)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Flawless Roman numeral analysis!" if ok else f"Correct on {matches}/{len(expected)} chords.",
        "details": {"accuracy": score},
    }


# ---- 3. ear_interval_id ----
def _np_ear_interval_id(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    semitones = p.get("semitones")
    name = str(p.get("interval_name") or p.get("name") or "").strip().lower()
    if semitones is None and name:
        for st, aliases in INTERVAL_NAMES.items():
            if name in aliases:
                semitones = st
                break
    if semitones is None:
        notes = p.get("notes") or []
        if len(notes) == 2:
            p1 = _parse_pitch(notes[0])
            p2 = _parse_pitch(notes[1])
            if p1 is not None and p2 is not None:
                semitones = abs(p2 - p1)
    if semitones is None or not (0 <= semitones <= 24):
        return None
    if not name:
        name = next(iter(INTERVAL_NAMES.get(semitones % 12, {"unknown"})))

    return {
        **base,
        "semitones": int(semitones),
        "interval_name": name,
        "notes": p.get("notes") or [],
    }


def _grade_ear_interval_id(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    st_exp = item.get("semitones")
    aliases = INTERVAL_NAMES.get(st_exp % 12, set()) | {str(st_exp)}

    sub_str = str(submission or "").strip().lower()
    try:
        sub_st = int(submission)
        if sub_st == st_exp:
            return {"ok": True, "score": 1.0, "feedback": f"Correct! {st_exp} semitones.", "details": {}}
    except (ValueError, TypeError):
        pass

    if sub_str in aliases:
        return {
            "ok": True,
            "score": 1.0,
            "feedback": f"Correct interval identification: {item.get('interval_name')}.",
            "details": {},
        }
    return {
        "ok": False,
        "score": 0.0,
        "feedback": "Incorrect interval identification.",
        "details": {"submitted": submission},
    }


# ---- 4. figured_bass_realize ----
def _np_figured_bass_realize(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
    expected = [str(x).strip().upper() for x in item.get("solution", [])]
    if not isinstance(submission, list):
        return {"ok": False, "score": 0.0, "feedback": "Submission must be a list of realized voices", "details": {}}
    sub = [str(x).strip().upper() for x in submission]
    ok = (sorted(sub) == sorted(expected))
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Figured bass correctly realized!" if ok else "Incorrect upper voice realization.",
        "details": {"submitted": sub},
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
