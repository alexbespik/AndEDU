"""
Polity / Political Science practice types: compute_dhondt, compute_shapley_shubik_pivotal, veto_pipeline, instant_runoff_tally.
Exports NORMALIZERS, GRADERS, and SECRET_FIELDS.
Standard library only.
"""
import itertools
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"solution", "pivotal_counts", "shapley_shubik_index", "winner", "elimination_order", "rounds"}


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


# ---- 1. compute_dhondt ----
def _calc_dhondt(votes: Dict[str, int], seats: int) -> Dict[str, int]:
    allocated = {p: 0 for p in votes}
    for _ in range(seats):
        best_party = None
        best_quotient = -1.0
        for p, v in votes.items():
            q = v / (allocated[p] + 1)
            # Tie breaking: highest initial vote, then alphabetical
            if q > best_quotient or (abs(q - best_quotient) < 1e-9 and votes[p] > votes.get(best_party or "", -1)):
                best_quotient = q
                best_party = p
        if best_party:
            allocated[best_party] += 1
    return allocated


def _np_compute_dhondt(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_votes = p.get("votes")
    seats = p.get("seats")
    if not isinstance(raw_votes, dict) or not raw_votes:
        return None
    try:
        seats_int = int(seats)
        if seats_int <= 0:
            return None
        votes = {str(k).strip(): int(v) for k, v in raw_votes.items() if int(v) >= 0}
    except (ValueError, TypeError):
        return None
    if not votes:
        return None

    solution = _calc_dhondt(votes, seats_int)
    return {
        **base,
        "votes": votes,
        "seats": seats_int,
        "solution": solution,
    }


def _grade_compute_dhondt(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("solution", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must map party names to allocated seat counts", "details": {}}

    sub_alloc = {}
    try:
        for k, v in submission.items():
            sub_alloc[str(k).strip()] = int(v)
    except (ValueError, TypeError):
        return {"ok": False, "score": 0.0, "feedback": "Seat counts must be integers", "details": {}}

    ok = (sub_alloc == expected)
    correct_seats = sum(min(sub_alloc.get(p, 0), exp_s) for p, exp_s in expected.items())
    total_seats = sum(expected.values())
    score = round(correct_seats / max(total_seats, 1), 2)
    return {
        "ok": ok,
        "score": 1.0 if ok else score,
        "feedback": "D'Hondt proportional representation seats calculated correctly!" if ok else f"Seat allocation differs: {correct_seats}/{total_seats} correct.",
        "details": {"submitted": sub_alloc, "solution": expected},
    }


# ---- 2. compute_shapley_shubik_pivotal ----
def _calc_shapley_shubik(quota: int, weights: Dict[str, int]) -> Tuple[Dict[str, int], Dict[str, float]]:
    voters = sorted(weights.keys())
    pivotal_counts = {v: 0 for v in voters}
    perms = list(itertools.permutations(voters))
    total_perms = len(perms)

    for perm in perms:
        cum = 0
        for v in perm:
            prev = cum
            cum += weights[v]
            if prev < quota <= cum:
                pivotal_counts[v] += 1
                break

    indices = {v: round(count / total_perms, 4) for v, count in pivotal_counts.items()}
    return pivotal_counts, indices


def _np_compute_shapley_shubik_pivotal(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    quota = p.get("quota")
    raw_weights = p.get("weights")
    if not isinstance(raw_weights, dict) or len(raw_weights) < 2 or len(raw_weights) > 8:
        return None
    try:
        q_int = int(quota)
        weights = {str(k).strip(): int(v) for k, v in raw_weights.items()}
    except (ValueError, TypeError):
        return None

    counts, indices = _calc_shapley_shubik(q_int, weights)
    return {
        **base,
        "quota": q_int,
        "weights": weights,
        "pivotal_counts": counts,
        "shapley_shubik_index": indices,
        "solution": indices,
    }


def _grade_compute_shapley_shubik_pivotal(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("shapley_shubik_index", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must map voters to power index values", "details": {}}

    diffs = []
    for v, exp_idx in expected.items():
        sub_val = submission.get(v)
        try:
            val_f = float(sub_val)
            diffs.append(abs(val_f - exp_idx))
        except (ValueError, TypeError):
            diffs.append(1.0)

    max_diff = max(diffs) if diffs else 1.0
    ok = (max_diff <= 0.05)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Shapley-Shubik voting power indices computed correctly!" if ok else "Voting power indices diverge from combinatorial pivot calculation.",
        "details": {"max_diff": round(max_diff, 4)},
    }


# ---- 3. veto_pipeline ----
def _np_veto_pipeline(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    players = p.get("veto_players")
    if not isinstance(players, list) or not players:
        return None
    will_pass = p.get("will_pass")
    if will_pass is None and p.get("solution") is not None:
        sol = p["solution"]
        if isinstance(sol, dict):
            will_pass = sol.get("will_pass")
    if will_pass is None:
        will_pass = True
    blocking = p.get("blocking_actor")
    return {
        **base,
        "bill": _s(p.get("bill") or "Legislation", 120),
        "veto_players": players,
        "will_pass": bool(will_pass),
        "blocking_actor": _s(blocking, 80) if blocking else None,
        "solution": {"will_pass": bool(will_pass), "blocking_actor": _s(blocking, 80) if blocking else None},
    }


def _grade_veto_pipeline(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("solution", {})
    exp_pass = expected.get("will_pass", True)
    exp_block = str(expected.get("blocking_actor") or "").strip().lower()

    sub_pass = None
    sub_block = ""
    if isinstance(submission, dict):
        sub_pass = submission.get("will_pass")
        sub_block = str(submission.get("blocking_actor") or "").strip().lower()
    elif isinstance(submission, bool):
        sub_pass = submission

    if sub_pass is None:
        return {"ok": False, "score": 0.0, "feedback": "Submission must specify will_pass (bool)", "details": {}}

    pass_ok = (bool(sub_pass) == exp_pass)
    if not exp_pass and exp_block:
        block_ok = (sub_block == exp_block)
        ok = pass_ok and block_ok
    else:
        ok = pass_ok

    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Legislative veto pipeline traced accurately!" if ok else "Incorrect veto player analysis.",
        "details": {"submitted": submission},
    }


# ---- 4. instant_runoff_tally ----
def _calc_irv(candidates: List[str], ballots: List[List[str]]) -> Tuple[List[Dict[str, int]], List[str], str]:
    active_cands = set(candidates)
    elimination_order: List[str] = []
    rounds: List[Dict[str, int]] = []

    while True:
        # Count top active candidate on each ballot
        tally: Dict[str, int] = {c: 0 for c in active_cands}
        valid_ballots = 0
        for b in ballots:
            for choice in b:
                if choice in active_cands:
                    tally[choice] += 1
                    valid_ballots += 1
                    break

        rounds.append(dict(tally))
        if valid_ballots == 0 or not active_cands:
            return rounds, elimination_order, ""

        # Check for majority winner
        for c, count in tally.items():
            if count > valid_ballots / 2:
                return rounds, elimination_order, c

        # If only 2 or 1 candidate left
        if len(active_cands) <= 2:
            sorted_by_votes = sorted(tally.items(), key=lambda x: x[1], reverse=True)
            winner = sorted_by_votes[0][0]
            return rounds, elimination_order, winner

        # Eliminate candidate with minimum votes
        min_votes = min(tally.values())
        lowest = [c for c, count in tally.items() if count == min_votes]
        # Tie breaker: alphabetical
        to_eliminate = sorted(lowest)[0]
        active_cands.remove(to_eliminate)
        elimination_order.append(to_eliminate)


def _np_instant_runoff_tally(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_ballots = p.get("ballots")
    raw_cands = p.get("candidates")
    if not isinstance(raw_ballots, list) or not raw_ballots:
        return None
    ballots = [[_s(x, 60) for x in b if _s(x, 60)] for b in raw_ballots if isinstance(b, list)]
    if not ballots:
        return None
    if not raw_cands:
        raw_cands = list(dict.fromkeys(c for b in ballots for c in b))
    candidates = [_s(x, 60) for x in raw_cands if _s(x, 60)]
    if len(candidates) < 2:
        return None

    rounds, elim, winner = _calc_irv(candidates, ballots)
    return {
        **base,
        "candidates": candidates,
        "ballots": ballots,
        "rounds": rounds,
        "elimination_order": elim,
        "winner": winner,
        "solution": {"winner": winner, "elimination_order": elim},
    }


def _grade_instant_runoff_tally(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected_winner = str(item.get("winner", "")).strip().lower()
    expected_elim = [x.strip().lower() for x in item.get("elimination_order", [])]

    sub_winner = ""
    sub_elim = []
    if isinstance(submission, dict):
        sub_winner = str(submission.get("winner") or "").strip().lower()
        sub_elim = [str(x).strip().lower() for x in submission.get("elimination_order", [])]
    else:
        sub_winner = str(submission or "").strip().lower()

    winner_ok = (sub_winner == expected_winner)
    elim_ok = (not sub_elim or sub_elim == expected_elim)
    ok = winner_ok and elim_ok

    return {
        "ok": ok,
        "score": 1.0 if ok else (0.5 if winner_ok else 0.0),
        "feedback": f"Instant-runoff voting rounds tallies correct: {item.get('winner')} elected!" if ok else "Ranked-choice / IRV elimination tally differs.",
        "details": {"submitted_winner": sub_winner, "expected_winner": item.get("winner")},
    }


NORMALIZERS = {
    "compute_dhondt": _np_compute_dhondt,
    "compute_shapley_shubik_pivotal": _np_compute_shapley_shubik_pivotal,
    "veto_pipeline": _np_veto_pipeline,
    "instant_runoff_tally": _np_instant_runoff_tally,
}

GRADERS = {
    "compute_dhondt": _grade_compute_dhondt,
    "compute_shapley_shubik_pivotal": _grade_compute_shapley_shubik_pivotal,
    "veto_pipeline": _grade_veto_pipeline,
    "instant_runoff_tally": _grade_instant_runoff_tally,
}
