"""Deterministic desks for the liberal-arts kits (docs/plans/KIT_TOOLS_CONTRACT.md).

Stdlib only, no model calls, no network. `run(kind, op, args)` never raises: it answers {"ok": True, "result": ...} or
{"ok": False, "error": {"code", "message", "at"?}}. Domain outcomes (a cycle, an unbalanced bracket, a form mismatch)
are results, not errors. Floats are rounded to 4 places; exact values are fraction strings such as "7/30".
art_history has no server ops (its composition HUD runs in the browser)."""
import heapq
import inspect
import json
import math
import re
import unicodedata
from fractions import Fraction
from typing import Any, Callable, Dict, List, Optional, Tuple

import practice_classics
import practice_music
import practice_polity

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


TOOLS: Dict[str, Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]] = {
    "polity": {"allocate": _polity_allocate, "stv": _polity_stv, "irv": _polity_irv, "power": _polity_power},
    "music": {"lint": _music_lint, "tuning": _music_tuning},
    "classics": {"harris": _classics_harris, "leiden": _classics_leiden},
    "literature": {"scan": _lit_scan, "form": _lit_form},
    "rhetoric": {"toulmin": _rhet_toulmin, "appeals": _rhet_appeals},
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
