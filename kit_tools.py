"""Deterministic desks for the liberal-arts kits (docs/plans/KIT_TOOLS_CONTRACT.md).

Stdlib only, no model calls, no network. `run(kind, op, args)` never raises: it answers {"ok": True, "result": ...} or
{"ok": False, "error": {"code", "message", "at"?}}. Domain outcomes (a cycle, an unbalanced bracket, a form mismatch)
are results, not errors. Floats are rounded to 4 places; exact values are fraction strings such as "7/30".
art_history has no server ops (its composition HUD runs in the browser). The STEM kits (ee, ai, systems, stats, bio;
docs/plans/STEM_KIT_TOOLS_CONTRACT.md) follow the same rules; their size caps answer too_large or too_complex."""
import heapq
import inspect
import json
import math
import re
import unicodedata
from fractions import Fraction
from typing import Any, Callable, Dict, List, Optional, Tuple

import practice_bio
import practice_classics
import practice_music
import practice_polity
import practice_systems

# The contract says 20_000, but its own caps (650 districts x 30 parties, 500 ballot groups) need far more room.
MAX_ARGS_BYTES = 500_000


class ToolError(ValueError):
    def __init__(self, code: str, message: str, at: Optional[str] = None):
        super().__init__(message)
        self.code, self.message, self.at = code, message, at

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.at:
            d["at"] = self.at
        return d


def _bad(message: str, at: Optional[str] = None) -> ToolError:
    return ToolError("bad_args", message, at)


def _r4(x: float) -> float:
    return round(float(x), 4) + 0.0


def _int(v: Any, lo: int, hi: int, at: str) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _bad(f"{at} must be a whole number.", at)
    if isinstance(v, float) and (not math.isfinite(v) or v != int(v)):
        raise _bad(f"{at} must be a whole number.", at)
    n = int(v)
    if n < lo or n > hi:
        raise _bad(f"{at} must be between {lo} and {hi}.", at)
    return n


def _name(v: Any, at: str, limit: int = 60) -> str:
    if not isinstance(v, str) or not v.strip():
        raise _bad(f"{at} must be a non-empty text.", at)
    if len(v) > limit:
        raise _bad(f"{at} is longer than {limit} characters.", at)
    return v


def _list(v: Any, at: str, lo: int, hi: int) -> list:
    if not isinstance(v, list):
        raise _bad(f"{at} must be a list.", at)
    if len(v) < lo or len(v) > hi:
        raise _bad(f"{at} needs {lo} to {hi} items.", at)
    return v


def _dict(v: Any, at: str) -> dict:
    if not isinstance(v, dict):
        raise _bad(f"{at} must be an object.", at)
    return v


def _text(v: Any, at: str, limit: int, required: bool = False) -> str:
    if v is None and not required:
        return ""
    if not isinstance(v, str):
        raise _bad(f"{at} must be text.", at)
    if len(v) > limit:
        raise _bad(f"{at} is longer than {limit} characters.", at)
    return v


def _frac(x: Fraction) -> str:
    return str(x)


# ===================================================================== polity
def _count_map(raw: Any, at: str) -> Dict[str, int]:
    raw = _dict(raw, at)
    if not raw or len(raw) > 30:
        raise _bad(f"{at} needs 1 to 30 parties.", at)
    return {_name(k, f"{at}.{k}"): _int(v, 0, 10 ** 9, f"{at}.{k}") for k, v in raw.items()}


def _pick(candidates: Dict[str, Fraction], votes: Dict[str, int]) -> str:
    """Highest value; ties go to the higher total vote, then the alphabetically first name."""
    return min(candidates, key=lambda p: (-candidates[p], -votes.get(p, 0), p))


def _polity_allocate(a: Dict[str, Any]) -> Dict[str, Any]:
    """allocate {method: dhondt|sainte_lague|fptp, seats, votes: {party: int}}; fptp takes districts: [{party: int}]
    instead of votes and seats = len(districts). Caps: 30 parties, seats 1..650, 650 districts, each count 0..1e9.
    Ties: higher total vote, then alphabetical. Result: {seats: {party: int}, rounds: [{seat, party, quotient}]
    (fptp: quotient is the winner's district vote), shares: {party: {votes_pct, seats_pct}}, gallagher}."""
    method = a.get("method")
    if method not in ("dhondt", "sainte_lague", "fptp"):
        raise _bad("method must be dhondt, sainte_lague or fptp.", "method")
    rounds: List[Dict[str, Any]] = []
    if method == "fptp":
        districts = _list(a.get("districts"), "districts", 1, 650)
        parsed = [_count_map(d, f"districts.{i}") for i, d in enumerate(districts)]
        votes: Dict[str, int] = {}
        for d in parsed:
            for p, v in d.items():
                votes[p] = votes.get(p, 0) + v
        if len(votes) > 30:
            raise _bad("districts name more than 30 parties.", "districts")
        seats = {p: 0 for p in votes}
        for i, d in enumerate(parsed):
            win = _pick({p: Fraction(v) for p, v in d.items()}, votes)
            seats[win] += 1
            rounds.append({"seat": i + 1, "party": win, "quotient": d[win]})
        n_seats = len(parsed)
    else:
        n_seats = _int(a.get("seats"), 1, 650, "seats")
        votes = _count_map(a.get("votes"), "votes")
        seats = {p: 0 for p in votes}
        step = 1 if method == "dhondt" else 2  # divisor: s+1 or 2s+1
        for k in range(n_seats):
            quotients = {p: Fraction(v, step * seats[p] + 1) for p, v in votes.items()}
            win = _pick(quotients, votes)
            rounds.append({"seat": k + 1, "party": win, "quotient": _r4(quotients[win])})
            seats[win] += 1
    total_v = sum(votes.values())
    shares = {}
    gall = 0.0
    for p in sorted(votes):
        vp = 100.0 * votes[p] / total_v if total_v else 0.0
        sp = 100.0 * seats[p] / n_seats
        shares[p] = {"votes_pct": _r4(vp), "seats_pct": _r4(sp)}
        gall += (vp - sp) ** 2
    return {"seats": seats, "rounds": rounds, "shares": shares, "gallagher": _r4(math.sqrt(gall / 2))}


def _ballots(a: Dict[str, Any]) -> Tuple[List[str], List[Tuple[List[str], int]]]:
    cands = [_name(c, f"candidates.{i}") for i, c in enumerate(_list(a.get("candidates"), "candidates", 1, 20))]
    if len(set(cands)) != len(cands):
        raise _bad("candidates must be different names.", "candidates")
    known = set(cands)
    groups = _list(a.get("ballots"), "ballots", 1, 500)
    out: List[Tuple[List[str], int]] = []
    total = 0
    for i, g in enumerate(groups):
        g = _dict(g, f"ballots.{i}")
        ranking = _list(g.get("ranking"), f"ballots.{i}.ranking", 0, 20)
        seen: List[str] = []
        for j, c in enumerate(ranking):
            if not isinstance(c, str) or c not in known:
                raise _bad("ranking names a candidate that is not in candidates.", f"ballots.{i}.ranking.{j}")
            if c not in seen:
                seen.append(c)
        count = _int(g.get("count", 1), 1, 10 ** 6, f"ballots.{i}.count")
        total += count
        out.append((seen, count))
    if total > 10 ** 6:
        raise _bad("The ballot counts add up to more than 1,000,000.", "ballots")
    return cands, out


def _polity_stv(a: Dict[str, Any]) -> Dict[str, Any]:
    """stv {candidates: [str], ballots: [{ranking: [str], count: int}], seats}. Droop quota floor(valid/(seats+1))+1;
    a winner's surplus moves on by Weighted Inclusive Gregory (exact fractions); with no one at quota the lowest
    candidate is excluded; when as many candidates remain as seats open they are all elected. Ties: highest tally
    wins, lowest is excluded, alphabetical. Caps: 20 candidates, 500 ballot groups, 1e6 ballots, seats 1..10 (not
    above the candidates). Result: {quota, elected: [str], rounds: [{tally: {c: "7/30"}, action: elect|exclude, who}]}."""
    cands, groups = _ballots(a)
    seats = _int(a.get("seats"), 1, 10, "seats")
    if seats > len(cands):
        raise _bad("seats is more than the number of candidates.", "seats")
    valid = sum(n for r, n in groups if r)
    quota = valid // (seats + 1) + 1
    elected: List[str] = []
    rounds: List[Dict[str, Any]] = []
    if valid == 0:
        return {"quota": quota, "elected": elected, "rounds": rounds}
    weight = [Fraction(1)] * len(groups)
    continuing = list(cands)
    while len(elected) < seats and continuing:
        tally = {c: Fraction(0) for c in continuing}
        top: List[Optional[str]] = []
        for gi, (rank, n) in enumerate(groups):
            t = next((c for c in rank if c in tally), None)
            top.append(t)
            if t is not None:
                tally[t] += weight[gi] * n
        snap = {c: _frac(tally[c]) for c in cands if c in tally}
        best = min(continuing, key=lambda c: (-tally[c], c))
        if tally[best] >= quota:
            factor = (tally[best] - quota) / tally[best]
            for gi, t in enumerate(top):
                if t == best:
                    weight[gi] *= factor
            elected.append(best)
            rounds.append({"tally": snap, "action": "elect", "who": best})
            continuing.remove(best)
        elif len(continuing) <= seats - len(elected):
            elected.append(best)
            rounds.append({"tally": snap, "action": "elect", "who": best})
            continuing.remove(best)
        else:
            low = min(continuing, key=lambda c: (tally[c], c))
            rounds.append({"tally": snap, "action": "exclude", "who": low})
            continuing.remove(low)
    return {"quota": quota, "elected": elected, "rounds": rounds}


def _polity_irv(a: Dict[str, Any]) -> Dict[str, Any]:
    """irv {candidates: [str], ballots: [{ranking: [str], count: int}]}: instant-runoff count, same rules as the
    practice type (a tie for last drops the alphabetically first; a tie in the final two goes to the alphabetically
    first; no ballots left means winner ""). Caps as stv. Result: {rounds: [{candidate: int}], eliminated: [str],
    winner}."""
    cands, groups = _ballots(a)
    active = list(cands)
    eliminated: List[str] = []
    rounds: List[Dict[str, int]] = []
    while active:
        tally = {c: 0 for c in active}
        valid = 0
        for rank, n in groups:
            t = next((c for c in rank if c in tally), None)
            if t is not None:
                tally[t] += n
                valid += n
        rounds.append(dict(tally))
        if valid == 0:
            return {"rounds": rounds, "eliminated": eliminated, "winner": ""}
        for c in active:
            if tally[c] * 2 > valid:
                return {"rounds": rounds, "eliminated": eliminated, "winner": c}
        if len(active) <= 2:
            top = max(tally.values())
            return {"rounds": rounds, "eliminated": eliminated, "winner": sorted(c for c in active if tally[c] == top)[0]}
        low = min(tally.values())
        out = sorted(c for c in active if tally[c] == low)[0]
        active.remove(out)
        eliminated.append(out)
    return {"rounds": rounds, "eliminated": eliminated, "winner": ""}


