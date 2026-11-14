"""
Declarative Decision Tree Engine for ethical and strategic simulations:
Fog-of-war hidden facts, committed premises, axiomatic weights, and epistemic-neutral consistency tracking.
"""
from typing import Any, Dict, List, Optional, Set, Tuple


def validate_decision_tree_spec(spec: Any) -> Tuple[Dict[str, Any], List[str]]:
    """Validates and normalizes a kind: 'decision_tree' simulation specification.
    Returns (cleaned_spec, errors).
    """
    errors: List[str] = []
    if not isinstance(spec, dict):
        return {}, ["Decision tree spec must be a dictionary"]
    if spec.get("kind") != "decision_tree":
        errors.append("Spec kind must be 'decision_tree'")

    title = str(spec.get("title") or "Decision Tree")[:120]
    description = str(spec.get("description") or "")[:1000]

    raw_nodes = spec.get("nodes")
    nodes: Dict[str, Dict[str, Any]] = {}
    if isinstance(raw_nodes, list):
        for i, n in enumerate(raw_nodes):
            if isinstance(n, dict):
                nid = str(n.get("id") or f"node_{i + 1}")
                nodes[nid] = {**n, "id": nid}
    elif isinstance(raw_nodes, dict):
        for nid, n in raw_nodes.items():
            if isinstance(n, dict):
                nodes[str(nid)] = {**n, "id": str(nid)}
    else:
        errors.append("Spec requires a non-empty 'nodes' dict or list")

    if not nodes:
        errors.append("At least one node is required in 'nodes'")

    clean_nodes: Dict[str, Dict[str, Any]] = {}
    for nid, node in nodes.items():
        text = str(node.get("text") or node.get("prompt") or "")[:2000]
        if not text:
            errors.append(f"Node '{nid}' requires 'text' or 'prompt'")

        raw_choices = node.get("choices") or []
        if not isinstance(raw_choices, list):
            errors.append(f"Node '{nid}': choices must be a list")
            raw_choices = []

        clean_choices: List[Dict[str, Any]] = []
        for j, c in enumerate(raw_choices):
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or f"c{j + 1}")
            ctext = str(c.get("text") or f"Choice {j + 1}")[:500]
            nxt = c.get("next_node")
            nxt_str = str(nxt) if nxt is not None else None

            # Axiomatic weights
            weights: Dict[str, float] = {}
            raw_w = c.get("axiomatic_weights") or {}
            if isinstance(raw_w, dict):
                for ax, val in raw_w.items():
                    try:
                        weights[str(ax)] = float(val)
                    except (ValueError, TypeError):
                        pass

            reveals = [str(f) for f in c.get("reveals_facts", []) if str(f)]
            premises_comm = [str(p) for p in c.get("premises_committed", []) if str(p)]

            clean_choices.append({
                "id": cid,
                "text": ctext,
                "next_node": nxt_str,
                "axiomatic_weights": weights,
                "reveals_facts": reveals,
                "premises_committed": premises_comm,
            })

        clean_nodes[nid] = {
            "id": nid,
            "text": text,
            "choices": clean_choices,
            "premises": [str(p) for p in node.get("premises", []) if str(p)],
            "hidden_facts": [str(f) for f in node.get("hidden_facts", []) if str(f)],
        }

    # Verify initial_node
    initial_node = spec.get("initial_node")
    if initial_node is not None:
        initial_node = str(initial_node)
        if initial_node not in clean_nodes:
            errors.append(f"initial_node '{initial_node}' does not exist in nodes")
    elif clean_nodes:
        initial_node = list(clean_nodes.keys())[0]

    # Verify next_node references
    for nid, node in clean_nodes.items():
        for ch in node["choices"]:
            nxt = ch.get("next_node")
            if nxt is not None and nxt not in clean_nodes:
                errors.append(f"Node '{nid}' choice '{ch['id']}' references non-existent next_node '{nxt}'")

    # Fog of war hidden facts mapping
    raw_fog = spec.get("fog_of_war_hidden_facts") or {}
    fog_facts: Dict[str, str] = {}
    if isinstance(raw_fog, dict):
        for fid, fdesc in raw_fog.items():
            fog_facts[str(fid)] = str(fdesc)
    elif isinstance(raw_fog, list):
        for item in raw_fog:
            fog_facts[str(item)] = str(item)

    clean_spec = {
        "version": 1,
        "kind": "decision_tree",
        "title": title,
        "description": description,
        "initial_node": initial_node,
        "nodes": clean_nodes,
        "fog_of_war_hidden_facts": fog_facts,
        "axioms": [str(a) for a in spec.get("axioms", []) if str(a)],
    }
    return clean_spec, errors


