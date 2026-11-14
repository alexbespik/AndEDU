"""
Argument maps (logic engine): a debate as claims and support/attack edges, checked without a model.

{"version": 1, "main": "c1",
 "claims": [{"id": "c1", "text": "...", "role": "conclusion|premise|objection|rebuttal", "formal": "P -> Q"}],
 "edges": [{"from": "c2", "to": "c1", "type": "supports"}, {"from": ["c3", "c4"], "to": "c1", "type": "supports"},
           {"from": "c5", "to": "c1", "type": "attacks"}]}

`formal` (optional) is the claim in propositional notation (logic_formula). Findings:
- unsupported_claim: the main claim, or a claim with role "conclusion", that nothing supports
- disconnected_claim: a claim with no edge at all
- circular_support: claims that support each other in a cycle
- unanswered_objection: a claim that attacks another and is not attacked itself (no rebuttal)
- invalid_inference: a formalised claim whose formalised supporters do not entail it (with a counterexample row)
Turning free text into a map is a separate step (a model may draft it; the student edits it before this runs).
"""
import re
from typing import Any, Dict, List, Tuple

from logic_formula import LogicError, check_validity, parse, to_string

MAX_MAP_CLAIMS = 60
MAX_MAP_EDGES = 200
MAX_TEXT = 500
ROLES = ("conclusion", "premise", "objection", "rebuttal")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def validate_map(raw: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    """(clean map, errors, warnings). Errors make the map unusable; warnings say what was dropped."""
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not isinstance(raw, dict):
        return {}, [{"code": "bad_map", "message": "An argument map is an object with claims and edges."}], warnings
    claims_in, edges_in = raw.get("claims"), raw.get("edges", [])
    if not isinstance(claims_in, list) or not claims_in:
        errors.append({"code": "bad_map", "message": "claims must be a non-empty list."})
        claims_in = []
    if not isinstance(edges_in, list):
        errors.append({"code": "bad_map", "message": "edges must be a list."})
        edges_in = []
    if len(claims_in) > MAX_MAP_CLAIMS or len(edges_in) > MAX_MAP_EDGES:
        return {}, [{"code": "too_large", "message": f"At most {MAX_MAP_CLAIMS} claims and {MAX_MAP_EDGES} edges."}], warnings
    claims: Dict[str, Dict[str, Any]] = {}
    for i, c in enumerate(claims_in):
        where = f"claim {i + 1}"
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not _ID.match(c["id"]):
            errors.append({"code": "bad_claim", "message": f"{where}: an id of letters, digits, - or _ is required."})
            continue
        cid = c["id"]
        if cid in claims:
            errors.append({"code": "duplicate_id", "id": cid, "message": f"{where}: the id '{cid}' is used twice."})
            continue
        text = c.get("text", "")
        if not isinstance(text, str) or len(text) > MAX_TEXT:
            errors.append({"code": "bad_claim", "id": cid, "message": f"{where}: text is up to {MAX_TEXT} characters."})
            continue
        role = c.get("role")
        if role is not None and role not in ROLES:
            warnings.append(f"Claim '{cid}': unknown role '{role}' dropped.")
            role = None
        clean = {"id": cid, "text": text, **({"role": role} if role else {})}
        if c.get("kind") is not None:
            clean["kind"] = str(c["kind"])
        if c.get("predicates") is not None and isinstance(c["predicates"], list):
            clean["predicates"] = [str(p).strip() for p in c["predicates"] if str(p).strip()]
        if c.get("formal") not in (None, ""):
            try:
                clean["formal"] = to_string(parse(c["formal"]))
            except LogicError as e:
                errors.append({"code": "bad_formal", "id": cid, "message": f"Claim '{cid}': {e.message}", "pos": e.pos})
        claims[cid] = clean
    edges: List[Dict[str, Any]] = []
    seen = set()
    for i, e in enumerate(edges_in):
        where = f"edge {i + 1}"
        if not isinstance(e, dict):
            errors.append({"code": "bad_edge", "message": f"{where} must be an object."})
            continue
        src = e.get("from")
        src = [src] if isinstance(src, str) else src
        kind, dst = e.get("type"), e.get("to")
        if kind not in ("supports", "attacks"):
            errors.append({"code": "bad_edge", "message": f"{where}: type is supports or attacks."})
            continue
        if not isinstance(src, list) or not src or not all(isinstance(s, str) for s in src) or not isinstance(dst, str):
            errors.append({"code": "bad_edge", "message": f"{where}: from (an id or a list of ids) and to (an id) are required."})
            continue
        unknown = sorted({s for s in src + [dst] if s not in claims})
        if unknown:
            errors.append({"code": "unknown_id", "ids": unknown, "message": f"{where}: unknown claim id(s) {', '.join(unknown)}."})
            continue
        if dst in src:
            errors.append({"code": "self_edge", "id": dst, "message": f"{where}: a claim cannot {kind[:-1]} itself."})
            continue
        key = (tuple(sorted(set(src))), dst, kind)
        if key in seen:
            warnings.append(f"Duplicate {where} dropped.")
            continue
        seen.add(key)
        edges.append({"from": list(key[0]), "to": dst, "type": kind})
    main = raw.get("main")
    if main is not None and (not isinstance(main, str) or main not in claims):
        errors.append({"code": "unknown_id", "ids": [str(main)], "message": "main is not one of the claims."})
        main = None
    clean_map = {"version": 1, "claims": list(claims.values()), "edges": edges, **({"main": main} if main else {})}
    return clean_map, errors, warnings


def _cycles(nodes: List[str], succ: Dict[str, List[str]]) -> List[List[str]]:
    """Strongly connected groups of more than one claim (Tarjan's algorithm, iterative: no recursion limit)."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack, stack, out = set(), [], []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = counter
                counter += 1
                stack.append(v)
                on_stack.add(v)
            nxt = succ.get(v, [])
            if i < len(nxt):
                work.append((v, i + 1))
                w = nxt[i]
                if w not in index:
                    work.append((w, 0))
                elif w in on_stack:
                    low[v] = min(low[v], index[w])
                continue
            if low[v] == index[v]:
                group = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    group.append(w)
                    if w == v:
                        break
                if len(group) > 1:
                    out.append(sorted(group))
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[v])
    return sorted(out)


_DEONTIC_TERMS = {
    "ought", "should", "must", "right", "wrong", "good", "bad", "evil",
    "permissible", "impermissible", "obligatory", "duty", "virtue", "vicious",
    "just", "unjust", "fair", "unfair", "cruel", "courageous", "noble",
    "blameworthy", "praiseworthy", "moral", "immoral", "ethical", "unethical"
}


def _get_predicates(claim: Dict[str, Any]) -> Set[str]:
    preds = claim.get("predicates")
    if isinstance(preds, (list, tuple, set)) and preds:
        return {str(p).strip().lower() for p in preds if str(p).strip()}
    text = str(claim.get("text") or "").lower()
    words = set(re.findall(r"\b[a-z0-9_-]+\b", text))
    stopwords = {"that", "this", "with", "from", "have", "been", "were", "what", "when", "where", "which", "there", "their", "they"}
    return {w for w in words if (w in _DEONTIC_TERMS or len(w) > 3) and w not in stopwords}


def check_humes_guillotine(claims: Any, edges: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Checks for is-ought gap violations:
    Every normative conclusion C must share moral/deontic predicates with at least one
    ancestral normative premise (c_terms & ancestor_norm_terms), blocking Prior's paradox
    and irrelevant dummy normative premises.
    Returns findings with code: "is_ought_gap" and "is_ought_unbridged_predicates".
    """
    if isinstance(claims, dict):
        raw_edges = claims.get("edges", [])
        main_id = claims.get("main")
        claims_list = claims.get("claims", [])
    else:
        claims_list = list(claims) if isinstance(claims, list) else []
        raw_edges = edges or []
        main_id = None

    claims_by_id = {c["id"]: c for c in claims_list if isinstance(c, dict) and "id" in c}
    
    parents: Dict[str, Set[str]] = {cid: set() for cid in claims_by_id}
    for e in raw_edges:
        if isinstance(e, dict) and e.get("type") == "supports":
            dst = e.get("to")
            srcs = e.get("from")
            srcs = [srcs] if isinstance(srcs, str) else (srcs if isinstance(srcs, list) else [])
            if dst in parents:
                for s in srcs:
                    if s in claims_by_id:
                        parents[dst].add(s)

    violations = []
    for cid, c in claims_by_id.items():
        is_normative = (c.get("kind") == "normative")
        is_conclusion = c.get("role") == "conclusion" or cid == main_id or bool(parents[cid])
        if not (is_normative and is_conclusion and parents[cid]):
            continue

        ancestors = set()
        work = list(parents[cid])
        while work:
            curr = work.pop()
            if curr not in ancestors:
                ancestors.add(curr)
                work.extend(parents.get(curr, set()))

        norm_ancestors = [a for a in ancestors if claims_by_id[a].get("kind") == "normative"]
        c_terms = _get_predicates(c)

        if not norm_ancestors:
            violations.append({
                "code": "is_ought_gap",
                "id": cid,
                "ids": [cid],
                "message": f"Normative conclusion '{cid}' derives from non-normative premises (is-ought gap).",
                "is_ought_unbridged_predicates": sorted(list(c_terms)),
            })
        else:
            ancestor_norm_terms = set()
            for a in norm_ancestors:
                ancestor_norm_terms.update(_get_predicates(claims_by_id[a]))
            bridged = c_terms & ancestor_norm_terms
            if not bridged:
                unbridged = sorted(list(c_terms - ancestor_norm_terms)) or sorted(list(c_terms))
                violations.append({
                    "code": "is_ought_gap",
                    "id": cid,
                    "ids": [cid],
                    "message": f"Normative conclusion '{cid}' does not share moral/deontic predicates with any ancestral normative premise.",
                    "is_ought_unbridged_predicates": unbridged,
                })

    return violations


def analyze(clean: Dict[str, Any]) -> Dict[str, Any]:
    claims = {c["id"]: c for c in clean["claims"]}
    order = [c["id"] for c in clean["claims"]]
    supporters: Dict[str, List[str]] = {cid: [] for cid in order}
    attacked, attackers, touched = set(), set(), set()
    succ: Dict[str, List[str]] = {cid: [] for cid in order}
    for e in clean["edges"]:
        touched.update(e["from"])
        touched.add(e["to"])
        if e["type"] == "supports":
            for s in e["from"]:
                if s not in supporters[e["to"]]:
                    supporters[e["to"]].append(s)
                if e["to"] not in succ[s]:
                    succ[s].append(e["to"])
        else:
            attacked.add(e["to"])
            attackers.update(e["from"])
    findings: List[Dict[str, Any]] = []
    notes: List[Dict[str, Any]] = []
    main = clean.get("main")
    for cid in order:
        c = claims[cid]
        if (cid == main or c.get("role") == "conclusion") and not supporters[cid]:
            findings.append({"code": "unsupported_claim", "ids": [cid], "message": f"Nothing supports '{cid}'."})
        if len(order) > 1 and cid not in touched:
            findings.append({"code": "disconnected_claim", "ids": [cid], "message": f"'{cid}' is not linked to any other claim."})
        if cid in attackers and cid not in attacked:
            findings.append({"code": "unanswered_objection", "ids": [cid], "message": f"No claim answers the objection '{cid}'."})
    for group in _cycles(order, succ):
        findings.append({"code": "circular_support", "ids": group,
                         "message": f"These claims support each other in a circle: {', '.join(group)}."})
    for cid in order:
        sup = supporters[cid]
        if not sup or "formal" not in claims[cid]:
            continue
        missing = [s for s in sup if "formal" not in claims[s]]
        if missing:
            notes.append({"code": "not_formalised", "ids": [cid] + missing,
                          "message": f"'{cid}' was not checked: its supporters {', '.join(missing)} have no formal version."})
            continue
        try:
            verdict = check_validity([parse(claims[s]["formal"]) for s in sup], parse(claims[cid]["formal"]))
        except LogicError as e:
            notes.append({"code": e.code, "ids": [cid], "message": e.message})
            continue
        if not verdict["valid"]:
            findings.append({"code": "invalid_inference", "ids": [cid] + sup, "counterexample": verdict["counterexample"],
                             "message": f"'{cid}' does not follow from {', '.join(sup)}: there is a row where they are true and it is false."})
    findings.extend(check_humes_guillotine(clean))
    findings.sort(key=lambda f: (f["code"], f["ids"]))
    return {"findings": findings, "notes": notes}


def check_map(raw: Any) -> Dict[str, Any]:
    clean, errors, warnings = validate_map(raw)
    if errors:
        raise LogicError("bad_map", "; ".join(e["message"] for e in errors[:5]))
    return {**analyze(clean), "warnings": warnings, "map": clean}
