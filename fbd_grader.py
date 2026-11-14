"""
Deterministic Free-Body Diagram (FBD) Grader for &.edu.
Pure standard library only (math, re, typing, dataclasses).

Evaluates vector scene graphs constructed by DrawingBoard:
- Extracts vector arrows and text label associations
- Computes screen-to-Cartesian angles: theta = atan2(-(y2 - y1), x2 - x1) * 180 / pi (mod 360)
- Validates origin attachment against body_origin within origin_tol_px
- Matches targets by angle within angle_tol_deg and aliases
- Compares relative vector magnitudes (eq, gt, lt) within ratio_tol
- Detects and rejects forbidden forces (e.g. centrifugal, ma, inertia, motion)
"""
from dataclasses import dataclass
import math
import re
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ExtractedVector:
    id: Any
    x1: float
    y1: float
    x2: float
    y2: float
    angle_deg: float
    length: float
    label: str
    normalized_label: str


def normalize_label(text: Any) -> str:
    """Normalizes label text: lowercases, removes LaTeX wrappers, spaces and punctuation."""
    if text is None:
        return ""
    s = str(text).lower().strip()
    s = re.sub(r"\\[a-zA-Z]+", "", s)  # strip LaTeX commands like \vec, \text
    s = re.sub(r"[{}\[\]()_$^`'\"~=+\-*\/]", "", s)
    s = re.sub(r"\s+", "", s)
    return s


def cartesian_angle(x1: float, y1: float, x2: float, y2: float) -> float:
    """Computes Cartesian angle in degrees in [0, 360) from SVG/screen coordinates where y increases downwards."""
    dx = x2 - x1
    dy_math = -(y2 - y1)
    rad = math.atan2(dy_math, dx)
    deg = math.degrees(rad) % 360.0
    return deg


def angle_diff(a: float, b: float) -> float:
    """Shortest angular distance between two angles in degrees [0, 180]."""
    diff = abs((a - b + 180.0) % 360.0 - 180.0)
    return diff


def point_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def extract_vectors(shapes: List[Dict[str, Any]]) -> Tuple[List[ExtractedVector], List[str]]:
    """Separates arrows and text labels, associating nearby text labels with arrow tips or midpoints."""
    safe_shapes = [s for s in (shapes or []) if isinstance(s, dict)][:200]
    arrows = [s for s in safe_shapes if s.get("type") == "arrow"][:60]
    texts = [s for s in safe_shapes if s.get("type") == "text" and s.get("text")][:60]

    all_text_labels = [str(t.get("text", "")).strip() for t in texts if str(t.get("text", "")).strip()]
    extracted: List[ExtractedVector] = []

    for idx, arr in enumerate(arrows):
        try:
            x1 = float(arr.get("x1", 0))
            y1 = float(arr.get("y1", 0))
            x2 = float(arr.get("x2", 0))
            y2 = float(arr.get("y2", 0))
        except (ValueError, TypeError):
            continue

        length = point_distance(x1, y1, x2, y2)
        if length < 5.0:
            continue  # ignore accidental zero-length clicks

        angle = cartesian_angle(x1, y1, x2, y2)
        mid_x, mid_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0

        # Find closest text label within 60 px of tip or midpoint
        best_label = ""
        best_dist = 60.0
        for t in texts:
            try:
                tx = float(t.get("x1", 0))
                ty = float(t.get("y1", 0))
                raw_txt = str(t.get("text", "")).strip()
            except (ValueError, TypeError):
                continue
            dist_tip = point_distance(tx, ty, x2, y2)
            dist_mid = point_distance(tx, ty, mid_x, mid_y)
            d = min(dist_tip, dist_mid)
            if d < best_dist:
                best_dist = d
                best_label = raw_txt

        raw_id = arr.get("id")
        # Ensure ID is hashable and unique
        vec_id = raw_id if isinstance(raw_id, (int, str)) else f"vec_{idx}"

        extracted.append(ExtractedVector(
            id=vec_id,
            x1=x1, y1=y1, x2=x2, y2=y2,
            angle_deg=angle,
            length=length,
            label=best_label,
            normalized_label=normalize_label(best_label)
        ))

    return extracted, all_text_labels