def _polity_power(a: Dict[str, Any]) -> Dict[str, Any]:
    """power {weights: {player: int}, quota?}: Shapley-Shubik and Banzhaf power by subset enumeration. 2..15 players,
    weights 0..10000, quota 1..sum (default sum//2+1). A swing is a coalition that wins only with that player.
    Result: {quota, shapley_shubik: {p: {exact: "1/3", value}}, banzhaf: {p: {swings, normalized}},
    minimal_winning: [[p...]] (at most 200, sorted by size then names), truncated, dummies: [p] (no swings)}."""
    raw = _dict(a.get("weights"), "weights")
    if len(raw) < 2 or len(raw) > 15:
        raise _bad("weights needs 2 to 15 players.", "weights")
    players = sorted(_name(k, f"weights.{k}") for k in raw)
    w = [_int(raw[p], 0, 10000, f"weights.{p}") for p in players]
    total = sum(w)
    if total < 1:
        raise _bad("The weights must add up to at least 1.", "weights")
    quota = _int(a["quota"], 1, total, "quota") if a.get("quota") is not None else total // 2 + 1
    n = len(players)
    sums = [0] * (1 << n)
    for mask in range(1, 1 << n):
        low = mask & -mask
        sums[mask] = sums[mask ^ low] + w[low.bit_length() - 1]
    swings = [0] * n
    sizes = [[0] * n for _ in range(n)]  # sizes[i][s]: swing coalitions of size s (without i)
    minimal: List[List[str]] = []
    for mask in range(1, 1 << n):
        s = sums[mask]
        if s < quota:
            continue
        members = [i for i in range(n) if mask >> i & 1]
        critical = [i for i in members if s - w[i] < quota]
        for i in critical:
            swings[i] += 1
            sizes[i][len(members) - 1] += 1
        if len(critical) == len(members):
            minimal.append([players[i] for i in members])
    fact = [math.factorial(k) for k in range(n + 1)]
    ss = {}
    for i, p in enumerate(players):
        x = sum(Fraction(c * fact[s] * fact[n - s - 1], fact[n]) for s, c in enumerate(sizes[i]) if c)
        ss[p] = {"exact": _frac(x), "value": _r4(x)}
    tot_sw = sum(swings)
    bz = {p: {"swings": swings[i], "normalized": _r4(swings[i] / tot_sw) if tot_sw else 0.0} for i, p in enumerate(players)}
    minimal.sort(key=lambda m: (len(m), m))
    return {"quota": quota, "shapley_shubik": ss, "banzhaf": bz, "minimal_winning": minimal[:200],
            "truncated": len(minimal) > 200, "dummies": [p for i, p in enumerate(players) if swings[i] == 0]}


# ===================================================================== music
_VOICES = ("s", "a", "t", "b")
_RANGES = {"s": (60, 79), "a": (55, 74), "t": (48, 67), "b": (40, 60)}  # S C4-G5, A G3-D5, T C3-G4, B E2-C4
_RULE_RANK = {"voice_crossing": 0, "parallel_fifth": 1, "parallel_octave": 2, "spacing": 3, "range": 4}


def _music_lint(a: Dict[str, Any]) -> Dict[str, Any]:
    """lint {chords: [{s, a, t, b}]}: pitch names ("F#3") or MIDI numbers 21..108; 2..32 chords. Checks voice
    crossing, parallel fifths and octaves (the practice type's own rules), spacing (S-A or A-T wider than an octave)
    and range (S C4-G5, A G3-D5, T C3-G4, B E2-C4). Chord positions in `at` are 0-based. Result: {issues: [{rule,
    voices: [str], at: [int]}], clean}; rule is voice_crossing|parallel_fifth|parallel_octave|spacing|range."""
    chords_raw = _list(a.get("chords"), "chords", 2, 32)
    chords: List[Dict[str, int]] = []
    for i, c in enumerate(chords_raw):
        c = _dict(c, f"chords.{i}")
        ch: Dict[str, int] = {}
        for v in _VOICES:
            raw = c.get(v)
            at = f"chords.{i}.{v}"
            if isinstance(raw, bool) or not isinstance(raw, (int, str)):
                raise _bad("Give a pitch name like F#3 or a MIDI number.", at)
            m = practice_music._parse_pitch(raw)
            if m is None or m < 21 or m > 108:
                raise _bad("Give a pitch name like F#3 or a MIDI number 21..108.", at)
            ch[v] = m
        chords.append(ch)
    issues: List[Dict[str, Any]] = []
    for code in practice_music._lint_satb(chords):
        parts = code.split(":")
        if parts[0] == "voice_crossing":
            i = int(parts[1].split("_")[1]) - 1
            ch = chords[i]
            names: List[str] = []
            for hi, lo in (("s", "a"), ("a", "t"), ("t", "b")):
                if ch[hi] < ch[lo]:
                    for v in (hi, lo):
                        if v.upper() not in names:
                            names.append(v.upper())
            if not names:  # only a non-adjacent inversion is impossible when the adjacent pairs hold
                names = ["S", "B"]
            issues.append({"rule": "voice_crossing", "voices": names, "at": [i]})
        else:
            i = int(parts[2].split("_")[1]) - 1
            issues.append({"rule": parts[0], "voices": parts[1].split("_"), "at": [i, i + 1]})
    for i, ch in enumerate(chords):
        if ch["s"] - ch["a"] > 12:
            issues.append({"rule": "spacing", "voices": ["S", "A"], "at": [i]})
        if ch["a"] - ch["t"] > 12:
            issues.append({"rule": "spacing", "voices": ["A", "T"], "at": [i]})
        for v in _VOICES:
            lo, hi = _RANGES[v]
            if ch[v] < lo or ch[v] > hi:
                issues.append({"rule": "range", "voices": [v.upper()], "at": [i]})
    issues.sort(key=lambda x: (x["at"][0], _RULE_RANK[x["rule"]], x["voices"]))
    return {"issues": issues, "clean": not issues}


_JUST = ["1/1", "16/15", "9/8", "6/5", "5/4", "4/3", "45/32", "3/2", "8/5", "5/3", "9/5", "15/8", "2/1"]
_PYTH = ["1/1", "256/243", "9/8", "32/27", "81/64", "4/3", "729/512", "3/2", "128/81", "27/16", "16/9", "243/128", "2/1"]
_INTERVALS = ["unison", "minor second", "major second", "minor third", "major third", "perfect fourth", "tritone",
              "perfect fifth", "minor sixth", "major sixth", "minor seventh", "major seventh", "octave"]
_SYSTEMS = ("equal", "just", "pythagorean")


def _music_tuning(a: Dict[str, Any]) -> Dict[str, Any]:
    """tuning {root_hz = 261.63, systems = [equal, just, pythagorean], semitones = [0..12]}: root 20..2000 Hz, at most
    13 intervals of 0..12 semitones. Just is 5-limit, Pythagorean is built from 3:2 fifths, equal is 2^(n/12).
    Result: {rows: [{semitones, name, systems: {sys: {ratio, hz, cents, vs_equal_cents, beat_hz}}}]}; ratio is a
    fraction string for just/pythagorean and a number for equal; beat_hz = |q*f_upper - p*f_root| for the just ratio
    p/q (0 for just itself). The browser makes the sound; the server only computes."""
    root = a.get("root_hz", 261.63)
    if isinstance(root, bool) or not isinstance(root, (int, float)) or not 20 <= root <= 2000:
        raise _bad("root_hz must be a number from 20 to 2000.", "root_hz")
    systems = a.get("systems", list(_SYSTEMS))
    systems = _list(systems, "systems", 1, 3)
    for i, s in enumerate(systems):
        if s not in _SYSTEMS:
            raise _bad("systems are equal, just or pythagorean.", f"systems.{i}")
    semis = [_int(s, 0, 12, f"semitones.{i}") for i, s in enumerate(_list(a.get("semitones", list(range(13))), "semitones", 1, 13))]
    rows = []
    for n in semis:
        jp, jq = (int(x) for x in _JUST[n].split("/"))
        per: Dict[str, Any] = {}
        for sysname in dict.fromkeys(systems):
            if sysname == "equal":
                ratio_val, ratio = 2 ** (n / 12), _r4(2 ** (n / 12))
            else:
                fr = Fraction(_JUST[n] if sysname == "just" else _PYTH[n])
                ratio_val, ratio = float(fr), _frac(fr)
            hz = root * ratio_val
            cents = 1200 * math.log2(ratio_val)
            per[sysname] = {"ratio": ratio, "hz": _r4(hz), "cents": _r4(cents), "vs_equal_cents": _r4(cents - 100 * n),
                            "beat_hz": _r4(abs(jq * hz - jp * root))}
        rows.append({"semitones": n, "name": _INTERVALS[n], "systems": per})
    return {"rows": rows}


# ===================================================================== classics
def _classics_harris(a: Dict[str, Any]) -> Dict[str, Any]:
    """harris {contexts: [str], edges: [[above, below]]}: a Harris matrix check. At most 200 contexts and 1000 edges,
    names up to 60 characters; an edge naming an unknown context is an error. A cycle is a result: {cycle: [c...]}
    (the first one found, scanning names alphabetically). Otherwise {order: [c] (above before below, Kahn with
    alphabetical ties), phases: [[c]] (longest-path layers from the top), redundant: [[a, b]] (edges implied by a
    longer path), isolated: [c] (no edges)}."""
    ctx = [_name(c, f"contexts.{i}") for i, c in enumerate(_list(a.get("contexts"), "contexts", 1, 200))]
    if len(set(ctx)) != len(ctx):
        raise _bad("contexts must be different names.", "contexts")
    known = set(ctx)
    edges: List[Tuple[str, str]] = []
    for i, e in enumerate(_list(a.get("edges", []), "edges", 0, 1000)):
        if not isinstance(e, list) or len(e) != 2:
            raise _bad("An edge is [above, below].", f"edges.{i}")
        for j in (0, 1):
            if not isinstance(e[j], str) or e[j] not in known:
                raise _bad("The edge names an unknown context.", f"edges.{i}.{j}")
        edges.append((e[0], e[1]))
    edges = sorted(set(edges))
    succ: Dict[str, List[str]] = {c: [] for c in ctx}
    pred: Dict[str, List[str]] = {c: [] for c in ctx}
    for u, v in edges:
        succ[u].append(v)
        pred[v].append(u)
    # cycle: iterative DFS, names and neighbours in alphabetical order
    state = {c: 0 for c in ctx}
    for start in sorted(ctx):
        if state[start]:
            continue
        stack = [(start, iter(succ[start]))]
        path = [start]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
                path.pop()
            elif state[nxt] == 1:
                return {"cycle": path[path.index(nxt):]}
            elif state[nxt] == 0:
                state[nxt] = 1
                stack.append((nxt, iter(succ[nxt])))
                path.append(nxt)
    indeg = {c: len(pred[c]) for c in ctx}
    heap = [c for c in ctx if indeg[c] == 0]
    heapq.heapify(heap)
    order: List[str] = []
    while heap:
        c = heapq.heappop(heap)
        order.append(c)
        for v in succ[c]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)
    layer: Dict[str, int] = {}
    for c in order:
        layer[c] = max((layer[p] + 1 for p in pred[c]), default=0)
    phases: List[List[str]] = [[] for _ in range(max(layer.values()) + 1)]
    for c in sorted(ctx):
        phases[layer[c]].append(c)
    index = {c: i for i, c in enumerate(ctx)}
    reach = {c: 0 for c in ctx}  # bit mask of everything below c
    for c in reversed(order):
        for v in succ[c]:
            reach[c] |= (1 << index[v]) | reach[v]
    redundant = [[u, v] for u, v in edges
                 if any(w != v and (reach[w] >> index[v]) & 1 for w in succ[u])]
    return {"order": order, "phases": phases, "redundant": redundant,
            "isolated": sorted(c for c in ctx if not succ[c] and not pred[c])}


