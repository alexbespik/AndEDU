"""
Machine Learning & AI practice types:
- backprop_layer_step: Analytical matrix gradient computation and delta propagation
- attention_score_matrix: Scaled dot-product attention softmax weight calculation
- confusion_matrix_metrics: Classification metrics (Precision, Recall, F1, Specificity)
- loss_gradient_verify: Cross-entropy and MSE loss & analytical gradient calculation

Exports NORMALIZERS, GRADERS, and SECRET_FIELDS. Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"expected", "solution", "grad_W", "grad_b", "attention_weights", "metrics", "loss_expected", "grad_expected"}


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
# 1. backprop_layer_step
# ---------------------------------------------------------------------------
def _np_backprop_layer_step(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    x = p.get("X")  # input vector/matrix
    delta = p.get("delta")  # incoming upstream gradient dL/dz
    if not isinstance(x, list) or not isinstance(delta, list):
        return None

    # Compute expected grad_W = delta^T * X or outer product for vectors
    try:
        if isinstance(x[0], (int, float)) and isinstance(delta[0], (int, float)):
            # 1D outer product: (len(delta), len(x))
            grad_w = [[round(d * xi, 4) for xi in x] for d in delta]
            grad_b = [round(float(d), 4) for d in delta]
        else:
            return None
    except Exception:
        return None

    return {
        **base,
        "X": x,
        "delta": delta,
        "activation": _s(p.get("activation") or "linear", 50),
        "grad_W": grad_w,
        "grad_b": grad_b,
    }


def _grade_backprop_layer_step(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Submission must provide grad_W and grad_b.", "details": {}}

    exp_w = item.get("grad_W", [])
    exp_b = item.get("grad_b", [])
    sub_w = submission.get("grad_W")
    sub_b = submission.get("grad_b")

    if not isinstance(sub_w, list) or not isinstance(sub_b, list):
        return {"ok": False, "score": 0.0, "feedback": "grad_W and grad_b must be lists.", "details": {}}

    correct_cells = 0
    total_cells = 0

    # Check grad_W
    for r in range(len(exp_w)):
        for c in range(len(exp_w[r])):
            total_cells += 1
            try:
                if abs(float(sub_w[r][c]) - exp_w[r][c]) < 0.02:
                    correct_cells += 1
            except (IndexError, TypeError, ValueError):
                pass

    # Check grad_b
    for i in range(len(exp_b)):
        total_cells += 1
        try:
            if abs(float(sub_b[i]) - exp_b[i]) < 0.02:
                correct_cells += 1
        except (IndexError, TypeError, ValueError):
            pass

    score = round(correct_cells / max(1, total_cells), 2)
    ok = (score >= 0.95)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Backprop gradient step verified!" if ok else f"Gradient elements off ({correct_cells}/{total_cells} matched).",
        "details": {"score": score},
    }


# ---------------------------------------------------------------------------
# 2. attention_score_matrix
# ---------------------------------------------------------------------------
def _np_attention_score_matrix(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    q = p.get("Q")  # shape (seq, d_k)
    k = p.get("K")  # shape (seq, d_k)
    if not isinstance(q, list) or not isinstance(k, list) or not q or not k:
        return None

    try:
        dk = len(q[0])
        scale = math.sqrt(dk)
        seq_len = len(q)
        scores = []
        for i in range(seq_len):
            row = []
            for j in range(len(k)):
                dot = sum(q[i][d] * k[j][d] for d in range(dk))
                row.append(dot / scale)
            scores.append(row)

        # Softmax along each row
        weights = []
        for row in scores:
            max_val = max(row)
            exps = [math.exp(val - max_val) for val in row]
            sum_exp = sum(exps)
            weights.append([round(e / sum_exp, 4) for e in exps])
    except Exception:
        return None

    return {
        **base,
        "Q": q,
        "K": k,
        "d_k": dk,
        "attention_weights": weights,
    }


def _grade_attention_score_matrix(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("attention_weights", [])
    user_matrix = submission.get("weights") if isinstance(submission, dict) else submission

    if not isinstance(user_matrix, list):
        return {"ok": False, "score": 0.0, "feedback": "Must submit weights matrix.", "details": {}}

    correct = 0
    total = 0
    for r in range(len(expected)):
        for c in range(len(expected[r])):
            total += 1
            try:
                if abs(float(user_matrix[r][c]) - expected[r][c]) <= 0.03:
                    correct += 1
            except Exception:
                pass

    score = round(correct / max(1, total), 2)
    ok = (score >= 0.9)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Attention matrix calculated accurately!" if ok else f"Mismatch in attention weights ({correct}/{total} accurate).",
        "details": {"score": score},
    }


# ---------------------------------------------------------------------------
# 3. confusion_matrix_metrics
# ---------------------------------------------------------------------------
def _np_confusion_matrix_metrics(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tp = _num(p.get("TP") or p.get("tp"))
    fp = _num(p.get("FP") or p.get("fp"))
    fn = _num(p.get("FN") or p.get("fn"))
    tn = _num(p.get("TN") or p.get("tn"))
    if None in (tp, fp, fn, tn):
        return None

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    return {
        **base,
        "TP": int(tp), "FP": int(fp), "FN": int(fn), "TN": int(tn),
        "metrics": {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "specificity": round(spec, 4),
        },
    }


def _grade_confusion_matrix_metrics(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("metrics", {})
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Must submit metrics object (precision, recall, f1).", "details": {}}

    matched = 0
    total = len(expected)
    for k, exp_val in expected.items():
        sub_val = _num(submission.get(k))
        if sub_val is not None and abs(sub_val - exp_val) <= 0.02:
            matched += 1

    score = round(matched / max(1, total), 2)
    ok = (score >= 0.75)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Classification metrics verified!" if ok else f"Some metrics mismatched ({matched}/{total} correct).",
        "details": {"matched": matched, "total": total},
    }


# ---------------------------------------------------------------------------
# 4. loss_gradient_verify
# ---------------------------------------------------------------------------
def _np_loss_gradient_verify(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    loss_type = _s(p.get("loss_type") or "cross_entropy", 50).lower()
    y_true = _num(p.get("y_true"))
    y_pred = _num(p.get("y_pred"))
    if y_true is None or y_pred is None:
        return None

    if loss_type == "cross_entropy":
        # Binary cross entropy L = -(y log(p) + (1-y) log(1-p))
        eps = 1e-12
        p_c = max(eps, min(1.0 - eps, y_pred))
        loss = -(y_true * math.log(p_c) + (1.0 - y_true) * math.log(1.0 - p_c))
        grad = p_c - y_true
    else:  # MSE: 0.5 * (y_pred - y_true)^2
        loss = 0.5 * (y_pred - y_true) ** 2
        grad = y_pred - y_true

    return {
        **base,
        "loss_type": loss_type,
        "y_true": y_true,
        "y_pred": y_pred,
        "loss_expected": round(loss, 4),
        "grad_expected": round(grad, 4),
    }


def _grade_loss_gradient_verify(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    if not isinstance(submission, dict):
        return {"ok": False, "score": 0.0, "feedback": "Must submit loss and grad values.", "details": {}}

    sub_l = _num(submission.get("loss"))
    sub_g = _num(submission.get("grad"))
    exp_l = _num(item.get("loss_expected"))
    exp_g = _num(item.get("grad_expected"))

    ok_l = sub_l is not None and abs(sub_l - exp_l) <= 0.05
    ok_g = sub_g is not None and abs(sub_g - exp_g) <= 0.05

    score = (0.5 if ok_l else 0.0) + (0.5 if ok_g else 0.0)
    ok = (score == 1.0)
    return {
        "ok": ok,
        "score": score,
        "feedback": "Loss & analytical gradient match!" if ok else "Loss or gradient discrepancy detected.",
        "details": {"loss_match": ok_l, "grad_match": ok_g},
    }


NORMALIZERS = {
    "backprop_layer_step": _np_backprop_layer_step,
    "attention_score_matrix": _np_attention_score_matrix,
    "confusion_matrix_metrics": _np_confusion_matrix_metrics,
    "loss_gradient_verify": _np_loss_gradient_verify,
}

GRADERS = {
    "backprop_layer_step": _grade_backprop_layer_step,
    "attention_score_matrix": _grade_attention_score_matrix,
    "confusion_matrix_metrics": _grade_confusion_matrix_metrics,
    "loss_gradient_verify": _grade_loss_gradient_verify,
}