def step_decision_tree(spec: Dict[str, Any], history: Optional[List[Dict[str, Any]]], choice: str) -> Dict[str, Any]:
    """Steps the decision tree engine forward:
    - Traverses nodes based on history and choice.
    - Unveils fog_of_war_hidden_facts revealed by chosen actions.
    - Accumulates stated premises and axiomatic weights.
    - Tracks consistency/tensions neutrally without normative ranking.
    """
    clean_spec, errors = validate_decision_tree_spec(spec)
    if errors:
        return {"ok": False, "error": f"Invalid spec: {'; '.join(errors)}"}

    nodes = clean_spec["nodes"]
    initial_node_id = clean_spec["initial_node"]
    fog_dict = clean_spec.get("fog_of_war_hidden_facts", {})

    hist = list(history or [])

    # Trace past history to reach current node
    curr_nid = initial_node_id
    revealed_fact_keys: Set[str] = set()
    stated_premises: List[str] = []
    axiomatic_totals: Dict[str, float] = {}
    choice_weights_history: List[Dict[str, float]] = []

    # Include initial node premises
    if curr_nid in nodes:
        stated_premises.extend(nodes[curr_nid].get("premises", []))

    for step in hist:
        step_nid = step.get("node_id")
        step_cid = step.get("choice_id")
        if step_nid not in nodes:
            continue
        c_node = nodes[step_nid]
        matching = [c for c in c_node["choices"] if c["id"] == step_cid]
        if not matching:
            continue
        matched = matching[0]
        revealed_fact_keys.update(matched.get("reveals_facts", []))
        stated_premises.extend(matched.get("premises_committed", []))
        w = matched.get("axiomatic_weights", {})
        choice_weights_history.append(w)
        for ax, val in w.items():
            axiomatic_totals[ax] = axiomatic_totals.get(ax, 0.0) + val
        nxt = matched.get("next_node")
        if nxt and nxt in nodes:
            curr_nid = nxt
            stated_premises.extend(nodes[curr_nid].get("premises", []))

    # Now execute current choice at curr_nid
    if curr_nid not in nodes:
        return {"ok": False, "error": f"Current node '{curr_nid}' not found in decision tree"}

    current_node = nodes[curr_nid]
    matching_choices = [c for c in current_node["choices"] if c["id"] == str(choice) or c["text"] == str(choice)]
    if not matching_choices:
        return {"ok": False, "error": f"Choice '{choice}' not found in node '{curr_nid}'"}

    chosen = matching_choices[0]
    revealed_fact_keys.update(chosen.get("reveals_facts", []))
    stated_premises.extend(chosen.get("premises_committed", []))
    curr_w = chosen.get("axiomatic_weights", {})
    choice_weights_history.append(curr_w)
    for ax, val in curr_w.items():
        axiomatic_totals[ax] = axiomatic_totals.get(ax, 0.0) + val

    updated_hist = hist + [{"node_id": curr_nid, "choice_id": chosen["id"]}]

    nxt_nid = chosen.get("next_node")
    is_terminal = (nxt_nid is None or nxt_nid not in nodes or len(nodes[nxt_nid]["choices"]) == 0)

    if nxt_nid and nxt_nid in nodes:
        stated_premises.extend(nodes[nxt_nid].get("premises", []))

    # Consistency tracking: detect trade-offs / philosophical tensions between decisions
    tensions: List[str] = []
    # Check if weights on any axiom flipped sign across choices
    flipped_axioms = set()
    for ax in axiomatic_totals:
        signs = [w[ax] for w in choice_weights_history if ax in w and abs(w[ax]) > 0.01]
        has_pos = any(s > 0 for s in signs)
        has_neg = any(s < 0 for s in signs)
        if has_pos and has_neg:
            flipped_axioms.add(ax)
            tensions.append(f"Axiomatic tension detected on '{ax}': prior choices supported this framework while other choices constrained it.")

    # Consistency metric: 1.0 - (ratio of flipped axioms to evaluated axioms)
    evaluated_count = len(axiomatic_totals)
    consistency_score = 1.0
    if evaluated_count > 0:
        consistency_score = max(0.0, min(1.0, 1.0 - (len(flipped_axioms) / evaluated_count)))

    # Revealed facts descriptions
    revealed_facts_output = [
        {"id": k, "description": fog_dict.get(k, k)}
        for k in sorted(revealed_fact_keys)
    ]

    return {
        "ok": True,
        "current_node_id": nxt_nid if nxt_nid else curr_nid,
        "node": nodes.get(nxt_nid) if nxt_nid and nxt_nid in nodes else None,
        "is_terminal": is_terminal,
        "history": updated_hist,
        "revealed_facts": revealed_facts_output,
        "stated_premises": list(dict.fromkeys(stated_premises)),
        "axiomatic_weights": {k: round(v, 3) for k, v in axiomatic_totals.items()},
        "consistency": round(consistency_score, 2),
        "tensions": tensions,
    }