_OPEN = {"[": ("restored", "]"), "(": ("expansion", ")"), "<": ("addition", ">"), "{": ("deletion", "}"),
         "[[": ("erasure", "]]"), "⟦": ("erasure", "⟧")}
_CLOSERS = set("])>}⟧")
_LOST = re.compile(r"\[(---|\.\.\.|\.\d+)\]")


def _classics_leiden(a: Dict[str, Any]) -> Dict[str, Any]:
    """leiden {text}: reads Leiden brackets. At most 2000 characters and 40 lines. [abc] restored, [---] [...] [.3] lost
    letters, (abc) expansion of an abbreviation, <abc> editorial addition, {abc} editorial deletion, [[abc]] or ⟦abc⟧
    erased in antiquity, a combining underdot marks an uncertain letter, | or a newline is a line break, vac. is a
    vacat. `diplomatic` keeps what is carved and still legible (plain, uncertain and {deleted} letters); `edited`
    is the editor's reading (plain, restored, expanded, added and uncertain letters, no lost, deleted or erased text).
    Result: {tokens: [{kind, text, line}], diplomatic, edited, normalized, counts: {kind: int}, problems: [{code:
    unbalanced|nested, at}]}; kind is text|restored|lost|expansion|addition|deletion|erasure|uncertain|vacat and
    `at` is a 0-based character index."""
    raw = _text(a.get("text"), "text", 2000, required=True)
    if raw.count("\n") + 1 > 40:
        raise _bad("text has more than 40 lines.", "text")
    s = unicodedata.normalize("NFD", raw)
    tokens: List[Dict[str, Any]] = []
    problems: List[Dict[str, Any]] = []
    line = 1
    mode: Optional[str] = None
    closer = ""
    opener_at = 0
    buf: List[str] = []

    def flush(kind: str) -> None:
        if buf:
            tokens.append({"kind": kind, "text": unicodedata.normalize("NFC", "".join(buf)), "line": line})
            buf.clear()

    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        cur = mode or "text"
        if ch in "\n|":
            flush(cur)
            line += 1
            i += 1
            continue
        if s.startswith("vac.", i) and mode is None:
            flush("text")
            tokens.append({"kind": "vacat", "text": "vac.", "line": line})
            i += 4
            continue
        if mode is None:
            if s.startswith("[[", i):
                flush("text"); mode, closer, opener_at = "erasure", "]]", i; i += 2; continue
            m = _LOST.match(s, i)
            if m:
                flush("text")
                tokens.append({"kind": "lost", "text": m.group(1), "line": line})
                i = m.end()
                continue
            if ch in _OPEN and ch != "[":
                flush("text"); mode, closer, opener_at = _OPEN[ch][0], _OPEN[ch][1], i; i += 1; continue
            if ch == "[":
                flush("text"); mode, closer, opener_at = "restored", "]", i; i += 1; continue
            if ch in _CLOSERS:
                problems.append({"code": "unbalanced", "at": i})
                i += 1
                continue
            j = i + 1
            while j < n and unicodedata.combining(s[j]):  # the letter's marks (NFD puts the underdot before accents)
                j += 1
            if j > i + 1 and "̣" in s[i + 1:j] and not unicodedata.combining(ch):
                flush("text")  # one uncertain letter keeps its accents and breathings with it
                tokens.append({"kind": "uncertain", "text": unicodedata.normalize("NFC", s[i:j]), "line": line})
                i = j
                continue
            buf.append(ch)
            i += 1
            continue
        # inside a bracket
        if s.startswith(closer, i):
            flush(mode)
            mode = None
            i += len(closer)
            continue
        if ch in _OPEN or ch in _CLOSERS or s.startswith("[[", i):
            problems.append({"code": "nested" if ch in _OPEN else "unbalanced", "at": i})
            i += 1
            continue
        buf.append(ch)
        i += 1
    if mode is not None:
        flush(mode)
        problems.append({"code": "unbalanced", "at": opener_at})
    flush("text")
    problems.sort(key=lambda p: (p["at"], p["code"]))
    # rebuild lines for the two readings
    dip_kinds = {"text", "uncertain", "deletion"}
    ed_kinds = {"text", "restored", "expansion", "addition", "uncertain"}

    def build(kinds: set) -> str:
        lines: Dict[int, str] = {}
        for t in tokens:
            if t["kind"] in kinds:
                txt = t["text"]
                if kinds is ed_kinds and t["kind"] == "uncertain":
                    txt = "".join(c for c in unicodedata.normalize("NFD", txt) if c != "̣")
                lines[t["line"]] = lines.get(t["line"], "") + unicodedata.normalize("NFC", txt)
        return "\n".join(lines.get(k, "") for k in range(1, line + 1))

    diplomatic, edited = build(dip_kinds), build(ed_kinds)
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t["kind"]] = counts.get(t["kind"], 0) + 1
    return {"tokens": tokens, "diplomatic": diplomatic, "edited": edited,
            "normalized": practice_classics._normalize_epigraphy(edited), "counts": counts, "problems": problems}


# ===================================================================== literature
_FOOTS = {"x/": "iamb", "/x": "trochee", "//": "spondee", "xx": "pyrrhic", "xx/": "anapest", "/xx": "dactyl",
          "x/x": "amphibrach"}
_METERS = {  # meter -> (base foot, allowed feet, a lone final syllable is allowed as ...)
    "iambic": ("iamb", ["x/", "/x", "//", "xx", "xx/"]),
    "trochaic": ("trochee", ["/x", "x/", "//", "xx", "/xx"]),
    "anapestic": ("anapest", ["xx/", "x/", "//", "xx"]),
    "dactylic": ("dactyl", ["/xx", "/x", "//", "xx"]),
}
_LINE_NAMES = ["", "monometer", "dimeter", "trimeter", "tetrameter", "pentameter", "hexameter", "heptameter", "octameter"]


def _scan_meter(sy: str, meter: str) -> Dict[str, Any]:
    base_name, allowed = _METERS[meter]
    n = len(sy)
    best: Dict[int, Optional[Tuple[Tuple[int, int], List[str], bool]]] = {}

    def solve(i: int):
        if i in best:
            return best[i]
        if i == n:
            res = ((0, 0), [], False)
        else:
            cands = []
            for p in allowed:
                if sy.startswith(p, i):
                    sub = solve(i + len(p))
                    cost = 0 if _FOOTS[p] == base_name else 1
                    cands.append(((sub[0][0] + cost, sub[0][1] + 1), [p] + sub[1], sub[2]))
            rest = sy[i:]
            if len(rest) == 1 and rest == "x" and meter in ("iambic", "anapestic"):
                cands.append(((0, 0), [], True))  # feminine ending
            elif len(rest) == 1 and rest == "/" and meter == "trochaic":
                cands.append(((0, 1), ["/"], False))  # catalectic final foot
            elif len(rest) <= 2:
                cands.append(((1, 1), [rest], False))  # incomplete final foot
            res = min(cands, key=lambda c: c[0]) if cands else ((10 ** 6, 0), [], False)
        best[i] = res
        return res

    (cost, _), pats, fem = solve(0)
    feet = []
    for p in pats:
        name = _FOOTS.get(p, "irregular")
        if p == "/" and meter == "trochaic":
            name = "trochee"
        elif p not in _FOOTS:
            name = "incomplete"
        feet.append({"pattern": p, "name": name, "substitution": name != base_name and not (p == "/" and meter == "trochaic")})
    subs = sum(1 for f in feet if f["substitution"])
    fit = max(0.0, 1 - subs / len(feet)) if feet else 0.0
    return {"meter": meter, "feet": feet, "foot_count": len(feet),
            "line_name": _LINE_NAMES[len(feet)] if len(feet) < len(_LINE_NAMES) else f"{len(feet)}-foot",
            "feminine_ending": fem, "fit": _r4(fit)}


def _lit_scan(a: Dict[str, Any]) -> Dict[str, Any]:
    """scan {stresses, meter = auto}: x or u is an unstressed syllable, / a stressed one, spaces are ignored, 1..24
    syllables. meter is auto|iambic|trochaic|anapestic|dactylic. Feet are read by the segmentation with the fewest
    substitutions (a foot other than the meter's own); named iamb, trochee, spondee, pyrrhic, anapest, dactyl,
    amphibrach, else irregular/incomplete. A final lone unstressed syllable of an iambic or anapestic line is a
    feminine ending, not a foot; a lone final stress of a trochaic line is a catalectic trochee. fit = 1 minus the
    share of feet that are substitutions. auto takes the best fit, ties in the order iambic, trochaic, anapestic,
    dactylic. Result: {meter, feet: [{pattern, name, substitution}], foot_count, line_name ("pentameter"),
    feminine_ending, fit}."""
    raw = a.get("stresses")
    if not isinstance(raw, str):
        raise _bad("stresses must be text such as x/x/x/x/x/.", "stresses")
    sy = ""
    for k, ch in enumerate(raw):
        if ch.isspace():
            continue
        if ch in "xXuU":
            sy += "x"
        elif ch == "/":
            sy += "/"
        else:
            raise _bad("Use x or u for unstressed and / for stressed.", f"stresses.{k}")
    if not 1 <= len(sy) <= 24:
        raise _bad("A line has 1 to 24 syllables.", "stresses")
    meter = a.get("meter", "auto")
    if meter == "auto":
        results = [_scan_meter(sy, m) for m in _METERS]
        best = results[0]
        for r in results[1:]:
            if r["fit"] > best["fit"]:
                best = r
        return best
    if meter not in _METERS:
        raise _bad("meter is auto, iambic, trochaic, anapestic or dactylic.", "meter")
    return _scan_meter(sy, meter)


def _canon(labels: List[str]) -> List[str]:
    seen: Dict[str, str] = {}
    out = []
    for lab in labels:
        key = lab.strip().casefold()
        if key not in seen:
            seen[key] = chr(ord("A") + len(seen)) if len(seen) < 26 else f"#{len(seen)}"
        out.append(seen[key])
    return out


