"""
Bioinformatics & Computational Biology practice types:
- smith_waterman_align: Dynamic programming local sequence alignment score
- orf_finder_translate: Open Reading Frame identification and codon translation
- restriction_digest_mapper: Plasmid and linear DNA restriction enzyme fragment sizing
- phylogenetic_upgma_step: UPGMA distance matrix hierarchical clustering step

Exports NORMALIZERS, GRADERS, and SECRET_FIELDS. Standard library only.
"""
import math
from typing import Any, Dict, List, Optional, Set, Tuple

SECRET_FIELDS: Set[str] = {"expected", "solution", "max_score", "protein_sequence", "fragment_sizes", "merged_cluster", "updated_distances", "merged_pair"}

CODON_TABLE: Dict[str, str] = {
    "ATA": "I", "ATC": "I", "ATT": "I", "ATG": "M",
    "ACA": "T", "ACC": "T", "ACG": "T", "ACT": "T",
    "AAC": "N", "AAT": "N", "AAA": "K", "AAG": "K",
    "AGC": "S", "AGT": "S", "AGA": "R", "AGG": "R",
    "CTA": "L", "CTC": "L", "CTG": "L", "CTT": "L",
    "CCA": "P", "CCC": "P", "CCG": "P", "CCT": "P",
    "CAC": "H", "CAT": "H", "CAA": "Q", "CAG": "Q",
    "CGA": "R", "CGC": "R", "CGG": "R", "CGT": "R",
    "GTA": "V", "GTC": "V", "GTG": "V", "GTT": "V",
    "GCA": "A", "GCC": "A", "GCG": "A", "GCT": "A",
    "GAC": "D", "GAT": "D", "GAA": "E", "GAG": "E",
    "GGA": "G", "GGC": "G", "GGG": "G", "GGT": "G",
    "TCA": "S", "TCC": "S", "TCG": "S", "TCT": "S",
    "TTC": "F", "TTT": "F", "TTA": "L", "TTG": "L",
    "TAC": "Y", "TAT": "Y", "TAA": "*", "TAG": "*",
    "TGC": "C", "TGT": "C", "TGA": "*", "TGG": "W",
}


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
# 1. smith_waterman_align
# ---------------------------------------------------------------------------
def _np_smith_waterman_align(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    s1 = _s(p.get("seq1")).upper()
    s2 = _s(p.get("seq2")).upper()
    if not s1 or not s2 or len(s1) > 20 or len(s2) > 20:
        return None

    match_score = int(_num(p.get("match_score")) or 2)
    mismatch_pen = int(_num(p.get("mismatch_penalty")) or 1)
    gap_pen = int(_num(p.get("gap_penalty")) or 2)

    # Compute local alignment DP matrix
    n1, n2 = len(s1), len(s2)
    dp = [[0] * (n2 + 1) for _ in range(n1 + 1)]
    max_score = 0

    for i in range(1, n1 + 1):
        for j in range(1, n2 + 1):
            diag = dp[i - 1][j - 1] + (match_score if s1[i - 1] == s2[j - 1] else -mismatch_pen)
            up = dp[i - 1][j] - gap_pen
            left = dp[i][j - 1] - gap_pen
            dp[i][j] = max(0, diag, up, left)
            if dp[i][j] > max_score:
                max_score = dp[i][j]

    return {
        **base,
        "seq1": s1,
        "seq2": s2,
        "match_score": match_score,
        "mismatch_penalty": mismatch_pen,
        "gap_penalty": gap_pen,
        "max_score": max_score,
    }


def _grade_smith_waterman_align(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("max_score", 0)
    user_score = _num(submission.get("max_score") if isinstance(submission, dict) else submission)

    if user_score is None:
        return {"ok": False, "score": 0.0, "feedback": "Must submit max alignment score.", "details": {}}

    ok = (int(user_score) == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Smith-Waterman optimal local score ({expected}) verified!" if ok else f"Mismatch in maximum score (expected {expected}).",
        "details": {"submitted": user_score, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 2. orf_finder_translate
# ---------------------------------------------------------------------------
def _np_orf_finder_translate(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    dna = _s(p.get("dna_sequence")).upper().replace(" ", "")
    if not dna or len(dna) < 9:
        return None

    # Find longest forward ORF starting with ATG
    longest_protein = ""
    start_pos = -1

    for i in range(len(dna) - 2):
        if dna[i:i + 3] == "ATG":
            protein = []
            for j in range(i, len(dna) - 2, 3):
                codon = dna[j:j + 3]
                aa = CODON_TABLE.get(codon, "?")
                if aa == "*":
                    if len(protein) > len(longest_protein):
                        longest_protein = "".join(protein)
                        start_pos = i
                    break
                protein.append(aa)

    if not longest_protein:
        return None

    return {
        **base,
        "dna_sequence": dna,
        "protein_sequence": longest_protein,
        "start_index": start_pos,
    }


def _grade_orf_finder_translate(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = _s(item.get("protein_sequence")).upper()
    user_str = _s(submission.get("protein") if isinstance(submission, dict) else submission).upper()

    ok = (user_str == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Translation {expected} matches genetic code!" if ok else "Protein translation mismatch.",
        "details": {"submitted": user_str, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 3. restriction_digest_mapper
# ---------------------------------------------------------------------------
def _np_restriction_digest_mapper(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    length = int(_num(p.get("total_length_bp")) or 5000)
    is_circular = bool(p.get("circular", True))
    sites = p.get("cleavage_sites")
    if not isinstance(sites, list) or not sites:
        return None

    clean_sites = sorted([int(s) for s in sites if _num(s) is not None and 0 <= int(s) <= length])
    if not clean_sites:
        return None

    # Calculate band sizes
    if is_circular:
        fragments = []
        for i in range(len(clean_sites)):
            if i < len(clean_sites) - 1:
                fragments.append(clean_sites[i + 1] - clean_sites[i])
            else:
                fragments.append(length - clean_sites[i] + clean_sites[0])
    else:  # Linear
        all_pts = [0] + clean_sites + [length]
        fragments = [all_pts[i + 1] - all_pts[i] for i in range(len(all_pts) - 1)]

    fragments.sort(reverse=True)

    return {
        **base,
        "total_length_bp": length,
        "circular": is_circular,
        "cleavage_sites": clean_sites,
        "fragment_sizes": fragments,
    }


def _grade_restriction_digest_mapper(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected = item.get("fragment_sizes", [])
    user_frags = submission.get("fragments") if isinstance(submission, dict) else submission

    if not isinstance(user_frags, list):
        return {"ok": False, "score": 0.0, "feedback": "Must submit fragment sizes list.", "details": {}}

    try:
        user_sorted = sorted([int(x) for x in user_frags], reverse=True)
    except Exception:
        return {"ok": False, "score": 0.0, "feedback": "Fragment sizes must be integers.", "details": {}}

    ok = (user_sorted == expected)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"Digested fragment bands ({expected} bp) verified!" if ok else "Fragment lengths mismatch.",
        "details": {"submitted": user_sorted, "expected": expected},
    }


# ---------------------------------------------------------------------------
# 4. phylogenetic_upgma_step
# ---------------------------------------------------------------------------
def _np_phylogenetic_upgma_step(p: Dict[str, Any], base: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    taxa = [_s(t, 20) for t in p.get("taxa", []) if _s(t, 20)]
    matrix = p.get("distance_matrix")  # 2D symmetric distance matrix
    if not taxa or not isinstance(matrix, list) or len(matrix) != len(taxa):
        return None

    # Find minimum distance pair
    n = len(taxa)
    min_dist = float("inf")
    min_i, min_j = -1, -1

    for i in range(n):
        for j in range(i + 1, n):
            d = float(matrix[i][j])
            if d < min_dist:
                min_dist = d
                min_i, min_j = i, j

    if min_i == -1:
        return None

    merged_cluster = f"({taxa[min_i]},{taxa[min_j]})"

    return {
        **base,
        "taxa": taxa,
        "distance_matrix": matrix,
        "min_distance": round(min_dist, 4),
        "merged_cluster": merged_cluster,
        "merged_pair": [taxa[min_i], taxa[min_j]],
    }


def _grade_phylogenetic_upgma_step(item: Dict[str, Any], submission: Any) -> Dict[str, Any]:
    expected_pair = set(item.get("merged_pair", []))
    sub_pair = set(submission.get("pair") if isinstance(submission, dict) else (submission if isinstance(submission, list) else []))

    ok = (sub_pair == expected_pair)
    return {
        "ok": ok,
        "score": 1.0 if ok else 0.0,
        "feedback": f"UPGMA nearest taxa pair {item.get('merged_cluster')} identified!" if ok else "Incorrect taxa pair merged.",
        "details": {"submitted": list(sub_pair), "expected": list(expected_pair)},
    }


NORMALIZERS = {
    "smith_waterman_align": _np_smith_waterman_align,
    "orf_finder_translate": _np_orf_finder_translate,
    "restriction_digest_mapper": _np_restriction_digest_mapper,
    "phylogenetic_upgma_step": _np_phylogenetic_upgma_step,
}

GRADERS = {
    "smith_waterman_align": _grade_smith_waterman_align,
    "orf_finder_translate": _grade_orf_finder_translate,
    "restriction_digest_mapper": _grade_restriction_digest_mapper,
    "phylogenetic_upgma_step": _grade_phylogenetic_upgma_step,
}