def grade_fbd(shapes: List[Dict[str, Any]], fbd_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates a free-body diagram vector scene graph deterministically against an fbd_spec.
    Returns:
      {
        "score": float,         # 0.0 to 1.0
        "passed": bool,         # score >= 0.75
        "criteria": List[dict], # [{"criterion": str, "met": bool, "comment": str}]
        "feedback": str,        # Pedagogical explanation
        "describe": str,        # Scene summary
        "deterministic": True
      }
    """
    if not isinstance(fbd_spec, dict):
        return {
            "score": 0.0,
            "passed": False,
            "criteria": [{"criterion": "FBD Specification", "met": False, "comment": "Invalid fbd_spec"}],
            "feedback": "No valid Free-Body Diagram specification was provided for grading.",
            "describe": "Drawing evaluation failed: specification missing.",
            "deterministic": True,
        }

    vectors, all_texts = extract_vectors(shapes or [])
    criteria_results: List[Dict[str, Any]] = []

    body_origin = fbd_spec.get("body_origin")
    if isinstance(body_origin, (list, tuple)) and len(body_origin) >= 2:
        try:
            origin_x, origin_y = float(body_origin[0]), float(body_origin[1])
        except (ValueError, TypeError):
            origin_x, origin_y = 500.0, 310.0
    else:
        origin_x, origin_y = 500.0, 310.0

    try:
        origin_tol = float(fbd_spec.get("origin_tol_px", 50.0))
    except (ValueError, TypeError):
        origin_tol = 50.0

    # 1. Guard against forbidden forces (e.g. centrifugal, ma, inertia)
    raw_forbidden = fbd_spec.get("forbidden_forces", [])
    forbidden_list = [str(f) for f in raw_forbidden] if isinstance(raw_forbidden, (list, tuple)) else []
    found_forbidden = []
    all_normalized_texts = [normalize_label(t) for t in all_texts]
    for forbidden in forbidden_list:
        norm_forbid = normalize_label(forbidden)
        if not norm_forbid:
            continue
        for nt in all_normalized_texts:
            if not nt:
                continue
            if norm_forbid == nt or (len(norm_forbid) >= 3 and norm_forbid in nt):
                found_forbidden.append(forbidden)
                break

    if forbidden_list:
        if found_forbidden:
            criteria_results.append({
                "criterion": "No unphysical or pseudo-forces included",
                "met": False,
                "comment": f"Forbidden force detected: {', '.join(found_forbidden)}"
            })
        else:
            criteria_results.append({
                "criterion": "No unphysical or pseudo-forces included",
                "met": True,
                "comment": "Free of non-inertial or pseudo-force labels"
            })

    if not vectors:
        criteria_results.append({
            "criterion": "Draw vector force arrows",
            "met": False,
            "comment": "No force vector arrows found in drawing"
        })
        return {
            "score": 0.0,
            "passed": False,
            "criteria": criteria_results,
            "feedback": "Draw force arrows starting from the object center of mass or contact surface.",
            "describe": "Empty or non-vector diagram.",
            "deterministic": True,
        }

    # 2. Check origin attachment for vectors
    origins_ok = True
    misplaced_tails = 0
    for v in vectors:
        dist_origin = point_distance(v.x1, v.y1, origin_x, origin_y)
        if dist_origin > origin_tol:
            origins_ok = False
            misplaced_tails += 1

    criteria_results.append({
        "criterion": "Forces originate from body center/origin",
        "met": origins_ok,
        "comment": "All force tails anchored near origin" if origins_ok else f"{misplaced_tails} force arrow(s) detached from body center"
    })

    # 3. Match Target Vectors
    raw_targets = fbd_spec.get("targets", [])
    targets = [t for t in raw_targets if isinstance(t, dict)] if isinstance(raw_targets, (list, tuple)) else []
    matched_vectors: Dict[str, ExtractedVector] = {}
    used_vector_ids = set()
    has_unmet_required = False

    for target in targets:
        name = str(target.get("name", "force"))
        raw_aliases = target.get("aliases", [])
        aliases_list = [str(a) for a in raw_aliases] if isinstance(raw_aliases, (list, tuple)) else []
        aliases = [normalize_label(a) for a in aliases_list] + [normalize_label(name)]
        try:
            expected_angle = float(target.get("angle_deg", 0.0))
        except (ValueError, TypeError):
            expected_angle = 0.0
        try:
            angle_tol = float(target.get("angle_tol_deg", 10.0))
        except (ValueError, TypeError):
            angle_tol = 10.0
        required = bool(target.get("required", True))

        best_match: Optional[ExtractedVector] = None
        best_diff = 999.0

        for v in vectors:
            if v.id in used_vector_ids:
                continue
            diff = angle_diff(v.angle_deg, expected_angle)
            if diff <= angle_tol:
                # If aliases specified, prefer vector whose label matches
                has_label_match = v.normalized_label and any(
                    a == v.normalized_label or (len(a) >= 2 and a in v.normalized_label) or (len(v.normalized_label) >= 2 and v.normalized_label in a)
                    for a in aliases if a
                )
                if has_label_match:
                    diff -= 0.1  # boost labeled vectors
                if diff < best_diff:
                    best_diff = diff
                    best_match = v

        if best_match is not None and best_diff <= angle_tol:
            matched_vectors[name] = best_match
            used_vector_ids.add(best_match.id)
            label_note = f" labeled '{best_match.label}'" if best_match.label else ""
            criteria_results.append({
                "criterion": f"Direction of {name} force ({expected_angle:.0f}°)",
                "met": True,
                "comment": f"Found vector at {best_match.angle_deg:.1f}° (expected {expected_angle:.0f}°){label_note}"
            })
        else:
            if required:
                has_unmet_required = True
            criteria_results.append({
                "criterion": f"Direction of {name} force ({expected_angle:.0f}°)",
                "met": not required,
                "comment": f"Missing or misdirected vector (expected {expected_angle:.0f}° ± {angle_tol:.0f}°)"
            })

    # 4. Magnitude Comparisons
    raw_mag_comps = fbd_spec.get("magnitude_comparisons", [])
    mag_comps = [m for m in raw_mag_comps if isinstance(m, dict)] if isinstance(raw_mag_comps, (list, tuple)) else []
    for comp in mag_comps:
        vec_a_name = str(comp.get("vector_a") or "")
        vec_b_name = str(comp.get("vector_b") or "")
        op = comp.get("op", "eq")  # eq, gt, lt
        try:
            ratio_tol = float(comp.get("ratio_tol", 0.25))
        except (ValueError, TypeError):
            ratio_tol = 0.25

        va = matched_vectors.get(vec_a_name)
        vb = matched_vectors.get(vec_b_name)

        comp_label = f"Relative magnitude: |{vec_a_name}| {op} |{vec_b_name}|"

        if not va or not vb:
            criteria_results.append({
                "criterion": comp_label,
                "met": False,
                "comment": f"Cannot compare: missing {vec_a_name if not va else vec_b_name}"
            })
            continue

        la, lb = va.length, vb.length
        met = False
        comment = ""

        if op == "eq":
            max_len = max(la, lb)
            ratio_diff = abs(la - lb) / max_len if max_len > 0 else 0.0
            met = ratio_diff <= ratio_tol
            comment = f"Lengths {la:.0f}px vs {lb:.0f}px (diff {ratio_diff*100:.1f}%, tol {ratio_tol*100:.0f}%)"
        elif op == "gt":
            # Must strictly be greater and visibly distinct (at least 5% longer or exceeds ratio_tol)
            met = la > lb and (la >= lb * (1.0 + min(0.05, ratio_tol)))
            comment = f"{vec_a_name} ({la:.0f}px) > {vec_b_name} ({lb:.0f}px)" if met else f"{vec_a_name} ({la:.0f}px) is not longer than {vec_b_name} ({lb:.0f}px)"
        elif op == "lt":
            # Must strictly be shorter and visibly distinct
            met = la < lb and (la <= lb * (1.0 - min(0.05, ratio_tol)))
            comment = f"{vec_a_name} ({la:.0f}px) < {vec_b_name} ({lb:.0f}px)" if met else f"{vec_a_name} ({la:.0f}px) is not shorter than {vec_b_name} ({lb:.0f}px)"

        criteria_results.append({
            "criterion": comp_label,
            "met": met,
            "comment": comment
        })

    # 5. Score calculation
    total_criteria = len(criteria_results)
    met_count = sum(1 for c in criteria_results if c.get("met") is True)
    score = round(met_count / total_criteria, 3) if total_criteria > 0 else 0.0
    passed = (score >= 0.75) and not bool(found_forbidden) and not has_unmet_required and len(targets) > 0

    # 6. Socratic Feedback Generation
    if passed:
        feedback = "Correct free-body diagram. The force directions, anchors, and relative magnitudes accurately balance according to Newtonian principles."
    else:
        unmet = [c for c in criteria_results if not c.get("met")]
        first_issue = unmet[0]["comment"] if unmet else "Check your vector orientations and magnitudes."
        feedback = f"Review your free-body diagram: {first_issue}. Ensure all vectors start at the body origin with balanced lengths."

    describe = f"Free-body diagram containing {len(vectors)} vector force(s); {len(matched_vectors)} target force(s) identified."

    return {
        "score": score,
        "passed": passed,
        "criteria": criteria_results,
        "feedback": feedback,
        "describe": describe,
        "deterministic": True,
    }