def _fold(s: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", s).casefold() if c.isalnum() or c.isspace()).split())


_PETRARCHAN = ["ABBAABBACDECDE", "ABBAABBACDCDCD", "ABBAABBACDDCDC", "ABBAABBACDEDCE"]


def _lit_form(a: Dict[str, Any]) -> Dict[str, Any]:
    """form {form, rhymes: [str], lines?: [str]}: compares the rhyme letters the student assigned with a fixed form.
    Forms: shakespearean_sonnet (ABAB CDCD EFEF GG), petrarchan_sonnet (ABBAABBA then the closest of the sestets
    CDECDE, CDCDCD, CDDCDC, CDEDCE), villanelle (19 lines, ABA x5 then ABAA, refrains compared on `lines` ignoring
    case and punctuation: line 1 returns at 6, 12, 18 and line 3 at 9, 15, 19), limerick (AABBA), terza_rima (ABA
    BCB CDC ..., a closing single line allowed). Letters are the student's own and compared as a pattern (XYXY equals
    ABAB); the tool never decides what rhymes. At most 60 lines of at most 300 characters. Result: {expected_lines,
    line_count_ok, scheme_expected, scheme_given, mismatches: [0-based line], refrains: [{line (1-based), ok}], fit
    (matching positions and refrains over all checked)}."""
    form = a.get("form")
    forms = ("shakespearean_sonnet", "petrarchan_sonnet", "villanelle", "limerick", "terza_rima")
    if form not in forms:
        raise _bad("form is one of " + ", ".join(forms) + ".", "form")
    rhymes = [_name(r, f"rhymes.{i}", 10) for i, r in enumerate(_list(a.get("rhymes"), "rhymes", 1, 60))]
    lines_raw = a.get("lines")
    lines = None
    if lines_raw is not None:
        lines = [_text(t, f"lines.{i}", 300, required=True) for i, t in enumerate(_list(lines_raw, "lines", 0, 60))]
    given = _canon(rhymes)
    if form == "shakespearean_sonnet":
        expected = list("ABABCDCDEFEFGG")
    elif form == "limerick":
        expected = list("AABBA")
    elif form == "villanelle":
        expected = list("ABA" * 5 + "ABAA")
    elif form == "petrarchan_sonnet":
        expected = list(min(_PETRARCHAN, key=lambda p: sum(1 for x, y in zip(_canon(list(p)), given) if x != y)))
    else:
        total = len(rhymes)
        expected = [chr(ord("A") + (i // 3 if i % 3 != 1 else i // 3 + 1)) for i in range(total)]
    expected = _canon(expected)
    count_ok = len(rhymes) == len(expected) and (form != "terza_rima" or (len(rhymes) >= 3 and len(rhymes) % 3 in (0, 1)))
    mismatches = [i for i in range(min(len(given), len(expected))) if given[i] != expected[i]]
    refrains: List[Dict[str, Any]] = []
    if form == "villanelle" and lines is not None:
        folded = [_fold(t) for t in lines]
        for src, dests in ((0, (5, 11, 17)), (2, (8, 14, 18))):
            for d in dests:
                ok = d < len(folded) and src < len(folded) and folded[d] == folded[src] and folded[src] != ""
                refrains.append({"line": d + 1, "ok": ok})
        refrains.sort(key=lambda r: r["line"])
    denom = len(expected) + len(refrains)
    matches = min(len(given), len(expected)) - len(mismatches) + sum(1 for r in refrains if r["ok"])
    return {"expected_lines": len(expected), "line_count_ok": count_ok, "scheme_expected": "".join(expected),
            "scheme_given": "".join(given), "mismatches": mismatches, "refrains": refrains,
            "fit": _r4(matches / denom) if denom else 0.0}


# ===================================================================== rhetoric
_TOULMIN = ("claim", "data", "warrant", "backing", "qualifier", "rebuttal")


def _rhet_toulmin(a: Dict[str, Any]) -> Dict[str, Any]:
    """toulmin {claim, data, warrant, backing, qualifier, rebuttal}: each text up to 1000 characters, missing or blank
    counts as absent. It checks only which parts are present, never how good they are. complete means claim, data
    and warrant are all present (backing, qualifier and rebuttal are optional parts and appear in `missing` when
    absent). Result: {present: {field: bool}, missing: [field], complete, notes: [fixed sentences]}."""
    present = {f: bool(_text(a.get(f), f, 1000).strip()) for f in _TOULMIN}
    notes = []
    if not present["claim"]:
        notes.append("There is no claim: say what the reader should accept")
    if present["claim"] and not present["data"]:
        notes.append("A claim without data has nothing to stand on")
    if present["data"] and not present["warrant"]:
        notes.append("The data is not yet connected to the claim: state the warrant")
    if present["backing"] and not present["warrant"]:
        notes.append("Backing supports a warrant, but no warrant is stated")
    if present["qualifier"] and not present["rebuttal"]:
        notes.append("A qualifier without a rebuttal leaves the exception unstated")
    if present["rebuttal"] and not present["qualifier"]:
        notes.append("A rebuttal without a qualifier leaves the strength of the claim unstated")
    return {"present": present, "missing": [f for f in _TOULMIN if not present[f]],
            "complete": all(present[f] for f in ("claim", "data", "warrant")), "notes": notes}


def _rhet_appeals(a: Dict[str, Any]) -> Dict[str, Any]:
    """appeals {segments: [{text, tags: [ethos|logos|pathos]}]}: at most 100 segments, text up to 1000 characters. A
    segment's weight is its trimmed length split evenly across its distinct tags; a segment with no tags counts as
    untagged. Result: {totals: {ethos, logos, pathos}, shares (sum 1, all 0 when nothing is tagged), point: {x, y}
    (barycentric: ethos bottom left (0,0), pathos bottom right (1,0), logos top (0.5, 0.866); the centre when
    nothing is tagged), untagged_chars}."""
    segs = _list(a.get("segments"), "segments", 0, 100)
    tot = {"ethos": 0.0, "logos": 0.0, "pathos": 0.0}
    untagged = 0
    for i, s in enumerate(segs):
        s = _dict(s, f"segments.{i}")
        text = _text(s.get("text"), f"segments.{i}.text", 1000, required=True).strip()
        tags = []
        for j, t in enumerate(_list(s.get("tags", []), f"segments.{i}.tags", 0, 3)):
            if t not in tot:
                raise _bad("Tags are ethos, logos or pathos.", f"segments.{i}.tags.{j}")
            if t not in tags:
                tags.append(t)
        if not tags:
            untagged += len(text)
        for t in tags:
            tot[t] += len(text) / len(tags)
    s_all = sum(tot.values())
    shares = {k: (v / s_all if s_all else 0.0) for k, v in tot.items()}
    if s_all:
        x = shares["pathos"] + 0.5 * shares["logos"]
        y = shares["logos"] * math.sqrt(3) / 2
    else:
        x, y = 0.5, math.sqrt(3) / 6
    return {"totals": {k: _r4(v) for k, v in tot.items()}, "shares": {k: _r4(v) for k, v in shares.items()},
            "point": {"x": _r4(x), "y": _r4(y)}, "untagged_chars": untagged}


# ===================================================================== STEM kits (docs/plans/STEM_KIT_TOOLS_CONTRACT.md)
# Size caps answer too_large (or too_complex for a circuit that is too big); wrong shapes and values answer bad_args.
def _cap_list(v: Any, at: str, lo: int, hi: int) -> list:
    if not isinstance(v, list):
        raise _bad(f"{at} must be a list.", at)
    if len(v) > hi:
        raise ToolError("too_large", f"{at} has more than {hi} items.", at)
    if len(v) < lo:
        raise _bad(f"{at} needs at least {lo} items.", at)
    return v


def _real(v: Any, at: str, lo: float = -1e12, hi: float = 1e12) -> float:
    """A finite number within [lo, hi] (as a float)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise _bad(f"{at} must be a number.", at)
    if isinstance(v, float) and not math.isfinite(v):
        raise _bad(f"{at} must be a finite number.", at)
    try:
        f = float(v)
    except OverflowError:
        raise _bad(f"{at} is out of range.", at)
    if f < lo or f > hi:
        raise _bad(f"{at} must be between {lo:g} and {hi:g}.", at)
    return f


def _sig(x: float) -> float:
    """Six significant digits, for values that can be very small (frequencies, p-values)."""
    return float(f"{x:.6g}") + 0.0


def _is_pow2(n: int) -> bool:
    return n > 0 and n & (n - 1) == 0


# ===================================================================== ee
def _node_name(v: Any, at: str) -> str:
    if isinstance(v, bool) or not isinstance(v, (str, int)):
        raise _bad(f"{at} must be a node name.", at)
    s = str(v)
    if not s or len(s) > 12:
        raise _bad(f"{at} must be 1 to 12 characters.", at)
    return s


_EE_LIMIT = {"R": (Fraction(0), Fraction(10 ** 9)), "V": (Fraction(-10 ** 6), Fraction(10 ** 6)),
             "I": (Fraction(-10 ** 6), Fraction(10 ** 6))}


def _ee_dc_solve(a: Dict[str, Any]) -> Dict[str, Any]:
    """dc_solve {elements: [{type: R|V|I, a, b, value}], ground = "0"}: DC operating point by modified nodal analysis
    in exact fractions. R is ohms in (0, 1e9]; V volts with node `a` the + terminal; I amps flowing a -> b inside the
    source; |V|, |I| <= 1e6. Node names up to 12 characters. Caps: 30 elements (too_large), 12 nodes and 10 voltage
    sources (too_complex). The ground node must appear in an element (bad_args at "ground"). Currents run a -> b
    through the element and power is absorbed (a voltage source that delivers power has negative power); the powers
    sum to 0. Result: {solvable: true, nodes: {n: {exact, value}}, elements: [{index, type, current, voltage, power,
    current_exact, voltage_exact, power_exact}]} or {solvable: false, reason: floating_node|singular, nodes_unreached:
    [n]} (floating: no path of resistors or voltage sources to ground; singular: e.g. a loop of voltage sources)."""
    ground = _node_name(a.get("ground", "0"), "ground")
    raw = _cap_list(a.get("elements"), "elements", 1, 30)
    els: List[Tuple[str, str, str, Fraction]] = []
    nodes: List[str] = []
    for i, e in enumerate(raw):
        e = _dict(e, f"elements.{i}")
        t = e.get("type")
        if t not in _EE_LIMIT:
            raise _bad("type is R, V or I.", f"elements.{i}.type")
        na, nb = _node_name(e.get("a"), f"elements.{i}.a"), _node_name(e.get("b"), f"elements.{i}.b")
        val = e.get("value")
        if isinstance(val, bool) or not isinstance(val, (int, float)) or (isinstance(val, float) and not math.isfinite(val)):
            raise _bad("value must be a finite number.", f"elements.{i}.value")
        fv = Fraction(str(val))
        lo, hi = _EE_LIMIT[t]
        if (t == "R" and not (lo < fv <= hi)) or (t != "R" and not (lo <= fv <= hi)):
            raise _bad("value is out of range (R in (0, 1e9], V and I within 1e6).", f"elements.{i}.value")
        els.append((t, na, nb, fv))
        for n in (na, nb):
            if n not in nodes:
                nodes.append(n)
    if ground not in nodes:
        raise _bad("The ground node is not used by any element.", "ground")
    if len(nodes) > 12:
        raise ToolError("too_complex", "A circuit has at most 12 nodes.", "elements")
    vs = [k for k, e in enumerate(els) if e[0] == "V"]
    if len(vs) > 10:
        raise ToolError("too_complex", "A circuit has at most 10 voltage sources.", "elements")
    # floating nodes: nothing but current sources ties them to ground
    adj: Dict[str, List[str]] = {n: [] for n in nodes}
    for t, na, nb, _ in els:
        if t in ("R", "V"):
            adj[na].append(nb)
            adj[nb].append(na)
    seen = {ground}
    stack = [ground]
    while stack:
        for m in adj[stack.pop()]:
            if m not in seen:
                seen.add(m)
                stack.append(m)
    lost = [n for n in nodes if n not in seen]
    if lost:
        return {"solvable": False, "reason": "floating_node", "nodes_unreached": lost}
    free = [n for n in nodes if n != ground]
    idx = {n: i for i, n in enumerate(free)}
    nn, size = len(free), len(free) + len(vs)
    M = [[Fraction(0)] * (size + 1) for _ in range(size)]
    vcol = {k: nn + j for j, k in enumerate(vs)}
    for k, (t, na, nb, v) in enumerate(els):
        ia, ib = idx.get(na), idx.get(nb)
        if t == "R":
            g = 1 / v
            for p, q, s in ((ia, ia, 1), (ib, ib, 1), (ia, ib, -1), (ib, ia, -1)):
                if p is not None and q is not None:
                    M[p][q] += s * g
        elif t == "I":
            if ia is not None:
                M[ia][size] -= v
            if ib is not None:
                M[ib][size] += v
        else:
            c = vcol[k]
            if ia is not None:
                M[ia][c] += 1
                M[c][ia] += 1
            if ib is not None:
                M[ib][c] -= 1
                M[c][ib] -= 1
            M[c][size] += v
    for col in range(size):  # Gaussian elimination, first nonzero pivot in row order
        piv = next((r for r in range(col, size) if M[r][col] != 0), None)
        if piv is None:
            return {"solvable": False, "reason": "singular", "nodes_unreached": []}
        M[col], M[piv] = M[piv], M[col]
        for r in range(size):
            if r != col and M[r][col] != 0:
                f = M[r][col] / M[col][col]
                M[r] = [x - f * y for x, y in zip(M[r], M[col])]
    x = [M[i][size] / M[i][i] for i in range(size)]
    volt = {ground: Fraction(0)}
    for n in free:
        volt[n] = x[idx[n]]
    out_nodes = {n: {"exact": _frac(volt[n]), "value": _r4(volt[n])} for n in nodes}
    rows = []
    for k, (t, na, nb, v) in enumerate(els):
        dv = volt[na] - volt[nb]
        cur = dv / v if t == "R" else (x[vcol[k]] if t == "V" else v)
        pw = dv * cur
        rows.append({"index": k, "type": t, "current": _r4(cur), "voltage": _r4(dv), "power": _r4(pw),
                     "current_exact": _frac(cur), "voltage_exact": _frac(dv), "power_exact": _frac(pw)})
    return {"solvable": True, "nodes": out_nodes, "elements": rows}


def _ee_bode(a: Dict[str, Any]) -> Dict[str, Any]:
    """bode {num: [c], den: [c], w_min = 0.01, w_max = 1e4, points = 121}: frequency response of N(s)/D(s) at s = jw.
    Coefficients highest power first, degree <= 6, |c| <= 1e9, den not all zero; 0 < w_min < w_max <= 1e9; points
    11..401, log-spaced. Phase is unwrapped from w_min, starting on the branch nearest the low-frequency asymptote (0 degrees for a positive gain, -180 for a negative gain, -90 per pole at the origin), so -1/(s+1) starts near -180. Crossings are found by bracketing on the grid and 60
    bisection steps; frequencies are given to 6 significant digits. cutoff is the first w where the magnitude falls
    3.0103 dB below its value at w_min; the gain crossover is the first crossing of 0 dB; the phase crossover the first
    crossing of -180 degrees; phase margin = 180 + phase at the gain crossover (wrapped to -180..180); gain margin =
    -gain (dB) at the phase crossover. Result: {samples: [{w, mag_db, phase_deg}], dc_gain_db (null when D(0) or N(0)
    is 0), cutoff_rad_s, gain_crossover, phase_margin_deg, phase_crossover, gain_margin_db, undefined_at: [w]}; each
    crossing value is null when the grid has none. Magnitude is floored at -400 dB."""
    def poly(v: Any, at: str) -> List[float]:
        return [_real(c, f"{at}.{i}", -1e9, 1e9) for i, c in enumerate(_cap_list(v, at, 1, 7))]
    num, den = poly(a.get("num"), "num"), poly(a.get("den"), "den")
    if not any(den):
        raise _bad("den must not be all zero.", "den")
    w_min = _real(a.get("w_min", 0.01), "w_min", 1e-12, 1e9)
    w_max = _real(a.get("w_max", 1e4), "w_max", 1e-12, 1e9)
    if w_min <= 0 or w_max <= w_min:
        raise _bad("Need 0 < w_min < w_max.", "w_max")
    pts = _int(a.get("points", 121), 11, 401, "points")

    def resp(w: float) -> Optional[complex]:
        s = complex(0, w)
        n = d = 0j
        for c in num:
            n = n * s + c
        for c in den:
            d = d * s + c
        scale = sum(abs(c) * w ** (len(den) - 1 - k) for k, c in enumerate(den))
        return None if abs(d) <= max(1e-300, 1e-9 * scale) else n / d

    def db(h: complex) -> float:
        return 20 * math.log10(max(abs(h), 1e-20))

    def unwrap(raw: float, ref: float) -> float:
        return raw + 360 * round((ref - raw) / 360)

    ratio = (w_max / w_min) ** (1 / (pts - 1))
    S: List[Tuple[float, float, float]] = []
    undefined: List[float] = []

    def low_order(c: List[float]) -> Optional[Tuple[int, float]]:
        for k in range(len(c) - 1, -1, -1):  # the lowest power of s with a nonzero coefficient
            if c[k] != 0:
                return len(c) - 1 - k, c[k]
        return None
    ln, ld = low_order(num), low_order(den)
    # low-frequency asymptote: a positive constant is 0 degrees, a negative one -180, and each net pole at the origin -90
    ref = None
    if ln is not None and ld is not None:
        ref = (0.0 if ln[1] / ld[1] > 0 else -180.0) + 90.0 * (ln[0] - ld[0])
    for k in range(pts):
        w = w_min * ratio ** k if k < pts - 1 else w_max
        h = resp(w)
        if h is None:
            undefined.append(_sig(w))
            continue
        ph = math.degrees(math.atan2(h.imag, h.real))
        ph = ph if ref is None else unwrap(ph, ref)
        ref = ph
        S.append((w, db(h), ph))

    def bisect(f: Callable[[float], Optional[float]], lo: float, hi: float) -> Optional[float]:
        flo = f(lo)
        if flo is None:
            return None
        for _ in range(60):
            mid = math.sqrt(lo * hi)
            fm = f(mid)
            if fm is None:
                return None
            if (fm > 0) == (flo > 0):
                lo, flo = mid, fm
            else:
                hi = mid
        return math.sqrt(lo * hi)

    def mag_f(off: float) -> Callable[[float], Optional[float]]:
        return lambda w: None if resp(w) is None else db(resp(w)) - off

    cutoff = wgc = wpc = pm = gm = None
    if S:
        thr = S[0][1] - 3.0103
        for i in range(1, len(S)):
            if S[i][1] <= thr < S[i - 1][1]:
                cutoff = bisect(mag_f(thr), S[i - 1][0], S[i][0])
                break
        for i in range(1, len(S)):
            if (S[i - 1][1] > 0) != (S[i][1] > 0):
                wgc = bisect(mag_f(0.0), S[i - 1][0], S[i][0])
                if wgc is not None:
                    h = resp(wgc)
                    raw = math.degrees(math.atan2(h.imag, h.real))
                    pm = ((180 + unwrap(raw, S[i - 1][2]) + 180) % 360) - 180
                break
        for i in range(1, len(S)):
            if (S[i - 1][2] + 180 > 0) != (S[i][2] + 180 > 0):
                left = S[i - 1][2]

                def pf(w: float, left: float = left) -> Optional[float]:
                    h = resp(w)
                    if h is None:
                        return None
                    return unwrap(math.degrees(math.atan2(h.imag, h.real)), left) + 180
                wpc = bisect(pf, S[i - 1][0], S[i][0])
                if wpc is not None:
                    gm = -db(resp(wpc))
                break
    dc = None
    if den[-1] != 0 and num[-1] != 0:
        dc = _r4(20 * math.log10(abs(num[-1] / den[-1])))
    return {"samples": [{"w": _sig(w), "mag_db": _r4(m), "phase_deg": _r4(p)} for w, m, p in S],
            "dc_gain_db": dc, "cutoff_rad_s": None if cutoff is None else _sig(cutoff),
            "gain_crossover": None if wgc is None else _sig(wgc),
            "phase_margin_deg": None if pm is None else _r4(pm),
            "phase_crossover": None if wpc is None else _sig(wpc),
            "gain_margin_db": None if gm is None else _r4(gm), "undefined_at": undefined}


# ===================================================================== ai
def _confusion_stats(m: List[List[int]], labels: List[int]) -> Dict[str, Any]:
    k = len(m)
    total = sum(sum(r) for r in m)
    rows = [sum(r) for r in m]
    cols = [sum(m[i][j] for i in range(k)) for j in range(k)]
    per, f1s = [], []
    for i in range(k):
        tp = m[i][i]
        fn, fp = rows[i] - tp, cols[i] - tp
        tn = total - tp - fn - fp
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        sp = tn / (tn + fp) if tn + fp else 0.0
        f1s.append(f)
        per.append({"label": labels[i], "precision": _r4(p), "recall": _r4(r), "f1": _r4(f),
                    "specificity": _r4(sp), "support": rows[i]})
    acc = sum(m[i][i] for i in range(k)) / total if total else 0.0
    pe = sum(rows[i] * cols[i] for i in range(k)) / (total * total) if total else 0.0
    kappa = (acc - pe) / (1 - pe) if 1 - pe > 1e-15 else 0.0
    mcc = None
    if k == 2:
        tp, fn, fp, tn = m[0][0], m[0][1], m[1][0], m[1][1]
        den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = _r4((tp * tn - fp * fn) / den) if den else 0.0
    weighted = sum(f * s for f, s in zip(f1s, rows)) / total if total else 0.0
    return {"accuracy": _r4(acc), "per_class": per, "macro_f1": _r4(sum(f1s) / k), "weighted_f1": _r4(weighted),
            "micro_f1": _r4(acc), "kappa": _r4(kappa), "mcc": mcc, "matrix": m}


def _ai_metrics(a: Dict[str, Any]) -> Dict[str, Any]:
    """metrics {matrix: [[int]]} or {labels: [0|1], scores: [num], threshold = 0.5}. A matrix is k x k with k 2..10,
    rows = actual class, columns = predicted, counts 0..1e9; for k = 2 class 0 is the positive class (TP is
    matrix[0][0]). Score mode takes 2..2000 pairs; a score >= threshold predicts label 1, and the matrix is
    [[TP, FN], [FP, TN]] with label 1 positive (per_class lists label 1 first, then 0). A zero denominator gives 0.
    Result: {accuracy, per_class: [{label, precision, recall, f1, specificity, support}], macro_f1, weighted_f1,
    micro_f1 (= accuracy), kappa (Cohen), mcc (k = 2 only, else null), matrix}; score mode adds roc: [{fpr, tpr,
    threshold}] (starts at (0, 0) with threshold null; equal scores form one point) and auc (trapezoid; null when a
    class is missing)."""
    if a.get("matrix") is not None:
        raw = _cap_list(a["matrix"], "matrix", 2, 10)
        m = []
        for i, r in enumerate(raw):
            r = _cap_list(r, f"matrix.{i}", 1, 10)
            if len(r) != len(raw):
                raise _bad("matrix must be square (k x k).", f"matrix.{i}")
            m.append([_int(x, 0, 10 ** 9, f"matrix.{i}.{j}") for j, x in enumerate(r)])
        return _confusion_stats(m, list(range(len(m))))
    labels = _cap_list(a.get("labels"), "labels", 2, 2000)
    scores = _cap_list(a.get("scores"), "scores", 2, 2000)
    if len(labels) != len(scores):
        raise _bad("labels and scores need the same length.", "scores")
    thr = _real(a.get("threshold", 0.5), "threshold")
    ys = [_int(v, 0, 1, f"labels.{i}") for i, v in enumerate(labels)]
    ss = [_real(v, f"scores.{i}") for i, v in enumerate(scores)]
    tp = sum(1 for y, s in zip(ys, ss) if y == 1 and s >= thr)
    fp = sum(1 for y, s in zip(ys, ss) if y == 0 and s >= thr)
    P, N = sum(ys), len(ys) - sum(ys)
    out = _confusion_stats([[tp, P - tp], [fp, N - fp]], [1, 0])
    roc: List[Dict[str, Any]] = [{"fpr": 0.0, "tpr": 0.0, "threshold": None}]
    ctp = cfp = 0
    pts = [(0.0, 0.0)]
    order = sorted(range(len(ys)), key=lambda i: -ss[i])
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and ss[order[j]] == ss[order[i]]:
            ctp += ys[order[j]]
            cfp += 1 - ys[order[j]]
            j += 1
        fpr, tpr = (cfp / N if N else 0.0), (ctp / P if P else 0.0)
        pts.append((fpr, tpr))
        roc.append({"fpr": _r4(fpr), "tpr": _r4(tpr), "threshold": _r4(ss[order[i]])})
        i = j
    out["roc"] = roc
    out["auc"] = _r4(sum((x1 - x0) * (y0 + y1) / 2 for (x0, y0), (x1, y1) in zip(pts, pts[1:]))) if P and N else None
    return out


def _ai_descent(a: Dict[str, Any]) -> Dict[str, Any]:
    """descent {model: linear|logistic, X: [[num]], y: [num], w?: [num], b = 0, lr = 0.1, steps = 50}: batch gradient
    descent. 1..100 rows, 1..8 features, steps 1..500, lr in (0, 10], values within 1e6, logistic y in {0, 1}, w
    defaults to zeros. Linear loss is mean 0.5*(yhat - y)^2; logistic loss is mean cross-entropy with p clamped to
    [1e-12, 1 - 1e-12] (gradient from the logit, p - y). Row `step` k holds the parameters after k updates with the
    loss and gradient at those parameters (step 0 is the start). It stops when the loss is not finite (that row is
    left out) or above 1e12 (that row is kept). Result: {history: [{step, loss, w, b, grad_w, grad_b}] (at most 200
    rows, evenly thinned, first and last kept), final: {w, b, loss, predictions (at most 100; probabilities for
    logistic)}, diverged}."""
    model = a.get("model")
    if model not in ("linear", "logistic"):
        raise _bad("model is linear or logistic.", "model")
    X = _cap_list(a.get("X"), "X", 1, 100)
    rows = []
    for i, r in enumerate(X):
        r = _cap_list(r, f"X.{i}", 1, 8)
        rows.append([_real(v, f"X.{i}.{j}", -1e6, 1e6) for j, v in enumerate(r)])
    n, d = len(rows), len(rows[0])
    if any(len(r) != d for r in rows):
        raise _bad("Every row of X needs the same number of features.", "X")
    ys = [_real(v, f"y.{i}", -1e6, 1e6) for i, v in enumerate(_cap_list(a.get("y"), "y", 1, 100))]
    if len(ys) != n:
        raise _bad("y needs one value per row of X.", "y")
    if model == "logistic" and any(v not in (0.0, 1.0) for v in ys):
        raise _bad("Logistic y values are 0 or 1.", "y")
    w0 = a.get("w")
    w = [0.0] * d if w0 is None else [_real(v, f"w.{i}", -1e6, 1e6) for i, v in enumerate(_cap_list(w0, "w", 1, 8))]
    if len(w) != d:
        raise _bad("w needs one value per feature.", "w")
    b = _real(a.get("b", 0), "b", -1e6, 1e6)
    lr = _real(a.get("lr", 0.1), "lr", 0.0, 10.0)
    if lr <= 0:
        raise _bad("lr must be above 0.", "lr")
    steps = _int(a.get("steps", 50), 1, 500, "steps")

    def sigmoid(z: float) -> float:
        if z >= 0:
            return 1 / (1 + math.exp(-z))
        e = math.exp(z)
        return e / (1 + e)

    def evaluate(w: List[float], b: float):
        loss, gw, gb, preds = 0.0, [0.0] * d, 0.0, []
        for x, y in zip(rows, ys):
            z = sum(wi * xi for wi, xi in zip(w, x)) + b
            if model == "linear":
                err = z - y
                loss += 0.5 * err * err
                preds.append(z)
            else:
                p = sigmoid(z)
                pc = min(max(p, 1e-12), 1 - 1e-12)
                loss -= y * math.log(pc) + (1 - y) * math.log(1 - pc)
                err = p - y
                preds.append(p)
            gb += err
            for j in range(d):
                gw[j] += err * x[j]
        return loss / n, [g / n for g in gw], gb / n, preds

    hist: List[Dict[str, Any]] = []
    diverged = False
    preds: List[float] = []
    for step in range(steps + 1):
        try:
            loss, gw, gb, p = evaluate(w, b)
        except OverflowError:
            diverged = True
            break
        if not all(math.isfinite(v) for v in [loss, gb] + gw + w + [b]):
            diverged = True
            break
        hist.append({"step": step, "loss": _r4(loss), "w": [_r4(v) for v in w], "b": _r4(b),
                     "grad_w": [_r4(v) for v in gw], "grad_b": _r4(gb)})
        preds = p
        if loss > 1e12:
            diverged = True
            break
        if step < steps:
            w = [wi - lr * g for wi, g in zip(w, gw)]
            b -= lr * gb
    if len(hist) > 200:
        keep = sorted({round(i * (len(hist) - 1) / 199) for i in range(200)})
        hist = [hist[i] for i in keep]
    last = hist[-1] if hist else None
    return {"history": hist,
            "final": {"w": last["w"] if last else [], "b": last["b"] if last else None,
                      "loss": last["loss"] if last else None, "predictions": [_r4(v) for v in preds[:100]]},
            "diverged": diverged}


# ===================================================================== systems
def _address(v: Any, bits: int, at: str) -> int:
    if isinstance(v, bool) or not isinstance(v, (int, str)):
        raise _bad("An address is a hex string such as \"0x1f40\" or a whole number.", at)
    if isinstance(v, str):
        s = v.strip().lower()
        try:
            n = int(s[2:], 16) if s.startswith("0x") else int(s, 10)
        except ValueError:
            raise _bad("An address is a hex string such as \"0x1f40\" or a whole number.", at)
    else:
        n = v
    if n < 0 or n >= 1 << bits:
        raise _bad(f"The address does not fit in {bits} bits.", at)
    return n


def _sys_cache(a: Dict[str, Any]) -> Dict[str, Any]:
    """cache {address_bits = 32, cache_size_bytes = 32768, block_size_bytes = 64, ways = 4 | "full", policy = lru |
    fifo, addresses: [str|int]}: a set-associative cache simulation. address_bits 8..64; cache and block sizes are
    powers of two (cache <= 2^30, block <= cache); ways is a power of two or "full" (fully associative); addresses
    are hex "0x..." or decimal, below 2^address_bits, 1..256 of them (too_large above). A miss is compulsory (the
    block was never seen), capacity (a fully associative LRU cache of the same size also misses) or conflict.
    Result: {bits: {tag, index, offset}, sets, steps: [{address, tag, index, offset, hit, miss_kind, evicted_tag}],
    hits, misses, hit_rate, touched_sets: {index: [tags, oldest first]} (at most 64 sets)}."""
    bits = _int(a.get("address_bits", 32), 8, 64, "address_bits")
    size = _int(a.get("cache_size_bytes", 32768), 1, 1 << 30, "cache_size_bytes")
    block = _int(a.get("block_size_bytes", 64), 1, 1 << 30, "block_size_bytes")
    if not _is_pow2(size):
        raise _bad("cache_size_bytes must be a power of two.", "cache_size_bytes")
    if not _is_pow2(block) or block > size:
        raise _bad("block_size_bytes must be a power of two, at most the cache size.", "block_size_bytes")
    blocks = size // block
    ways_raw = a.get("ways", 4)
    ways = blocks if ways_raw == "full" else _int(ways_raw, 1, 1 << 30, "ways")
    if not _is_pow2(ways) or ways > blocks:
        raise _bad("ways must be \"full\" or a power of two that fits the cache.", "ways")
    policy = a.get("policy", "lru")
    if policy not in ("lru", "fifo"):
        raise _bad("policy is lru or fifo.", "policy")
    sets = blocks // ways
    off_bits, idx_bits = block.bit_length() - 1, sets.bit_length() - 1
    tag_bits = bits - idx_bits - off_bits
    if tag_bits < 0:
        raise _bad("address_bits is too small for this cache.", "address_bits")
    addrs = [_address(v, bits, f"addresses.{i}") for i, v in enumerate(_cap_list(a.get("addresses"), "addresses", 1, 256))]
    state: Dict[int, List[int]] = {}
    seen: set = set()
    shadow: List[int] = []
    steps, hits = [], 0
    for ad in addrs:
        blk = ad >> off_bits
        idx, tag = blk & (sets - 1), blk >> idx_bits
        lines = state.setdefault(idx, [])
        hit = tag in lines
        kind, evicted = None, None
        in_shadow = blk in shadow
        if hit:
            hits += 1
            if policy == "lru":
                lines.remove(tag)
                lines.append(tag)
        else:
            kind = "compulsory" if blk not in seen else ("conflict" if in_shadow else "capacity")
            lines.append(tag)
            if len(lines) > ways:
                evicted = lines.pop(0)
        seen.add(blk)
        if in_shadow:
            shadow.remove(blk)
        shadow.append(blk)
        if len(shadow) > blocks:
            shadow.pop(0)
        steps.append({"address": ad, "tag": tag, "index": idx, "offset": ad & (block - 1), "hit": hit,
                      "miss_kind": kind, "evicted_tag": evicted})
    touched = {str(i): state[i] for i in sorted(state)[:64]}
    return {"bits": {"tag": tag_bits, "index": idx_bits, "offset": off_bits}, "sets": sets, "steps": steps,
            "hits": hits, "misses": len(addrs) - hits, "hit_rate": _r4(hits / len(addrs)), "touched_sets": touched}


def _sys_bankers(a: Dict[str, Any]) -> Dict[str, Any]:
    """bankers {allocation, max_claim, available, request?: {process, vector}}: the Banker's algorithm. Matrices are
    at most 12 processes x 8 resources of ints 0..10000 (checked by the practice type's own reader), max_claim >=
    allocation everywhere, available has one entry per resource. The safe sequence takes the lowest-index process
    that can finish first. Result: {need, safe, sequence ([] when unsafe), steps: [{process, need, work_before,
    work_after}] (when unsafe, the steps that could run before the search got stuck)}; with request, request_result:
    {granted, reason: ok|exceeds_need|must_wait|unsafe, state_after?: {allocation, available, need}} (the state
    after a granted request, to chain the next one)."""
    avail_m = practice_systems._int_matrix([a.get("available")] if isinstance(a.get("available"), list) else None)
    if not avail_m:
        raise _bad("available must be a list of 1 to 8 whole numbers from 0 to 10000.", "available")
    avail = avail_m[0]
    alloc = practice_systems._int_matrix(a.get("allocation"), cols=len(avail))
    if not alloc:
        raise _bad("allocation must be a matrix (up to 12 x 8) with one column per resource.", "allocation")
    claim = practice_systems._int_matrix(a.get("max_claim"), rows=len(alloc), cols=len(avail))
    if not claim:
        raise _bad("max_claim must have the same shape as allocation.", "max_claim")
    if any(claim[i][j] < alloc[i][j] for i in range(len(alloc)) for j in range(len(avail))):
        raise _bad("max_claim must be at least allocation everywhere.", "max_claim")

    def analyse(al: List[List[int]], av: List[int]):
        nd = [[claim[i][j] - al[i][j] for j in range(len(av))] for i in range(len(al))]
        work, done, seq, steps = list(av), [False] * len(al), [], []
        while len(seq) < len(al):
            for i in range(len(al)):
                if not done[i] and all(nd[i][j] <= work[j] for j in range(len(av))):
                    before = list(work)
                    work = [work[j] + al[i][j] for j in range(len(av))]
                    done[i] = True
                    seq.append(i)
                    steps.append({"process": i, "need": nd[i], "work_before": before, "work_after": list(work)})
                    break
            else:
                break
        return nd, len(seq) == len(al), seq, steps

    need, safe, seq, steps = analyse(alloc, avail)
    out: Dict[str, Any] = {"need": need, "safe": safe, "sequence": seq if safe else [], "steps": steps}
    req = a.get("request")
    if req is not None:
        req = _dict(req, "request")
        p = _int(req.get("process"), 0, len(alloc) - 1, "request.process")
        vec = [_int(v, 0, 10000, f"request.vector.{i}") for i, v in enumerate(_cap_list(req.get("vector"), "request.vector", 1, 8))]
        if len(vec) != len(avail):
            raise _bad("vector needs one entry per resource.", "request.vector")
        if any(vec[j] > need[p][j] for j in range(len(vec))):
            res: Dict[str, Any] = {"granted": False, "reason": "exceeds_need"}
        elif any(vec[j] > avail[j] for j in range(len(vec))):
            res = {"granted": False, "reason": "must_wait"}
        else:
            av2 = [avail[j] - vec[j] for j in range(len(vec))]
            al2 = [list(r) for r in alloc]
            al2[p] = [al2[p][j] + vec[j] for j in range(len(vec))]
            nd2, ok2, _, _ = analyse(al2, av2)
            res = ({"granted": True, "reason": "ok", "state_after": {"allocation": al2, "available": av2, "need": nd2}}
                   if ok2 else {"granted": False, "reason": "unsafe"})
        out["request_result"] = res
    return out


# ===================================================================== stats
def _norm_sf(x: float) -> float:
    return 0.5 * math.erfc(x / math.sqrt(2))


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 3e-16:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1 - math.exp(lbeta) * _betacf(b, a, 1 - x) / b


def _t_sf(t: float, df: float) -> float:
    """P(T > t) for Student's t with df degrees of freedom (a normal above 1e6)."""
    if df >= 1e6:
        return _norm_sf(t)
    tail = 0.5 * _betai(df / 2, 0.5, df / (df + t * t))
    return tail if t >= 0 else 1 - tail


def _stats_two_sample(a: Dict[str, Any]) -> Dict[str, Any]:
    """two_sample {test: z | welch | pooled, alternative: two_sided | less | greater, alpha = 0.05, mean1, sd1, n1,
    mean2, sd2, n2} or {x: [num], y: [num]} (2..1000 values each; sample means and sd with n - 1). n >= 2 (up to
    1e9), sd >= 0, the standard error must be above 0, alpha in (0, 0.5]. z uses the normal curve; welch uses
    Satterthwaite degrees of freedom; pooled uses n1 + n2 - 2; a t curve above 1e6 degrees of freedom is read as
    normal. p-values and critical values come from the normal (erfc) or t (incomplete beta) distribution, critical
    values by 80 bisection steps. p_value has 6 significant digits. Result: {statistic, df (null for z), p_value,
    critical (positive for two_sided, signed for one-sided), reject (p < alpha), ci: [lo, hi] (the difference of
    means, two-sided 1 - alpha), se, curve: [{x, y}] (101 points of the null density from -4.5 to 4.5)}."""
    test = a.get("test", "welch")
    if test not in ("z", "welch", "pooled"):
        raise _bad("test is z, welch or pooled.", "test")
    alt = a.get("alternative", "two_sided")
    if alt not in ("two_sided", "less", "greater"):
        raise _bad("alternative is two_sided, less or greater.", "alternative")
    alpha = _real(a.get("alpha", 0.05), "alpha", 0.0, 0.5)
    if alpha <= 0:
        raise _bad("alpha must be above 0.", "alpha")
    if a.get("x") is not None or a.get("y") is not None:
        def stats(v: Any, at: str) -> Tuple[float, float, int]:
            xs = [_real(t, f"{at}.{i}", -1e9, 1e9) for i, t in enumerate(_cap_list(v, at, 2, 1000))]
            m = math.fsum(xs) / len(xs)
            return m, math.sqrt(math.fsum((t - m) ** 2 for t in xs) / (len(xs) - 1)), len(xs)
        m1, s1, n1 = stats(a.get("x"), "x")
        m2, s2, n2 = stats(a.get("y"), "y")
    else:
        m1, m2 = _real(a.get("mean1"), "mean1"), _real(a.get("mean2"), "mean2")
        s1, s2 = _real(a.get("sd1"), "sd1", 0, 1e12), _real(a.get("sd2"), "sd2", 0, 1e12)
        n1, n2 = _int(a.get("n1"), 2, 10 ** 9, "n1"), _int(a.get("n2"), 2, 10 ** 9, "n2")
    v1, v2 = s1 * s1 / n1, s2 * s2 / n2
    if test == "pooled":
        df: Optional[float] = float(n1 + n2 - 2)
        sp2 = ((n1 - 1) * s1 * s1 + (n2 - 1) * s2 * s2) / df
        se = math.sqrt(sp2 * (1 / n1 + 1 / n2))
    else:
        se = math.sqrt(v1 + v2)
        df = None
        if test == "welch" and se > 0:
            df = (v1 + v2) ** 2 / (v1 * v1 / (n1 - 1) + v2 * v2 / (n2 - 1))
    if not se > 0 or not math.isfinite(se):
        raise _bad("The standard error is 0: the data have no spread.", "sd1")
    stat = (m1 - m2) / se
    sf = (lambda t: _norm_sf(t)) if df is None else (lambda t: _t_sf(t, df))
    if alt == "two_sided":
        p = min(1.0, 2 * sf(abs(stat)))
    elif alt == "less":
        p = sf(-stat)
    else:
        p = sf(stat)
    target = alpha / 2 if alt == "two_sided" else alpha

    def crit(tail: float) -> float:
        lo, hi = 0.0, 1.0
        for _ in range(60):
            if sf(hi) < tail:
                break
            hi *= 2
        for _ in range(80):
            mid = (lo + hi) / 2
            if sf(mid) > tail:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    c = crit(target)
    cc = c if alt != "less" else -c
    c2 = c if alt == "two_sided" else crit(alpha / 2)
    if df is None:
        curve = [(-4.5 + 9 * k / 100, math.exp(-0.5 * (-4.5 + 9 * k / 100) ** 2) / math.sqrt(2 * math.pi)) for k in range(101)]
    else:
        lc = math.lgamma((df + 1) / 2) - math.lgamma(df / 2) - 0.5 * math.log(df * math.pi)
        curve = [(x, math.exp(lc - (df + 1) / 2 * math.log1p(x * x / df))) for x in (-4.5 + 9 * k / 100 for k in range(101))]
    diff = m1 - m2
    return {"statistic": _r4(stat), "df": None if df is None else _r4(df), "p_value": _sig(p), "critical": _r4(cc),
            "reject": p < alpha, "ci": [_r4(diff - c2 * se), _r4(diff + c2 * se)], "se": _r4(se),
            "curve": [{"x": _r4(x), "y": _r4(y)} for x, y in curve]}


def _stats_markov(a: Dict[str, Any]) -> Dict[str, Any]:
    """markov {P: [[num]], start?: [num], steps = 20}: a finite Markov chain. P is n x n with n 2..10, entries in
    [0, 1], every row summing to 1 within 1e-9 (bad_args at "P.<row>"); rows are then rescaled to sum to exactly 1 in
    fractions. steps 0..100; start is a distribution (default state 0). The stationary distribution is solved exactly
    (pi(P - I) = 0, sum 1) when the chain has exactly one closed (recurrent) class, else it is null. Communicating
    classes are ordered by smallest state; period is the gcd of cycle lengths in a class (0 when the class has no
    cycle); aperiodic means every recurrent class has period 1. Result: {stationary: [{exact, value}] | null, unique,
    classes: [[state]], recurrent: [bool per class], absorbing: [state], period: [int per class], irreducible,
    aperiodic, distribution: [[num]] (steps + 1 rows, row 0 = start)}."""
    raw = _cap_list(a.get("P"), "P", 2, 10)
    n = len(raw)
    P: List[List[Fraction]] = []
    for i, r in enumerate(raw):
        r = _cap_list(r, f"P.{i}", 1, 10)
        if len(r) != n:
            raise _bad("P must be square.", f"P.{i}")
        vals = [_real(v, f"P.{i}.{j}", 0.0, 1.0) for j, v in enumerate(r)]
        if abs(math.fsum(vals) - 1) > 1e-9:
            raise _bad("Each row of P must sum to 1.", f"P.{i}")
        fr = [Fraction(str(v)) for v in r]
        tot = sum(fr)
        P.append([x / tot for x in fr])
    steps = _int(a.get("steps", 20), 0, 100, "steps")
    start = a.get("start")
    if start is None:
        dist = [1.0] + [0.0] * (n - 1)
    else:
        dist = [_real(v, f"start.{i}", 0.0, 1.0) for i, v in enumerate(_cap_list(start, "start", n, n))]
        if abs(math.fsum(dist) - 1) > 1e-9:
            raise _bad("start must sum to 1.", "start")
    edge = [[P[i][j] > 0 for j in range(n)] for i in range(n)]
    reach = [[edge[i][j] or i == j for j in range(n)] for i in range(n)]
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    if reach[k][j]:
                        reach[i][j] = True
    classes: List[List[int]] = []
    placed: set = set()
    for i in range(n):
        if i not in placed:
            cl = [j for j in range(n) if reach[i][j] and reach[j][i]]
            placed.update(cl)
            classes.append(cl)
    recurrent = [all(not edge[i][j] or j in cl for i in cl for j in range(n)) for cl in classes]
    absorbing = [i for i in range(n) if P[i][i] == 1]
    periods = []
    for cl in classes:
        level = {cl[0]: 0}
        queue = [cl[0]]
        for u in queue:
            for v in cl:
                if edge[u][v] and v not in level:
                    level[v] = level[u] + 1
                    queue.append(v)
        g = 0
        for u in cl:
            for v in cl:
                if edge[u][v]:
                    g = math.gcd(g, abs(level[u] + 1 - level[v]))
        periods.append(g)
    unique = sum(recurrent) == 1
    stationary = None
    if unique:
        M = [[P[j][i] - (1 if i == j else 0) for j in range(n)] + [Fraction(0)] for i in range(n)]
        M[n - 1] = [Fraction(1)] * n + [Fraction(1)]
        for col in range(n):
            piv = next((r for r in range(col, n) if M[r][col] != 0), None)
            if piv is None:
                raise ToolError("bad_input", "The stationary system could not be solved.")
            M[col], M[piv] = M[piv], M[col]
            for r in range(n):
                if r != col and M[r][col] != 0:
                    f = M[r][col] / M[col][col]
                    M[r] = [x - f * y for x, y in zip(M[r], M[col])]
        pi = [M[i][n] / M[i][i] for i in range(n)]
        stationary = [{"exact": _frac(x), "value": _r4(x)} for x in pi]
    Pf = [[float(x) for x in r] for r in P]
    rows_out, cur = [[_r4(v) for v in dist]], dist
    for _ in range(steps):
        cur = [sum(cur[i] * Pf[i][j] for i in range(n)) for j in range(n)]
        rows_out.append([_r4(v) for v in cur])
    return {"stationary": stationary, "unique": unique, "classes": classes, "recurrent": recurrent,
            "absorbing": absorbing, "period": periods, "irreducible": len(classes) == 1,
            "aperiodic": all(p == 1 for p, r in zip(periods, recurrent) if r), "distribution": rows_out}


# ===================================================================== bio
def _letters(v: Any, at: str, hi: int) -> str:
    s = "".join(_text(v, at, 10 * hi + 1000, required=True).split()).upper()
    if not s:
        raise _bad(f"{at} is empty.", at)
    if len(s) > hi:
        raise ToolError("too_large", f"{at} is longer than {hi} letters.", at)
    return s


def _bio_align(a: Dict[str, Any]) -> Dict[str, Any]:
    """align {seq1, seq2, mode: global | local, match = 2, mismatch = -1, gap = -2}: Needleman-Wunsch (global) or
    Smith-Waterman (local) with a linear gap. Letters A-Z only (case and spaces ignored), 1..300 each (too_large
    above); scores are whole numbers from -100 to 100 (mismatch and gap are given as negative numbers to penalise).
    Traceback ties prefer diagonal, then up (a gap in seq2), then left (a gap in seq1); a local alignment starts at
    the first best cell in row-major order. Result: {score, aligned1, aligned2, midline ("|" match, "." mismatch,
    " " gap), identity (matches over alignment columns), gaps, start: [i, j] and end: [i, j] (1-based residue
    positions of the first and last aligned columns; null for an empty local alignment), matrix (the (n+1) x (m+1)
    score table, only when both sequences have at most 12 letters), path: [[i, j]] (the table cells walked, from
    the start cell to the end cell)}."""
    s1, s2 = _letters(a.get("seq1"), "seq1", 300), _letters(a.get("seq2"), "seq2", 300)
    for at, s in (("seq1", s1), ("seq2", s2)):
        if any(not ("A" <= c <= "Z") for c in s):
            raise _bad("Use the letters A to Z only.", at)
    mode = a.get("mode", "global")
    if mode not in ("global", "local"):
        raise _bad("mode is global or local.", "mode")
    match, mis, gap = (_int(a.get(k, d), -100, 100, k) for k, d in (("match", 2), ("mismatch", -1), ("gap", -2)))
    n, m = len(s1), len(s2)
    local = mode == "local"
    H = [[0] * (m + 1) for _ in range(n + 1)]
    if not local:
        for i in range(1, n + 1):
            H[i][0] = i * gap
        for j in range(1, m + 1):
            H[0][j] = j * gap
    best, bi, bj = 0, 0, 0
    for i in range(1, n + 1):
        row, prev, c1 = H[i], H[i - 1], s1[i - 1]
        for j in range(1, m + 1):
            v = max(prev[j - 1] + (match if c1 == s2[j - 1] else mis), prev[j] + gap, row[j - 1] + gap)
            if local and v < 0:
                v = 0
            row[j] = v
            if local and v > best:
                best, bi, bj = v, i, j
    if local:
        i, j = bi, bj
    else:
        i, j = n, m
    end_i, end_j = i, j
    x1: List[str] = []
    x2: List[str] = []
    cells = [(i, j)]
    while (H[i][j] > 0) if local else (i > 0 or j > 0):
        sc = match if s1[i - 1] == s2[j - 1] else mis
        if i > 0 and j > 0 and H[i][j] == H[i - 1][j - 1] + sc:
            x1.append(s1[i - 1]); x2.append(s2[j - 1]); i -= 1; j -= 1
        elif i > 0 and H[i][j] == H[i - 1][j] + gap:
            x1.append(s1[i - 1]); x2.append("-"); i -= 1
        else:
            x1.append("-"); x2.append(s2[j - 1]); j -= 1
        cells.append((i, j))
    al1, al2 = "".join(reversed(x1)), "".join(reversed(x2))
    mid = "".join(" " if p == "-" or q == "-" else ("|" if p == q else ".") for p, q in zip(al1, al2))
    empty = not al1
    return {"score": H[n][m] if not local else best, "aligned1": al1, "aligned2": al2, "midline": mid,
            "identity": _r4(mid.count("|") / len(mid)) if mid else 0.0, "gaps": al1.count("-") + al2.count("-"),
            "start": None if empty else [i + 1, j + 1], "end": None if empty else [end_i, end_j],
            "matrix": H if n <= 12 and m <= 12 else None,
            "path": [] if empty else [list(c) for c in reversed(cells)]}


_COMP = {"A": "T", "C": "G", "G": "C", "T": "A"}


def _bio_orf(a: Dict[str, Any]) -> Dict[str, Any]:
    """orf {dna, min_codons = 10, strands: both | forward}: open reading frames. DNA is A, C, G, T (U read as T;
    case and spaces ignored), 3..20000 letters (too_large above); other letters are bad_args at "dna". min_codons
    1..1000 is the least number of amino acids (ATG included, stop left out). An ORF is ATG ... stop in one frame;
    per stop only the first ATG after the previous stop (the longest). Codons come from the standard table. Result:
    {frames: [{frame: "+1".."-3", protein}] (only when dna has at most 3000 letters; * marks a stop; forward frames
    first), orfs: [{frame, start, end, length_nt, protein}] (longest first, then smaller start; at most 100;
    length_nt counts the stop codon; start and end are 1-based on the given strand's forward coordinates and run
    from the A of ATG to the last base of the stop, so start > end on the minus strand), truncated}."""
    raw = a.get("dna")
    if not isinstance(raw, str):
        raise _bad("dna must be text.", "dna")
    if len(raw) > 200_000:
        raise ToolError("too_large", "dna is longer than 20000 letters.", "dna")
    dna = "".join(raw.split()).upper().replace("U", "T")
    if len(dna) > 20000:
        raise ToolError("too_large", "dna is longer than 20000 letters.", "dna")
    if len(dna) < 3 or any(c not in "ACGT" for c in dna):
        raise _bad("dna needs 3 to 20000 letters from A, C, G, T (or U).", "dna")
    min_c = _int(a.get("min_codons", 10), 1, 1000, "min_codons")
    strands = a.get("strands", "both")
    if strands not in ("both", "forward"):
        raise _bad("strands is both or forward.", "strands")
    L = len(dna)
    seqs = [("+", dna)]
    if strands == "both":
        seqs.append(("-", "".join(_COMP[c] for c in reversed(dna))))
    frames, orfs = [], []
    for sign, s in seqs:
        for f in range(3):
            prot = [practice_bio.CODON_TABLE[s[p:p + 3]] for p in range(f, L - 2, 3)]
            name = f"{sign}{f + 1}"
            if L <= 3000:
                frames.append({"frame": name, "protein": "".join(prot)})
            first = None
            for k, aa in enumerate(prot):
                if aa == "M" and first is None:
                    first = k
                elif aa == "*":
                    if first is not None and k - first >= min_c:
                        p0 = f + 3 * first
                        nt = 3 * (k - first + 1)
                        start, end = (p0 + 1, p0 + nt) if sign == "+" else (L - p0, L - p0 - nt + 1)
                        orfs.append({"frame": name, "start": start, "end": end, "length_nt": nt,
                                     "protein": "".join(prot[first:k])})
                    first = None
    orfs.sort(key=lambda o: (-o["length_nt"], min(o["start"], o["end"]), o["frame"]))
    return {"frames": frames, "orfs": orfs[:100], "truncated": len(orfs) > 100}


TOOLS: Dict[str, Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {
    "polity": {"allocate": _polity_allocate, "stv": _polity_stv, "irv": _polity_irv, "power": _polity_power},
    "music": {"lint": _music_lint, "tuning": _music_tuning},
    "classics": {"harris": _classics_harris, "leiden": _classics_leiden},
    "literature": {"scan": _lit_scan, "form": _lit_form},
    "rhetoric": {"toulmin": _rhet_toulmin, "appeals": _rhet_appeals},
    "ee": {"dc_solve": _ee_dc_solve, "bode": _ee_bode},
    "ai": {"metrics": _ai_metrics, "descent": _ai_descent},
    "systems": {"cache": _sys_cache, "bankers": _sys_bankers},
    "stats": {"two_sample": _stats_two_sample, "markov": _stats_markov},
    "bio": {"align": _bio_align, "orf": _bio_orf},
}


def run(kind: str, op: str, args: Any) -> Dict[str, Any]:
    """Runs one desk operation. Never raises."""
    try:
        fn = TOOLS.get(kind, {}).get(op) if isinstance(kind, str) and isinstance(op, str) else None
        if fn is None:
            raise ToolError("bad_op", "Unknown kit or operation.")
        if not isinstance(args, dict):
            raise ToolError("bad_args", "args must be an object.")
        try:
            size = len(json.dumps(args, allow_nan=False, ensure_ascii=False).encode("utf-8"))
        except ValueError:
            raise ToolError("bad_args", "args contain a number that is not finite.")
        except TypeError:
            raise ToolError("bad_args", "args must be plain JSON data.")
        if size > MAX_ARGS_BYTES:
            raise ToolError("too_large", f"args are larger than {MAX_ARGS_BYTES} bytes.")
        return {"ok": True, "result": fn(args)}
    except ToolError as e:
        return {"ok": False, "error": e.to_dict()}
    except (RecursionError, MemoryError):
        return {"ok": False, "error": {"code": "too_complex", "message": "The input is too complex."}}
    except Exception as e:  # noqa: BLE001 - run never raises
        return {"ok": False, "error": {"code": "bad_input", "message": f"Could not process the input ({type(e).__name__})."}}


def guide() -> Dict[str, Dict[str, str]]:
    return {k: {op: inspect.getdoc(fn) or "" for op, fn in ops.items()} for k, ops in TOOLS.items()}
