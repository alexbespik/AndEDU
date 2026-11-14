"""
Probability & Mathematical Statistics practice types:
- hypothesis_test_two_sample: Two-sample difference of means test statistic and rejection decision
- bayes_posterior_update: Prior, likelihood, and normalized posterior probability
- mle_parameter_derivation: Analytical Maximum Likelihood Estimator calculation from sample data
- markov_steady_state: Discrete-time Markov chain stationary distribution vector

Exports NORMALIZERS, GRADERS, and SECRET_FIELDS. Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"expected", "solution", "statistic_expected", "reject_null_expected", "posterior_expected", "mle_expected", "steady_state_expected"}


def _s(v: Any, limit: int = 500) -> str:
    return str(v if v is not None else "").strip()[:limit]


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        val = float(v)
        return val if math.isfinite(val) else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. hypothesis_test_two_sample
# ---------------------------------------------------------------------------
def _np_hypothesis_test_two_sample(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    m1 = _num(p.get("mean1"))
    s1 = _num(p.get("std1"))
    n1 = int(_num(p.get("n1")) or 0)
    m2 = _num(p.get("mean2"))
    s2 = _num(p.get("std2"))
    n2 = int(_num(p.get("n2")) or 0)
    alpha = _num(p.get("alpha")) or 0.05

    if None in (m1, s1, m2, s2) or n1 <= 1 or n2 <= 1:
        return None

    # Two-sample z-test statistic: (m1 - m2) / sqrt(s1^2/n1 + s2^2/n2)
    se = math.sqrt((s1 ** 2) / n1 + (s2 ** 2) / n2)
    if se <= 0:
        return None
    z_stat = (m1 - m2) / se
    crit_z = 1.96 if abs(alpha - 0.05) < 0.01 else (2.576 if abs(alpha - 0.01) < 0.005 else 1.645)
    reject_null = abs(z_stat) > crit_z

    return {
        **base,
        "mean1": m1, "std1": s1, "n1": n1,
        "mean2": m2, "std2": s2, "n2": n2,
        "alpha": alpha,
        "statistic_expected": round(z_stat, 4),
        "reject_null_expected": reject_null,
    }


def _grade_hypothesis_test_two_sample(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Must submit test_statistic and reject_null.", "details": {}}

    exp_z = _num(item.get("statistic_expected"))
    exp_rej = item.get("reject_null_expected")
    sub_z = _num(submission.get("test_statistic"))
    sub_rej = bool(submission.get("reject_null"))

    z_ok = sub_z is not None and abs(sub_z - exp_z) <= 0.08
    rej_ok = (sub_rej == exp_rej)

    score = (0.5 if z_ok else 0.0) + (0.5 if rej_ok else 0.0)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Hypothesis test verified!" if ok else f"Discrepancy (stat_match={z_ok}, decision_match={rej_ok}).",
        "details": {"expected_z": exp_z, "expected_reject": exp_rej},
    }


# ---------------------------------------------------------------------------
# 2. bayes_posterior_update
# ---------------------------------------------------------------------------
def _np_bayes_posterior_update(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    prior = _num(p.get("prior"))  # P(H)
    sensitivity = _num(p.get("sensitivity") or p.get("p_e_given_h"))  # P(E|H)
    fpr = _num(p.get("false_positive_rate") or p.get("p_e_given_not_h"))  # P(E|~H)

    if prior is None or sensitivity is None or fpr is None:
        return None

    # P(H|E) = (P(E|H) * P(H)) / (P(E|H)*P(H) + P(E|~H)*P(~H))
    num = sensitivity * prior
    denom = num + fpr * (1.0 - prior)
    if denom <= 0:
        return None
    post = num / denom

    return {
        **base,
        "prior": prior,
        "sensitivity": sensitivity,
        "false_positive_rate": fpr,
        "posterior_expected": round(post, 4),
    }


def _grade_bayes_posterior_update(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = _num(item.get("posterior_expected"))
    user_val = _num(submission.get("posterior") if isinstance(submission, dict) else submission)

    if expected is None or user_val is None:
        return {"ok": False, "score": 0.0, "feedback": "Must submit posterior probability.", "details": {}}

    diff = abs(user_val - expected)
    ok = (diff <= 0.02)
    score = 1.0 if ok else max(0.0, round(1.0 - (diff / 0.1), 2))
    return {
        "ok": ok,
        "score": score,
        "feedback": f"Bayesian posterior {round(user_val, 4)} confirmed!" if ok else f"Posterior calculation error (expected ~{expected}).",
        "details": {"submitted": user_val, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 3. mle_parameter_derivation
# ---------------------------------------------------------------------------
def _np_mle_parameter_derivation(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    dist = _s(p.get("distribution") or "exponential", 50).lower()
    samples = p.get("samples")
    if not isinstance(samples, list) or not samples:
        return None

    clean_samples = [_num(x) for x in samples if _num(x) is not None]
    if not clean_samples:
        return None

    n = len(clean_samples)
    mean_val = sum(clean_samples) / n

    if dist == "exponential":
        mle = 1.0 / mean_val if mean_val > 0 else 0.0
    elif dist in ("bernoulli", "poisson", "normal_mean"):
        mle = mean_val
    else:
        mle = mean_val

    return {
        **base,
        "distribution": dist,
        "samples": clean_samples,
        "mle_expected": round(mle, 4),
    }


def _grade_mle_parameter_derivation(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = _num(item.get("mle_expected"))
    user_val = _num(submission.get("estimate") if isinstance(submission, dict) else submission)

    if expected is None or user_val is None:
        return {"ok": False, "score": 0.0, "feedback": "Must submit parameter estimate.", "details": {}}

    diff = abs(user_val - expected)
    ok = (diff <= 0.03)
    score = 1.0 if ok else max(0.0, round(1.0 - (diff / 0.2), 2))
    return {
        "ok": ok,
        "score": score,
        "feedback": "Maximum likelihood estimate verified!" if ok else f"Mismatch in MLE estimate (expected ~{expected}).",
        "details": {"submitted": user_val, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 4. markov_steady_state
# ---------------------------------------------------------------------------
def _np_markov_steady_state(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # 2x2 Markov transition matrix [[1-a, a], [b, 1-b]]
    # Stationary distribution: pi_1 = b / (a + b), pi_2 = a / (a + b)
    a = _num(p.get("alpha"))
    b = _num(p.get("beta"))
    if a is None or b is None or (a + b) <= 0:
        return None

    pi1 = b / (a + b)
    pi2 = a / (a + b)

    return {
        **base,
        "transition_matrix": [
            [round(1.0 - a, 4), round(a, 4)],
            [round(b, 4), round(1.0 - b, 4)],
        ],
        "steady_state_expected": [round(pi1, 4), round(pi2, 4)],
    }


def _grade_markov_steady_state(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("steady_state_expected", [])
    user_vec = submission.get("steady_state") if isinstance(submission, dict) else submission

    if not isinstance(user_vec, list) or len(user_vec) != len(expected):
        return {"ok": False, "score": 0.0, "feedback": "Must submit stationary distribution vector.", "details": {}}

    ok = all(abs(float(user_vec[i]) - expected[i]) <= 0.03 for i in range(len(expected)))
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": "Stationary distribution confirmed!" if ok else "Stationary vector does not satisfy pi * P = pi.",
        "details": {"submitted": user_vec, "expected": expected},
    }


NORMALIZERS = {
    "hypothesis_test_two_sample": _np_hypothesis_test_two_sample,
    "bayes_posterior_update": _np_bayes_posterior_update,
    "mle_parameter_derivation": _np_mle_parameter_derivation,
    "markov_steady_state": _np_markov_steady_state,
}

GRADERS = {
    "hypothesis_test_two_sample": _grade_hypothesis_test_two_sample,
    "bayes_posterior_update": _grade_bayes_posterior_update,
    "mle_parameter_derivation": _grade_mle_parameter_derivation,
    "markov_steady_state": _grade_markov_steady_state,
}
