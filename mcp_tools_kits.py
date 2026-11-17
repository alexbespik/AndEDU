"""Tools for the kit practice types (liberal arts: literature, music, art_history, classics, rhetoric, polity; STEM:
ee, ai, systems, stats, bio). Imported by mcp_server.py, which passes in its HTTP helpers. Items go through the backend,
which normalizes them (computing answer keys for the types that have one) and rejects anything malformed; the answer
keys never come back to the tool. No file writes, no model calls."""

KITS = {
    "literature": ("scansion", "volta_spot", "rhyme_scheme_audit", "chronology_unravel"),
    "music": ("lint_satb_progression", "roman_numeral_analysis", "ear_interval_id", "figured_bass_realize"),
    "art_history": ("composition_vector", "label_architecture", "iconography_decode", "stylistic_taxonomy"),
    "classics": ("epigraphy_transcribe", "harris_matrix_build", "cursus_honorum_order", "athenian_sortition_sim"),
    "rhetoric": ("stasis_classify", "trope_hunter", "dispositio_sort", "enthymeme_excavator"),
    "polity": ("compute_dhondt", "compute_shapley_shubik_pivotal", "veto_pipeline", "instant_runoff_tally"),
    "ee": ("circuit_kcl_kvl", "bode_plot_analyzer", "boolean_gate_minimization", "opamp_gain_calc"),
    "ai": ("backprop_layer_step", "attention_score_matrix", "confusion_matrix_metrics", "loss_gradient_verify"),
    "systems": ("page_table_walk", "cache_tag_index_offset", "assembly_reg_trace", "deadlock_bankers"),
    "stats": ("hypothesis_test_two_sample", "bayes_posterior_update", "mle_parameter_derivation", "markov_steady_state"),
    "bio": ("smith_waterman_align", "orf_finder_translate", "restriction_digest_mapper", "phylogenetic_upgma_step"),
}
KIT_OF = {t: k for k, types in KITS.items() for t in types}


def kit_guide(guide, kit=None):
    """{kit: {type: fields text}} from the backend's practice guide, for one kit or all of them."""
    kits = [kit] if kit else list(KITS)
    unknown = [k for k in kits if k not in KITS]
    if unknown:
        raise ValueError(f"Unknown kit {unknown[0]!r}; choose one of: {', '.join(KITS)}")
    return {k: {t: (guide or {}).get(t, "") for t in KITS[k]} for k in kits}


def tools(call, q, S, STR, OBJ, ARR):
    def kit_types(a):
        return kit_guide(call("GET", "/api/practice/guide"), a.get("kit"))

    def add_kit_practice(a):
        ptype = str(a.get("type") or "")
        if ptype not in KIT_OF:
            raise ValueError(f"{ptype!r} is not a kit practice type; call kit_types to list them.")
        item = dict(a.get("item") or {})
        item["type"] = ptype
        res = call("POST", f"/api/topics/{q(a['topic_id'])}/practice", {"items": [item]})
        if not res.get("added"):
            raise RuntimeError(f"The backend rejected the {ptype} item. Check its fields with kit_types "
                               f"(kit {KIT_OF[ptype]}); every item needs a prompt and the fields listed there.")
        return {**res, "kit": KIT_OF[ptype], "type": ptype}

    return [
        ("kit_types", "The kit practice types (literature, music, art_history, classics, rhetoric, polity, ee, ai, systems, stats, bio) with their fields, from the backend guide. Secret fields (answer keys) are listed as 'Secret'; the server keeps them out of the browser.",
         S(kit=STR("one kit id; all kits when omitted", enum=list(KITS), optional=True)), kit_types),
        ("add_kit_practice", "Add one kit practice item (any of the 44 kit types) to a lesson. The backend validates it, computes answer keys where the type has them and returns {added, rejected, total}; a rejected item raises an error.",
         S(topic_id=STR("topic id"), type=STR("kit practice type", enum=sorted(KIT_OF)), item=OBJ("the item's fields (prompt plus the type's fields, see kit_types)")),
         add_kit_practice),
    ]
